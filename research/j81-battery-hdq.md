# J81 battery gauge over UART5/HDQ

Date: 2026-09-08

Target: iPad Air 2 Wi-Fi, J81/J81AP, A8X/T7001

Kernel baseline: Hoolock Linux 7.3-rc1 at
`6831bc701a6ce059e71e5aaa9488c9195bea6927`

## Decision

Keep the current kernel. It already has the Samsung/Apple UART driver, the
serial-device bus, the TI bq27xxx power-supply core, and UART5's power domain.
The missing pieces are small and local:

1. describe UART5 and AP GPIO34 in the T7001/J81 device tree;
2. add stop-bit selection to the tty-backed serdev API;
3. add an HDQ-over-UART serdev frontend that reuses the bq27xxx core.

Do not use `w1-uart`, replace the bq27xxx core, import Corellium's complete
power-supply driver, or change kernels. Those paths either implement the wrong
wire protocol or duplicate code already present in this kernel.

The first hardware build should identify the gauge and expose read-only
standard measurements. Battery data-flash writes, battery authentication,
charger control, and Apple POSM policy are outside this step.

## Repository and live-device state

The overnight work established a much stronger starting point:

- The private real-J81 ADT capture exists under ignored `artifacts/adt/`.
- Its sanitized UART5 and gas-gauge facts are recorded in
  `docs/plans/2026-09-08-j81-bluetooth-battery-adt.md`.
- UART3 was added from the same resource pattern and registered on hardware,
  which validates the T7001 UART description method.
- The iPad is reachable over CDC-ECM at `172.16.42.1:23`, so the next battery
  image can be tested without relying on the display.

A fresh read-only check of the running device on 2026-09-08 found Linux
`7.3.0-rc1`, UART0 and UART3 only, no UART5 node, and no registered power
supply. This is the expected pre-battery baseline.

## Hardware evidence from this J81

The private ADT says:

| Resource | Real J81 value | Linux description |
| --- | --- | --- |
| UART | `uart5`, `uart-1,samsung` | `apple,s5l-uart` |
| Register range | base `0x20a0d4000`, size `0x4000` | `reg = <0x2 0x0a0d4000 0 0x4000>` |
| Interrupt | AIC hardware IRQ 163, level high | `interrupts = <AIC_IRQ 163 IRQ_TYPE_LEVEL_HIGH>` |
| Clock gate | `0x55` | bootloader reference clocks for now |
| Power domain | UART5 | existing `ps_uart5` in `t7001-pmgr.dtsi` |
| Flow control | `no-flow-control` | no `uart-has-rtscts` |
| Data pin | AP GPIO34, hardware-verified function 1 | `APPLE_PINMUX(34, 1)` |
| Gauge identity hint | `gas-gauge,bq27540`, `gas-gauge,hdq` | identify through TI `DEVICE_TYPE` before choosing a core table |

The gauge is a child of UART5. Its `function-battery_swi` OIPG payload is
byte-identical to UART5's `function-tx`, independently confirming that the
single-wire bus uses UART5 TX on AP GPIO34. No RX, enable, interrupt, or charger
phandle is present on the gauge child.

TI specifies an open-drain HDQ pin. Hoolock's Apple GPIO driver has no generic
open-drain pin configuration; its mux operation selects the peripheral, enables
input, and preserves the other GPIO register fields. Live hardware testing
proved that GPIO34 peripheral function 1 supplies the required UART5 TX/HDQ
route. The ADT OIPG flags value `0x102` is not a Linux pin-function selector;
using its low byte as function 2 was the BAT-4 root cause.

J81's `charger,k48` is a logical charger-policy node whose `function-set_charger`
target resolves to the D2207/Arabela PMU. Apple's own J81-era HDQ driver talks
directly through AppleSamsungSerial and does not switch a charger mux. The
SN2400 mux in Corellium's later-device implementation is therefore not part of
the J81 data path.

The raw ADT contains battery calibration and per-device data. It remains
ignored and must not be committed. The table above is sufficient board data
for the driver work.

