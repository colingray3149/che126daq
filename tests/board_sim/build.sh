#!/usr/bin/env bash
# Build the simulator (Linux; needs simavr and libelf) and the firmware .elf (arduino-cli).
#   nix shell nixpkgs#simavr nixpkgs#elfutils nixpkgs#gcc nixpkgs#arduino-cli -c tests/board_sim/build.sh
# On NixOS without the shell above, this script finds simavr/elfutils through nix itself.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
out=${OUT:-/tmp}
simavr=${SIMAVR:-$(nix build --no-link --print-out-paths nixpkgs#simavr)}
elf=${ELFUTILS:-$(nix build --no-link --print-out-paths nixpkgs#elfutils.out | head -1)}
gcc -O2 -Wall -Wextra -I"$simavr/include" -o "$out/board_sim" "$here/board_sim.c" \
  "$simavr/lib/libsimavr.so" -L"$elf/lib" -lelf -lm -lutil -Wl,-rpath,"$simavr/lib:$elf/lib"
arduino-cli compile --fqbn arduino:avr:mega:cpu=atmega2560 --output-dir "$out/che126_fw" "$here/../../firmware/che126_daq"
echo "BOARD_SIM=$out/board_sim FIRMWARE_ELF=$out/che126_fw/che126_daq.ino.elf"
