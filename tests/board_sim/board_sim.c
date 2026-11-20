// Runs the real che126_daq firmware on a simulated ATmega2560 (simavr) with three
// emulated MAX31855 amplifiers, a relay on D33 and a small thermal plant, and
// exposes the board's serial port as a pseudo-terminal. Test harness only.
//
//   board_sim <firmware.elf|-> <link-path> <control-fifo> [bootloader.hex]
//
// With a bootloader the chip starts in it (like a real reset), so a firmware upload
// over the pty can be tested; "-" starts with empty application flash.
//
// <link-path> becomes a symlink to the pty, so daq.py can open it like a real port.
// Lines written to <control-fifo> steer the plant:
//   V <volts>            variac voltage (default 100)
//   SET <ch> <C>         force a channel's temperature (plant keeps evolving)
//   FAULT <ch> <bits>    MAX31855 fault bits on a channel (0 clears)
//   MISSING <ch> <0|1>   amplifier absent: DO floats high
//   GLITCH <ch>          next reading on <ch> is 2048 C
//   RESET                reset the chip (starts in the bootloader if one is loaded)
//   QUIT
// Relay changes are printed to stderr as "relay on|off t=<s>".

#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <pty.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

#include <simavr/avr_ioport.h>
#include <simavr/avr_uart.h>
#include <simavr/sim_avr.h>
#include <simavr/sim_elf.h>
#include <simavr/sim_hex.h>
#include <simavr/sim_irq.h>

static avr_t *avr;
static int pty_master = -1;
static int uart_xon = 1;

// Physical amplifier pins: {CLK port, CLK bit, DO port, DO bit, CS port, CS bit}
typedef struct { char clk_port; int clk_bit; char do_port; int do_bit; char cs_port; int cs_bit; } amp_pins_t;
static const amp_pins_t PINS[3] = {
    {'A', 0, 'A', 2, 'A', 4},  // D22 D24 D26
    {'A', 6, 'C', 7, 'C', 5},  // D28 D30 D32
    {'C', 3, 'C', 1, 'D', 7},  // D34 D36 D38
};
#define RELAY_PORT 'C'
#define RELAY_BIT 4  // D33

typedef struct {
  int idx;
  int cs_low;
  int clk;
  uint32_t word;
  int bit;  // next bit index to present
  avr_irq_t *do_irq;
} amp_t;
static amp_t amps[3];

// Plant. Amplifier 2 sits on the heater (TC1 in the app); amplifier 1 is behind the
// barrier (TC2); amplifier 3 reads the heater core.
static double volts = 100.0;
static double temp[3] = {24.0, 24.5, 24.0};  // per physical amplifier
static double t_heater = 24.5, t_rear = 24.0, t_core = 24.5;
static int fault_bits[3] = {0, 0, 0};
static int missing[3] = {0, 0, 1};
static int glitch[3] = {0, 0, 0};
static int relay_pin = 1;  // NC wiring: pin HIGH = OFF
static double sim_time = 0;

static double now_s(void) { return (double)avr->cycle / avr->frequency; }

static int heater_powered(void) {
  // EEPROM default is NC; the harness assumes NC wiring (pin LOW = heat).
  return relay_pin == 0;
}

static void plant_step(double dt) {
  const double ambient = 24.0;
  double power = heater_powered() ? volts * volts / 28.8 : 0.0;  // 500 W at 120 V
  // Lumped nodes: core -> heater surface -> barrier rear -> ambient.
  double q_core_surf = (t_core - t_heater) / 0.25;
  double q_surf_rear = (t_heater - t_rear) / 4.0;
  double q_surf_amb = (t_heater - ambient) / 2.2;
  double q_rear_amb = (t_rear - ambient) / 3.0;
  t_core += dt * (power - q_core_surf) / 60.0;
  t_heater += dt * (q_core_surf - q_surf_rear - q_surf_amb) / 110.0;
  t_rear += dt * (q_surf_rear - q_rear_amb) / 220.0;
  temp[1] = t_heater;
  temp[0] = t_rear;
  temp[2] = t_core;
}

static uint32_t encode(int ch) {
  if (missing[ch]) return 0xFFFFFFFFu;
  double t = temp[ch];
  if (glitch[ch]) { t = 2048.0 - 0.25; glitch[ch] = 0; }
  int32_t tc = (int32_t)lround(t * 4.0);
  if (tc > 8191) tc = 8191;
  if (tc < -8192) tc = -8192;
  int32_t internal = (int32_t)lround(25.0 * 16.0);
  uint32_t w = ((uint32_t)(tc & 0x3FFF) << 18) | ((uint32_t)(internal & 0xFFF) << 4);
  if (fault_bits[ch]) w |= (1u << 16) | (uint32_t)(fault_bits[ch] & 7);
  return w;
}