## Important serdev correction

Earlier repository notes concluded that `apple,s5l-uart` could not host a
serdev child because `drivers/tty/serial/samsung_tty.c` does not call
`serdev_tty_port_register()` directly. That conclusion is wrong.

In the exact pinned source:

1. `samsung_tty.c` calls `uart_add_one_port()`;
2. `drivers/tty/serial/serial_core.c` then calls
   `tty_port_register_device_attr_serdev()` for that UART;
3. `drivers/tty/tty_port.c` registers a serdev controller when the UART's DT
   node has a child, and creates a tty device only when it does not.

The built configuration already has `CONFIG_SERIAL_DEV_BUS=y` and
`CONFIG_SERIAL_DEV_CTRL_TTYPORT=y`. A gauge child below `&serial5` will
therefore probe as a serdev device. When that child exists, `/dev/ttySAC2` is
expected to disappear because the serial core intentionally gives the port to
serdev instead of registering a tty character device.

No Samsung UART driver change is needed for registration, transmit, receive,
flow control, baud rate, parity, break control, or TX drain. The common tty
serdev controller supplies those operations through the existing UART ops.

## The actual serdev gap: two stop bits

TI HDQ is an asynchronous return-to-one single-wire protocol. Corellium's
working Apple transport maps one HDQ bit to one UART frame:

- `0xfe` encodes one;
- `0xc0` encodes zero;
- bytes are sent at 57,600 baud, 8 data bits, no parity, and 2 stop bits;
- an HDQ break is sent before each transaction;
- received UART bytes are decoded back into HDQ bits.

The exact Hoolock kernel's mainline serdev API has baud, parity, flow-control,
break, and wait-until-sent methods, but no stop-bit setter. The Samsung driver
does honor `CSTOPB`; the setting is simply not reachable from a serdev client.
Corellium carried a generic serdev stop-bit extension for this driver. A
similar 36-line API was proposed to Linux in 2019 but was not merged because
the submitter had no upstreamable user at the time.

Two stop bits are functional, not cosmetic. With the Corellium encoding:

| UART framing | HDQ cycle | one low pulse | zero low pulse | TI limits |
| --- | ---: | ---: | ---: | --- |
| 57,600 8N2 | 190.97 us | 34.72 us | 121.53 us | passes |
| 57,600 8N1 | 173.61 us | 34.72 us | 121.53 us | cycle too short |
| 50,000 8N1 | 200.00 us | 40.00 us | 140.00 us | passes on paper |

TI specifies at least 190 us per host-to-gauge bit, a 0.5-50 us host-one low
pulse, and an 86-145 us host-zero low pulse. Running 50,000 8N1 is a possible
fallback, but its UART receive thresholds and real clock error have not been
validated on Apple hardware. The first implementation should use the proven
57,600 8N2 framing and add the small general serdev API instead of depending on
an untested timing substitution.

## Transport behavior to retain

The frontend should reuse the useful part of Corellium's implementation:

- open the serdev port at 57,600 8N2, no parity, no flow control;
- drive break for 250-500 us, then leave 150-500 us recovery time;
- serialize transactions with one mutex;
- encode every byte LSB first into eight `0xfe`/`0xc0` UART bytes;
- synchronize reception on the eight-byte command echo;
- use a bounded 500 ms completion timeout;
- read 16-bit registers high/low/high and retry when the high byte changed;
- use HDQ command bit 7 as read=0 and write=1.

The timings satisfy TI's published minimum 190 us break and 40 us recovery.
The TI command byte has a seven-bit register address and bit 7 selects read or
write. Each read returns one byte. A word read must therefore read adjacent
registers in separate HDQ transactions.

The receive callback must only move transaction state while holding a
spinlock; it cannot sleep. Probe, register reads, and writes can sleep and use
the transaction mutex.

## Reuse the upstream bq27xxx core

The current kernel exports exactly the interface this frontend needs:

