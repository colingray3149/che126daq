"""Upload a .hex to an Arduino Mega 2560 / Mega ADK through its STK500v2 bootloader.

Same steps as the Arduino IDE (avrdude -c wiring): pulse DTR to reset the board,
talk to the bootloader for the first second after reset, write 256-byte pages,
read everything back to verify, then leave programming mode so the new firmware
starts.
"""

from __future__ import annotations

import time

import serial

START, TOKEN = 0x1B, 0x0E
CMD_SIGN_ON = 0x01
CMD_LOAD_ADDRESS = 0x06
CMD_ENTER_PROGMODE = 0x10
CMD_LEAVE_PROGMODE = 0x11
CMD_PROGRAM_FLASH = 0x13
CMD_READ_FLASH = 0x14
CMD_READ_SIGNATURE = 0x1B
STATUS_OK = 0x00
PAGE = 256
SIGNATURE_2560 = bytes([0x1E, 0x98, 0x01])


class UploadError(Exception):
    pass


def read_hex(path):
    """Intel HEX -> (start address, bytes)."""
    mem = {}
    base = 0
    with open(path, encoding="ascii") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            if not line.startswith(":"):
                raise UploadError("%s line %d is not Intel HEX" % (path, n))
            raw = bytes.fromhex(line[1:])
            if sum(raw) & 0xFF:
                raise UploadError("%s line %d has a bad checksum" % (path, n))
            count, addr, kind = raw[0], (raw[1] << 8) | raw[2], raw[3]
            data = raw[4:4 + count]
            if kind == 0:
                for i, b in enumerate(data):
                    mem[base + addr + i] = b
            elif kind == 1:
                break
            elif kind == 2:
                base = ((data[0] << 8) | data[1]) << 4
            elif kind == 4:
                base = ((data[0] << 8) | data[1]) << 16
    if not mem:
        raise UploadError("%s holds no data" % path)
    lo, hi = min(mem), max(mem) + 1
    return lo, bytes(mem.get(a, 0xFF) for a in range(lo, hi))


class Bootloader:
    def __init__(self, ser):
        self.ser = ser
        self.seq = 1

    def command(self, body, timeout=1.0):
        msg = bytes([START, self.seq, len(body) >> 8, len(body) & 0xFF, TOKEN]) + bytes(body)
        cs = 0
        for b in msg:
            cs ^= b
        self.ser.write(msg + bytes([cs]))
        deadline = time.monotonic() + timeout
        state, buf, size = 0, bytearray(), 0
        while time.monotonic() < deadline:
            c = self.ser.read(1)
            if not c:
                continue
            b = c[0]
            buf.append(b)
            if state == 0:
                if b == START:
                    buf = bytearray([b])
                    state = 1
                else:
                    buf = bytearray()
            elif state == 1:
                state = 2 if b == self.seq else 0
            elif state == 2:
                size = b << 8
                state = 3
            elif state == 3:
                size |= b
                state = 4
            elif state == 4:
                state = 5 if b == TOKEN else 0
            elif state == 5:
                if len(buf) == 5 + size + 1:
                    cs = 0
                    for x in buf:
                        cs ^= x
                    if cs:
                        raise UploadError("bootloader reply had a bad checksum")
                    self.seq = (self.seq + 1) & 0xFF
                    reply = bytes(buf[5:-1])
                    if not reply or reply[0] != body[0]:
                        raise UploadError("unexpected bootloader reply")
                    if len(reply) > 1 and reply[1] != STATUS_OK:
                        raise UploadError("bootloader refused command 0x%02X (status 0x%02X)" % (body[0], reply[1]))
                    return reply
        raise UploadError("no answer from the bootloader")


def flash(port, hex_path, log=print, verify=True):
    start, image = read_hex(hex_path)
    if start != 0:
        raise UploadError("firmware must start at address 0")
    image += b"\xff" * (-len(image) % PAGE)
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = 115200
    ser.timeout = 0.05
    try:
        ser.open()
    except (serial.SerialException, OSError) as e:
        raise UploadError("cannot open %s: %s" % (port, e))
    try:
        bl = Bootloader(ser)
        # Reset: DTR low then high; the bootloader listens briefly after reset.
        try:
            ser.dtr = False
            ser.rts = False
            time.sleep(0.25)
            ser.dtr = True
            ser.rts = True
            time.sleep(0.05)
        except OSError:
            pass  # not a real serial port (simulator); the bootloader is already listening
        ser.reset_input_buffer()
        deadline = time.monotonic() + 5.0
        while True:
            try:
                bl.command([CMD_SIGN_ON], timeout=0.6)
                break
            except UploadError:
                if time.monotonic() > deadline:
                    raise UploadError("the board's bootloader did not answer on %s (is it an Arduino Mega?)" % port)
        bl.command([CMD_ENTER_PROGMODE, 200, 100, 25, 32, 0, 0x53, 3, 0xAC, 0x53, 0, 0])
        sig = bytes(bl.command([CMD_READ_SIGNATURE, 4, 0x30, 0, i, 0])[2] for i in range(3))
        if sig != SIGNATURE_2560:
            raise UploadError("this is not an ATmega2560 (signature %s)" % sig.hex())
        log("Bootloader found; writing %d bytes" % len(image))
        for addr in range(0, len(image), PAGE):
            # Every page in order from 0: the bootloader erases pages on its own counter.
            page = image[addr:addr + PAGE]
            word = (addr >> 1) | 0x80000000
            bl.command([CMD_LOAD_ADDRESS, word >> 24 & 0xFF, word >> 16 & 0xFF, word >> 8 & 0xFF, word & 0xFF])
            bl.command([CMD_PROGRAM_FLASH, PAGE >> 8, PAGE & 0xFF, 0xC1, 10, 0x40, 0x4C, 0x20, 0, 0] + list(page), timeout=10.0)
        if verify:
            for addr in range(0, len(image), PAGE):
                word = (addr >> 1) | 0x80000000
                bl.command([CMD_LOAD_ADDRESS, word >> 24 & 0xFF, word >> 16 & 0xFF, word >> 8 & 0xFF, word & 0xFF])
                got = bl.command([CMD_READ_FLASH, PAGE >> 8, PAGE & 0xFF, 0x20], timeout=5.0)[2:2 + PAGE]
                if got != image[addr:addr + PAGE]:
                    raise UploadError("verify failed at 0x%05X; upload again" % addr)
            log("Verified")
        bl.command([CMD_LEAVE_PROGMODE, 1, 1])
    finally:
        try:
            ser.close()
        except Exception:
            pass