static void present(amp_t *a) {
  int v = a->bit >= 0 ? (a->word >> a->bit) & 1 : 0;
  avr_raise_irq(a->do_irq, v);
}

static void on_cs(struct avr_irq_t *irq, uint32_t value, void *param) {
  (void)irq;
  amp_t *a = param;
  if (!value && !a->cs_low) {  // falling: latch a conversion, D31 first
    a->cs_low = 1;
    a->word = encode(a->idx);
    a->bit = 31;
    present(a);
  } else if (value) {
    a->cs_low = 0;
    avr_raise_irq(a->do_irq, missing[a->idx] ? 1 : 0);
  }
}

static void on_clk(struct avr_irq_t *irq, uint32_t value, void *param) {
  (void)irq;
  amp_t *a = param;
  int falling = a->clk && !value;
  a->clk = value ? 1 : 0;
  if (falling && a->cs_low && a->bit >= 0) {
    // The first falling edge after CS (clock idles low) is not an edge; the
    // firmware writes LOW before each read, so only HIGH->LOW transitions shift.
    a->bit--;
    present(a);
  }
}

static void on_relay(struct avr_irq_t *irq, uint32_t value, void *param) {
  (void)irq; (void)param;
  int was = heater_powered();
  relay_pin = value ? 1 : 0;
  if (was != heater_powered()) fprintf(stderr, "relay %s t=%.3f\n", heater_powered() ? "on" : "off", now_s());
}

static void on_uart_out(struct avr_irq_t *irq, uint32_t value, void *param) {
  (void)irq; (void)param;
  uint8_t c = value;
  if (pty_master >= 0) (void)!write(pty_master, &c, 1);
}
static void on_xon(struct avr_irq_t *irq, uint32_t value, void *param) { (void)irq; (void)value; (void)param; uart_xon = 1; }
static void on_xoff(struct avr_irq_t *irq, uint32_t value, void *param) { (void)irq; (void)value; (void)param; uart_xon = 0; }

static void control_line(char *line) {
  int ch; double v;
  if (sscanf(line, "V %lf", &v) == 1) volts = v;
  else if (sscanf(line, "SET %d %lf", &ch, &v) == 2 && ch >= 1 && ch <= 3) {
    if (ch == 2) t_heater = v; else if (ch == 1) t_rear = v; else t_core = v;
    temp[ch - 1] = v;
  } else if (sscanf(line, "FAULT %d %lf", &ch, &v) == 2 && ch >= 1 && ch <= 3) fault_bits[ch - 1] = (int)v;
  else if (sscanf(line, "MISSING %d %lf", &ch, &v) == 2 && ch >= 1 && ch <= 3) missing[ch - 1] = (int)v;
  else if (sscanf(line, "GLITCH %d", &ch) == 1 && ch >= 1 && ch <= 3) glitch[ch - 1] = 1;
  else if (!strncmp(line, "RESET", 5)) { avr_reset(avr); fprintf(stderr, "reset t=%.3f\n", now_s()); }
  else if (!strncmp(line, "QUIT", 4)) exit(0);
}