- `struct bq27xxx_device_info`;
- `struct bq27xxx_access_methods`;
- `bq27xxx_battery_setup()`;
- `bq27xxx_battery_teardown()`;
- the shared power-supply property handling and polling logic.

The existing `bq27xxx_battery_hdq.c` is not the transport to use. It binds a
Linux 1-Wire slave, exposes only `BQ27000`, and assumes a 1-Wire master has
already produced native HDQ bytes. J81 instead needs UART pulse encoding and a
serdev child.

The bq27xxx core's BQ27541 and BQ27545 register tables share all standard
runtime addresses needed here: temperature `0x06`, voltage `0x08`, flags
`0x0a`, remaining capacity `0x10`, full capacity `0x12`, average current
`0x14`, time to empty `0x16`, cycle count `0x2a`, and state of charge `0x2c`.
They differ in exposed design-capacity behavior, so choosing one blindly is
unnecessary and would hide useful hardware evidence.

At probe, issue the sealed-access-safe TI Control() `DEVICE_TYPE` subcommand
`0x0001`, then read control bytes `0x00` and `0x01`. Documented IDs include
`0x0541` for BQ27541 and `0x0545` for BQ27545. Apple's `bq27540` compatible is
used across several device generations and should be treated as a family hint,
not proof of the precise silicon revision.

Map known returned IDs to their existing bq27xxx enum. If J81 returns a
different value, log it and fail probe with `-ENODEV`; add a core table only
after checking that device's register map. Do not silently select BQ27545.

For the first hardware build, the frontend's core access methods need byte and
word reads plus word writes for Control(). Block access and general data-flash
writes are not needed. Both candidate core tables have data-memory support set
to `NULL`, so `bq27xxx_battery_setup()` will not alter gauge flash.

## Implementation plan

### BAT-1: expose stop-bit selection

Add one kernel patch touching the existing serdev core only:

- add a one/two-stop-bit enum, controller operation, public helper, and disabled
  stub in `include/linux/serdev.h`;
- forward the helper in `drivers/tty/serdev/core.c`;
- set or clear `CSTOPB` through a copied `ktermios` in
  `drivers/tty/serdev/serdev-ttyport.c`, call `tty_set_termios()`, and verify the
  requested bit stuck.

Build this together with the battery frontend; it has no effect on existing
serdev clients until they call the new helper.

### BAT-2: add the HDQ-UART frontend

Add `drivers/power/supply/bq27xxx_battery_hdq_uart.c` and minimal Kconfig and
Makefile entries. Keep the frontend small: transport state, encode/decode,
byte/word transactions, safe device identification, and delegation to the
existing bq27xxx core.

Start with a local development compatible tied to the ADT evidence. Finalize
the TI-compatible name after `DEVICE_TYPE` is known. The first probe log must
include the numeric device type and the selected existing core enum.

Leave the Corellium charger mux, its duplicate power-supply property table,
authentication, POSM policy, and data-flash access out.

One host-side test is enough: compile the encode/decode helpers in isolation
or use KUnit to check all 256 byte values, echo alignment, and timeout-free
completion state. The test must prove `0xfe`/`0xc0` round trips LSB first.

### BAT-3: describe UART5 and the gauge

Add `serial5` to `t7001.dtsi` from the already-proven UART0/UART3 pattern, with
the J81 register, IRQ, clocks, and `ps_uart5`. Add the hardware-verified AP
GPIO34 function-1 pinctrl group. Enable UART5 in `t7001-air2.dtsi` without RTS/CTS and add the
gauge as its only serdev child.

Keep the SoC node, board node, and driver changes as reviewable kernel patches
applied by `kernel/hoolock.nix`. No initramfs userspace package is required.

### BAT-4: hardware gates

Test through the working USB network in this order:

1. boot still reaches `172.16.42.1:23`;
2. dmesg shows UART5 and the battery serdev driver probing;
3. the same `DEVICE_TYPE` is read ten times without an HDQ timeout;
4. `/sys/class/power_supply/` contains one battery;
5. `present`, `voltage_now`, `current_now`, `temp`, `capacity`, and
   `cycle_count` return plausible values for ten consecutive reads;
6. voltage and capacity are compared with iPadOS near the same time;
7. one warm reboot and one cold tethered boot reproduce the result;
8. dmesg contains no UART overrun, framing, timeout, or power-supply poll
   errors.

Stop after step 2 if identification is unstable. Capture the received UART
bytes and actual selected baud before changing protocol constants. Stop after
step 3 if the ID is unknown and research that device's exact register map.

The pass condition is a registered Linux battery with stable, plausible
readings while USB networking, RTC, backlight, and the existing UART3 work
continue to function.

## Implementation result: BAT-1/2/3 complete; BAT-4 hardware root cause fixed

BAT-1, BAT-2 and BAT-3 are implemented as four kernel patches applied from
`kernel/hoolock.nix`, following this document's plan closely:

- `kernel/patches/0003-serdev-add-stop-bit-selection.patch` (BAT-1):
  `enum serdev_stopbits { SERDEV_STOPBITS_ONE, SERDEV_STOPBITS_TWO }`, a
  `set_stopbits` controller op, and `serdev_device_set_stopbits()`, built by
  copying the existing `set_parity` three-file shape exactly (`serdev.h`'s
  enum/op/helper-plus-disabled-stub, `core.c`'s dispatch, `serdev-ttyport.c`'s
  real implementation) rather than inventing a new pattern. The ttyport
  implementation mirrors `ttyport_set_parity()` line for line, substituting
  the single `CSTOPB` flag for parity's `PARENB|PARODD|CMSPAR` group, and
  keeps the same "copy ktermios, apply, call `tty_set_termios()`, then
  compare the live result against what was requested" verify step this
  document's plan called for.
- `kernel/patches/0004-add-bq27xxx-hdq-uart-frontend.patch` (BAT-2):
  `drivers/power/supply/bq27xxx_battery_hdq_uart.c`, new
  `CONFIG_BATTERY_BQ27XXX_HDQ_UART` Kconfig/Makefile entries. Structural
  reference was the existing (wrong-transport) `bq27xxx_battery_hdq.c`'s
  `read()`/16-bit-retry shape and `bq27xxx_battery_i2c.c`'s minimal
  `di->dev`/`di->chip`/`di->name`/`di->bus.read`/`di->bus.write` field set
  before calling `bq27xxx_battery_setup()` -- confirmed by reading both, not
  guessed, that `bq27xxx_battery_setup()` already handles
  `power_supply_register()` and the initial poll scheduling internally, so
  the frontend needs nothing beyond those five fields.
  - The HDQ break is driven manually (`serdev_device_break_ctl()` assert,
    `usleep_range(250, 500)`, deassert, `usleep_range(150, 500)` recovery)
    rather than trusting a single fixed-duration break request, since
    `break_ctl()`'s own timing granularity doesn't match TI's
    microsecond-precision requirement.
  - `receive_buf()` only moves `rx_buf`/`rx_count` under `rx_lock` (a
    spinlock, since it may run in IRQ context) and signals a completion;
    every transaction (break, write, echo wait, response wait) is
    serialized under a separate sleeping `xfer_lock` mutex held by the
    caller, matching this document's own stated constraint.
  - `DEVICE_TYPE` identification (`hdq_uart_identify()`) writes Control()
    subcommand `0x0001` then reads the same register back; `0x0541`/`0x0545`
    map to the existing `BQ27541`/`BQ27545` core enums, anything else fails
    probe with `-ENODEV` rather than guessing a register table, exactly as
    specified.