int main(int argc, char **argv) {
  if (argc != 4 && argc != 5) {
    fprintf(stderr, "usage: board_sim <firmware.elf|-> <link-path> <control-fifo> [bootloader.hex]\n");
    return 2;
  }
  signal(SIGPIPE, SIG_IGN);
  avr = avr_make_mcu_by_name("atmega2560");
  if (!avr) { fprintf(stderr, "no atmega2560 core\n"); return 1; }
  avr_init(avr);
  avr->frequency = 16000000;
  if (strcmp(argv[1], "-")) {
    elf_firmware_t fw = {0};
    if (elf_read_firmware(argv[1], &fw)) { fprintf(stderr, "cannot read %s\n", argv[1]); return 1; }
    avr_load_firmware(avr, &fw);
  }
  if (argc == 5) {
    ihex_chunk_p chunks = NULL;
    int n = read_ihex_chunks(argv[4], &chunks);
    if (n <= 0) { fprintf(stderr, "cannot read %s\n", argv[4]); return 1; }
    uint32_t lo = 0xFFFFFFFF;
    for (int i = 0; i < n; i++) {
      memcpy(avr->flash + chunks[i].baseaddr, chunks[i].data, chunks[i].size);
      if (chunks[i].baseaddr < lo) lo = chunks[i].baseaddr;
    }
    avr->reset_pc = lo;
    avr->pc = lo;
    avr->codeend = avr->flashend;
    fprintf(stderr, "bootloader at 0x%05X\n", lo);
  }
  avr->log = 0;

  int slave;
  char name[256];
  if (openpty(&pty_master, &slave, name, NULL, NULL)) { perror("openpty"); return 1; }
  struct termios tio;
  tcgetattr(slave, &tio);
  cfmakeraw(&tio);
  tcsetattr(slave, TCSANOW, &tio);
  fcntl(pty_master, F_SETFL, O_NONBLOCK);
  unlink(argv[2]);
  if (symlink(name, argv[2])) { perror("symlink"); return 1; }
  fprintf(stderr, "pty %s -> %s\n", argv[2], name);

  int ctl = open(argv[3], O_RDWR | O_NONBLOCK);
  if (ctl < 0) { perror("control fifo"); return 1; }

  for (int i = 0; i < 3; i++) {
    amps[i].idx = i;
    amps[i].bit = -1;
    amps[i].do_irq = avr_io_getirq(avr, AVR_IOCTL_IOPORT_GETIRQ(PINS[i].do_port), PINS[i].do_bit);
    avr_irq_register_notify(avr_io_getirq(avr, AVR_IOCTL_IOPORT_GETIRQ(PINS[i].cs_port), PINS[i].cs_bit), on_cs, &amps[i]);
    avr_irq_register_notify(avr_io_getirq(avr, AVR_IOCTL_IOPORT_GETIRQ(PINS[i].clk_port), PINS[i].clk_bit), on_clk, &amps[i]);
    avr_raise_irq(amps[i].do_irq, missing[i] ? 1 : 0);
  }
  avr_irq_register_notify(avr_io_getirq(avr, AVR_IOCTL_IOPORT_GETIRQ(RELAY_PORT), RELAY_BIT), on_relay, NULL);
  avr_irq_t *uart_in = avr_io_getirq(avr, AVR_IOCTL_UART_GETIRQ('0'), UART_IRQ_INPUT);
  avr_irq_register_notify(avr_io_getirq(avr, AVR_IOCTL_UART_GETIRQ('0'), UART_IRQ_OUTPUT), on_uart_out, NULL);
  avr_irq_register_notify(avr_io_getirq(avr, AVR_IOCTL_UART_GETIRQ('0'), UART_IRQ_OUT_XON), on_xon, NULL);
  avr_irq_register_notify(avr_io_getirq(avr, AVR_IOCTL_UART_GETIRQ('0'), UART_IRQ_OUT_XOFF), on_xoff, NULL);

  struct timespec start;
  clock_gettime(CLOCK_MONOTONIC, &start);
  uint8_t inbuf[256];
  int in_len = 0, in_pos = 0;
  char ctlbuf[256];
  int ctl_len = 0;
  avr_cycle_count_t next_check = 0;

  for (;;) {
    int state = avr_run(avr);
    if (state == cpu_Done || state == cpu_Crashed) {
      fprintf(stderr, "avr stopped: state %d\n", state);
      return 1;
    }
    if (avr->cycle < next_check) continue;
    next_check = avr->cycle + 16000;  // every simulated millisecond

    double t = now_s();
    if (t - sim_time >= 0.01) { plant_step(t - sim_time); sim_time = t; }

    if (in_pos >= in_len) {
      in_len = read(pty_master, inbuf, sizeof inbuf);
      if (in_len < 0) in_len = 0;
      in_pos = 0;
    }
    // About 115200 baud: up to 11 bytes per simulated millisecond, paused while the
    // UART's receive FIFO reports full (XOFF).
    uart_xon = 1;
    for (int k = 0; k < 11 && uart_xon && in_pos < in_len; k++) avr_raise_irq(uart_in, inbuf[in_pos++]);

    int n = read(ctl, ctlbuf + ctl_len, sizeof ctlbuf - 1 - ctl_len);
    if (n > 0) {
      ctl_len += n;
      ctlbuf[ctl_len] = 0;
      char *nl;
      while ((nl = strchr(ctlbuf, '\n'))) {
        *nl = 0;
        control_line(ctlbuf);
        memmove(ctlbuf, nl + 1, strlen(nl + 1) + 1);
        ctl_len = strlen(ctlbuf);
      }
    }

    // Keep simulated time in step with the wall clock.
    struct timespec wall;
    clock_gettime(CLOCK_MONOTONIC, &wall);
    double elapsed = (wall.tv_sec - start.tv_sec) + (wall.tv_nsec - start.tv_nsec) / 1e9;
    if (t > elapsed + 0.002) {
      struct timespec ts = {0, (long)((t - elapsed) * 1e9)};
      nanosleep(&ts, NULL);
    }
  }
}