- `kernel/patches/0005-t7001-add-uart5-node.patch` and
  `0006-t7001-air2-enable-uart5-battery.patch` (BAT-3): `serial5` (register
  `0x20a0d4000`, IRQ 163, clock gate context, `power-domains = <&ps_uart5>`)
  and the `uart5_pins` AP-GPIO34-function-1 pinmux group added to
  `t7001.dtsi`; `&serial5` enabled with the gauge as a real serdev child
  (`compatible = "ti,bq27540-hdq-uart"`, matching BAT-2's `of_device_id`) in
  `t7001-air2.dtsi`. Unlike `serial3` (BT-1), the gauge child ships from the
  start, since BAT-2's driver needs a real `serdev_device` to bind to and the
  serdev correction above confirms it will actually probe -- there is no
  manual-attach diagnostic step for this transport the way `btattach` was for
  Bluetooth.

**Verified, not just written:**

- The four patches apply cleanly and stack correctly on top of the existing
  BT-1 patches (0001/0002), checked by applying all six in sequence to a
  fresh checkout and diffing the result against the intended files.
- The resulting `t7001-air2.dtsi`/`t7001.dtsi` were preprocessed
  (`clang -E -nostdinc -undef -x assembler-with-cpp`) and compiled with the
  real `dtc` before ever touching Nix, same practice as BT-1's original DTS
  work -- compiles with only one pre-existing, unrelated warning
  (`simple_bus_reg` on an unrelated `/soc/bus@` node, confirmed present on
  the *unpatched* source too, not introduced here).
- A full `nix build .#packages.x86_64-linux.hoolock-kernel` (the real
  cross-compiler, not a syntax-only check) succeeded with these patches
  applied. `System.map` confirms the new symbols actually compiled in:
  `hdq_uart_probe`, `hdq_uart_driver_init`, `hdq_uart_driver`, and a real
  `__initcall__kmod_bq27xxx_battery_hdq_uart__...` entry for
  `serdev_device_set_stopbits`/`__ksymtab_serdev_device_set_stopbits`
  (correctly exported, `EXPORT_SYMBOL_GPL` took effect) and
  `ttyport_set_stopbits`.
- Decompiling the built `t7001-j81.dtb` back with `dtc` confirms
  `serial@20a0d4000`, `uart5-pins`, and the `ti,bq27540-hdq-uart` gauge child
  are genuinely present in the final device tree, not just in the source
  patches.
- `nix build .#packages.x86_64-linux.m1n1-hoolock-control` (the full
  PongoOS/m1n1/kernel/initramfs boot payload) also succeeds end to end with
  these changes in place.

### Pre-hardware transport review, 2026-09-09

A review against the exact serdev core and Corellium transport found and fixed
three issues before the first iPad boot:

- `serdev_device_write()` requires the client's `write_wakeup` callback and
  otherwise returns `-EINVAL`; the frontend now supplies
  `serdev_device_write_wakeup`.
- Arming separate echo and response waits after transmit could miss immediate
  loopback bytes or strand a gauge response delivered with the echo. The
  frontend now arms one combined receive buffer before transmit, synchronizes
  on the eight-byte command echo, collects echo and response in the same
  callback, and waits once.
- A gauge-generated pulse need not decode to the exact transmitted `0xfe` or
  `0xc0` byte. The decoder now follows Corellium's proven `>= 0xf0` threshold
  for one and treats lower samples as zero.

The same change checks break-control errors and waits for TX drain. The small
`kernel/test_hdq_uart_patch.py` guard covers the required serdev callback,
receive-before-write ordering, combined delivery, noise synchronization,
threshold decoding, and all 256 byte round trips.

A fresh full build after these fixes succeeded:

- kernel: `/nix/store/4hh8kzchb653s2kcnsdmlfvjlci53cz1-linux-aarch64-unknown-linux-gnu-7.3.0-rc1`;
- boot payload: `/nix/store/b0cdibg23h6swvanqn4wlis8gw1xrrm7-ipad-air2-m1n1-hoolock-control`;
- `m1n1-linux.bin` SHA-256:
  `2c7bc155a66947f144b85e116dd0c0b9272f5f0f8418474896134bac86a892ba`.

`System.map` contains `hdq_uart_probe`, `serdev_device_set_stopbits`, and
`ttyport_set_stopbits`; the final DTB contains `serial@20a0d4000`,
`uart5-pins`, and `ti,bq27540-hdq-uart`. The iPad did not answer the USB-shell connection during that compile review.
That historical pre-hardware state is superseded by the BAT-4 result below.

## BAT-4 result, 2026-09-10: battery works; GPIO34 must use function 1

The first hardware boot reached the iPad over the working USB network. UART5
registered at `0x20a0d4000`, IRQ 48 (AIC hwirq 163), and the serdev child
probed, but identification initially timed out. The initial DTS selected
`APPLE_PINMUX(34, 2)` because the final OIPG argument is `0x102`.

### Reference-driver result: no J81 charger mux

The real J81 ADT resolves `charger,k48`'s `function-set_charger` phandle
`0x4e` to `pmu,d2207` at I2C address `0x3c`. It is a charger-policy callback,
not a second physical charger IC.

The unstripped iOS 10.3 `s8000` kexts provide a board-generation-matched
reference:

- `AppleHDQGasGaugeControl` matches `gas-gauge,hdq`, opens the serial provider,
  flushes both FIFOs, configures 57,600 baud/8N2/no flow control, sends a 200 us
  break, and reads the encoded command bytes back before the gauge response;
- `AppleSamsungSerial` implements those operations with the same UART register
  block used by Linux. Its normal UART programming does not set internal
  loopback or a hidden single-wire mode;
- `function-battery_swi_request` is optional and absent from J81. Where present,
  it arbitrates the line between clients; it is not called around each HDQ
  transaction;
- `AppleD2207PMU` creates the charger power-source provider, but exposes no HDQ
  mux operation.

Corellium's `sn2400_charger_hdq_mux()` is real, but belongs to later hardware
with a separate SN2400/Tigris charger. Applying that design to J81 was the
wrong inference.

The reference binaries came from `userlandkernel/ios-unstripped-kexts` commit
`96ca2b7f012ab20cf0274ea593d0e9a03f576764`. They were inspected outside the
repository and were not committed. Relevant SHA-256 values are:

| Binary | SHA-256 |
| --- | --- |
| `AppleHDQGasGaugeControl` | `90575af7fe95148197e03d4c04de97eaa9bb81d2e0b40b10efc23e9644c0e31f` |
| `AppleSamsungSerial` | `61f37e69f53e51de0a195bc4463afd8a71a54fab43f0084c1fadd93ae3493648` |
| `AppleOnboardSerial` | `40c931f9203edcc9896f9ad65f20c98f482933e9b80fcab3c36a26fa2fccda91` |
| `AppleD2207PMU` | `dca7ed9726c555655ccaa05410fd4006bc9adbf9d0b9224ab17889c8f943b0e8` |

### Live isolation tests

All register diagnostics were read-only except the explicitly reversible UART
loopback, break, and GPIO peripheral-function bits. No PMU register was written.
Temporary out-of-tree modules were transferred to `/tmp` on the RAM-backed
initramfs; the loaded kernel was already tainted by those diagnostics, and a
reboot removes them.

With GPIO34 on function 2, the live state during the failed transaction was:

```
ULCON=00000007   # 8N2
UCON=00001885   # RX enabled; threshold/legacy-timeout IRQs enabled
UFCON=00000031  # FIFO enabled, RX trigger 8
UTRSTAT=00000026 # TX empty/FIFO empty/TX threshold
UFSTAT=00000000 # no RX or TX bytes queued
UBRDIV=00000019
IRQ 48 count: 0
GPIO34 raw: 0x00072641 (peripheral function 2, input enabled, line high)
```

The command left the TX FIFO, while the RX FIFO and interrupt count stayed at
zero. The old `got 0/16` log counted only bytes after the expected echo prefix
matched, so `kernel/patches/0004` now calls that value `matched`. The independent
IRQ/FIFO trace supplies the actual raw-silence evidence.

Enabling UART internal loopback for one probe produced seven IRQs and the exact
command echo:

```
HDQ transact timeout: got 8/16 bytes: fe c0 c0 c0 c0 c0 c0 c0
```

That proves Linux TX, RX, IRQ delivery, 57,600 baud/8N2 framing, serdev, and the
HDQ echo matcher all work. Holding the UART break bit with function 2 left
GPIO34 high (`0x00072641`) and generated no RX data, isolating the failure to
the UART-to-pad route.

Changing only GPIO34's two-bit peripheral field from function 2 to function 1
changed its raw register from `0x00072641` to `0x00072621`. The existing driver
then bound without any other change:

```
bq27xxx-hdq-uart serial0-0: HDQ DEVICE_TYPE = 0x0545
```

Linux selected the existing BQ27545 table and registered
`/sys/class/power_supply/bq27545-battery`. Five consecutive reads were stable,
and a full uevent read completed without a timeout:

| Property | Live result |
| --- | ---: |
| `present` | `1` |
| `health` | `Good` |
| `voltage_now` | `4239000` uV |
| `current_now` | `-316000` to `-350000` uA |
| `capacity` | `94`% |
| `temp` | `319` (31.9 C) |
| `charge_now` | `6694000` uAh |
| `charge_full` | `6801000` uAh |
| `cycle_count` | `341` |
| `time_to_empty_now` | `71700` s |

The UART IRQ count reached 647 during these reads and dmesg contained no new
HDQ, UART, or power-supply error. The live device remains on function 1 with
the battery registered; rebooting returns control to the DT.

Ten consecutive driver unbind/rebind cycles then returned
`DEVICE_TYPE = 0x0545` every time. Each cycle reported the battery present,
4.230-4.233 V and 93% capacity, with no timeout, error, failure or UART overrun
in dmesg. The final binding remained active on function 1.

### Permanent fix and remaining validation

`kernel/patches/0005-t7001-add-uart5-node.patch` now uses
`APPLE_PINMUX(34, 1)`. Patch `0008`'s context was updated so the staged touch
patch still applies after the battery correction. The host-side patch guard
checks the hardware-proven selector.

A full distributed Nix build of
`packages.x86_64-linux.m1n1-hoolock-control` succeeded after the correction.
The resulting `m1n1-linux.bin` SHA-256 is
`0681c720ec632fc6fad88f562cdc57a74ac31e2ec58e29cbd4cedec2aa7f3e27`; the
J81 DTB SHA-256 is
`dde0c168a703f036faec44e30cdb193354b440c10669c12ec6c508b880ba0005`.
Decompiling that DTB confirms `serial@20a0d4000` is enabled with its gauge
child and `uart5-pins` contains pinmux value `0x10022`, the encoded GPIO34
function-1 selection.

### First reboot attempt used the stale function-2 payload

The first reboot attempt on 2026-09-10 does not count as the permanent-fix
test. The newly booted system exposed this live DT value:

```text
/sys/firmware/devicetree/base/soc/pinctrl@20e300000/uart5-pins/pinmux
    00 02 00 22    # 0x00020022: GPIO34 function 2
```

Boot dmesg then reproduced the expected old failure:

```text
bq27xxx-hdq-uart serial0-0: HDQ transact timeout: got 0/16 bytes
bq27xxx-hdq-uart serial0-0: error -ETIMEDOUT: HDQ device identification failed
```

`/sys/class/power_supply` was empty. This proves a stale payload was uploaded;
it is not a regression in the function-1 fix. The local generic `result`
symlink was also still pointing at that old build. Re-running the current Nix
target refreshed `result` to the function-1 store output and byte-compared it
with `result-bat4-func1` successfully:

```text
result/m1n1-linux.bin  sha256 0681c720ec632fc6fad88f562cdc57a74ac31e2ec58e29cbd4cedec2aa7f3e27
result/t7001-j81.dtb   sha256 dde0c168a703f036faec44e30cdb193354b440c10669c12ec6c508b880ba0005
```

On the next reboot, verify the live pinmux bytes are `00 01 00 22` before
judging battery behavior. A successful boot must then register
`bq27545-battery` without a runtime pinmux override.

### Permanent function-1 boot passed

The corrected payload passed that test on 2026-09-10. No runtime pinmux or
driver override was applied after boot. The live DT contained:

```text
00 01 00 22    # 0x00010022: GPIO34 function 1
```

Boot dmesg showed the successful probe instead of the earlier timeout:

```text
serial serial0: tty port ttySAC2 registered
bq27xxx-hdq-uart serial0-0: HDQ DEVICE_TYPE = 0x0545
```

`/sys/class/power_supply/bq27545-battery` was present automatically. At about
two minutes uptime its standard power-supply properties reported:

```text
status=Discharging  health=Good  present=1
capacity=82%        voltage=4.104 V
current=-0.625 A    temperature=32.1 C
cycle_count=341     charge_now=5.872 Ah
charge_full=6.817 Ah
```

This closes the permanent-DT portion of BAT-4: the function-1 result is now
proven across a reboot, not only through the live A/B override.

The OIPG record still proves the resource is AP GPIO34 and that
`function-battery_swi` and UART5 `function-tx` are identical. Its flags word
`0x102` does not directly encode the Apple GPIO peripheral selector. This live
A/B result supersedes the earlier low-byte inference and should be used when
decoding other old-A-series OIPG records.

Remaining BAT-4 gates are comparison with iPadOS and warm/cold reboot
reproduction. No charger or PMU mux work belongs on that path. Charging policy
remains a separate D2207/`charger,k48` project after read-only battery reporting
is locked down.

## Sources

- [Real J81 evidence and execution log](../docs/plans/2026-09-08-j81-bluetooth-battery-adt.md)
- [Hoolock Linux source pinned by this repository](https://github.com/HoolockLinux/linux/tree/6831bc701a6ce059e71e5aaa9488c9195bea6927)
- [Linux bq27xxx core interface](https://github.com/torvalds/linux/blob/master/include/linux/power/bq27xxx_battery.h)
- [Linux bq27xxx core](https://github.com/torvalds/linux/blob/master/drivers/power/supply/bq27xxx_battery.c)
- [Linux tty-backed serdev registration](https://github.com/torvalds/linux/blob/master/drivers/tty/tty_port.c)
- [Corellium Apple HDQ-UART transport](https://github.com/corellium/linux-sandcastle/blob/sandcastle-5.4/drivers/power/supply/bq27545-battery-hdquart.c)
- [Corellium SN2400 charger/mux implementation (later hardware)](https://github.com/corellium/linux-sandcastle/blob/sandcastle-5.4/drivers/power/supply/sn2400-charger.c)
- [Unstripped iOS 10.3 s8000 AppleHDQGasGaugeControl kext](https://github.com/userlandkernel/ios-unstripped-kexts/tree/master/kexts/10.3/s8000/AppleHDQGasGaugeControl.kext)
- [Unstripped iOS 10.3 s8000 AppleSamsungSerial kext](https://github.com/userlandkernel/ios-unstripped-kexts/tree/master/kexts/10.3/s8000/AppleSamsungSerial.kext)
- [Unstripped iOS 10.3 s8000 AppleOnboardSerial kext](https://github.com/userlandkernel/ios-unstripped-kexts/tree/master/kexts/10.3/s8000/AppleOnboardSerial.kext)
- [Unstripped iOS 10.3 s8000 AppleD2207PMU kext](https://github.com/userlandkernel/ios-unstripped-kexts/tree/master/kexts/10.3/s8000/AppleD2207PMU.kext)
- [TI bq27545-G1 datasheet, including HDQ timing and DEVICE_TYPE](https://www.ti.com/lit/ds/symlink/bq27545-g1.pdf)
- [TI-hosted bq27541-V200 datasheet](https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/196/bq27541_5F00_V200_5F00_DS.pdf)
- [2019 Linux serdev stop-bit proposal](https://marc.info/?l=linux-serial&m=155651925923098)
- [Public J82 ADT cross-check](https://gist.github.com/zhuowei/715ded46d018cc7d05265e58d6a65083)
