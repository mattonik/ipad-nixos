# J81 Bluetooth, battery and ADT development plan

Status: BT-1's UART3 hardware description is confirmed correct on real J81
hardware 2026-09-08 (`ttySAC1` registered at `0x20a0cc000` with RTS/CTS
active) -- see "BT-1 result" below. `hci0` still needs `btattach` tooling
added to the initramfs, since the parent UART driver has no serdev support
(a real, hardware-confirmed correction to this plan's original approach).

Target: iPad Air 2 Wi-Fi, J81/J81AP, A8X/T7001, A1566

Kernel baseline: Hoolock Linux 7.3-rc1 at `6831bc701a6ce059e71e5aaa9488c9195bea6927`

## Outcome

Bring up two independent peripherals on the working USB-networked Linux
baseline:

1. Broadcom Bluetooth over UART3, first as a transport-only probe and then
   with firmware, wake and power control.
2. The TI battery fuel gauge over Apple's UART5/HDQ encoding, exposed through
   Linux's existing `bq27xxx` power-supply core.

The first required artifact is a private raw Apple Device Tree (ADT) dump from
this exact J81. J82 is a useful sibling reference, but its GPIO and calibration
data are not authority for J81.

Charging control is outside this milestone. The battery work is read-only fuel
gauge support: presence, voltage, current, temperature, capacity and cycle
count.

## State verified on the connected J81

On 2026-09-08 the new Hoolock payload booted Linux 7.3-rc1 and became fully
accessible through CDC-ECM at `172.16.42.1`. The host saw 0% packet loss and a
real telnet shell. This removes USB from the Bluetooth/battery critical path.

The live shell established the exact starting point:

| Check | Live result | Meaning |
| --- | --- | --- |
| Kernel | `Linux 7.3.0-rc1`, Hoolock build | Use this pinned tree; no kernel-version jump is needed. |
| FDT identity | `Apple iPad Air 2 (Wi-Fi)`, `apple,j81`, `apple,t7001` | Correct board DTB is active. |
| Serial nodes | only `serial@20a0c0000` / `ttySAC0` | UART3 and UART5 are absent from the current FDT. |
| Bluetooth | core, H4 and Broadcom HCI UART protocols initialize; `/sys/class/bluetooth` is empty | Kernel driver support is built; there is no described controller to probe. |
| Battery | `/sys/class/power_supply` is empty | No gauge node or transport is present. |
| Active FDT | 29,812 bytes at `/sys/firmware/fdt` | Saved privately as `artifacts/adt/20260908T073547Z-j81-live-fdt.dtb`. |

The active FDT contains the device serial, so it is intentionally ignored by
Git. Its SHA-256 is
`dab4ab1dd50eb99a7926f52b1d21e214114cae8ec4fbd7167ccd86804f436b4c`.
It is a useful before-state, but it is m1n1's Linux FDT, not Apple's complete
ADT. Properties omitted during translation cannot be recovered from it.

## Evidence already available

Hoolock's T7001 DTS already has the required UART power domains through
`ps_uart3` and `ps_uart5`. Its UART0 node supplies the exact Linux-side
template: `apple,s5l-uart`, a 16 KiB register window, AIC interrupt, two
temporary 24 MHz reference clocks, and the matching PMGR power domain.

The public J82 ADT reports:

| Peripheral | Bus | J82 resources |
| --- | --- | --- |
| Bluetooth | UART3 | base `0x20a0cc000`, IRQ 161, clock gate `0x53`, TX AP GPIO14 alt2, RTS AP GPIO32 alt2 |
| Bluetooth child | `bluetooth,n88` | 3,000,000 baud, host wake AP GPIO164, PMU power-enable GPIO2, Apple vendor ID `0x05ac`, product ID `0x12a0` |
| Battery | UART5 | base `0x20a0d4000`, IRQ 163, clock gate `0x55`, no flow control |
| Fuel-gauge child | `gas-gauge,bq27540`, `gas-gauge,hdq` | battery SWI AP GPIO34 alt2 |

The Hoolock defconfig already enables `BT`, `BT_BCM`, `BT_HCIUART`,
`BT_HCIUART_BCM`, `SERIAL_SAMSUNG`, `SERIAL_DEV_BUS`, `POWER_SUPPLY`,
`BATTERY_BQ27XXX`, `W1` and `W1_MASTER_UART`. The last item is not the battery
solution: Linux's generic 1-Wire UART master generates standard 1-Wire slots,
while this Apple design uses TI HDQ represented as encoded UART bytes.

## Safe J81 ADT capture

`boot/dump_adt.py` implements the same PongoOS control requests as PongoOS's
own `issue_cmd.py` and `fetch_stdout.py`: it sends `dt\n` with request `0x21/3`
and drains the console ring with request `0xa1/1`.

The tool deliberately:

- writes under ignored `artifacts/adt/` by default;
- refuses a non-ignored output path inside the repository;
- creates captures mode `0600` and never prints their content;
- rejects a capture missing J81, T7001, A1566 and device-tree markers;
- saves a truncated or wrong-board result only as `.partial`;
- refuses to overwrite an earlier capture;
- stops after a bounded timeout or 8 MiB instead of looping forever.

The currently connected iPad is running Linux, so it is not a PongoOS
`05ac:4141` device and cannot expose the raw ADT without a reboot. On the next
planned boot session:

1. Put the iPad in DFU and launch the same Hoolock PongoOS payload used by the
   successful boot.
2. Stop at the PongoOS shell. Do not upload m1n1 yet.
3. In a second host terminal run:

   ```sh
   nix develop -c python3 boot/dump_adt.py
   ```

4. Record only the resulting byte count and SHA-256 in the repository.
5. Continue the normal boot with `boot/load_m1n1.py`.

The default minimum is 200,000 bytes. The earlier live experiment produced
317,946 bytes, and public J82 dumps are of the same order, so a much smaller
file is probably a console-ring truncation.

Before using the capture, inspect its relevant nodes locally:

```sh
ADT=artifacts/adt/YYYYMMDDTHHMMSSZ-j81.adt
rg -n -C 35 '^ +name +uart3$|^ +name +bluetooth$' "$ADT"
rg -n -C 35 '^ +name +uart5$|^ +name +gas-gauge$' "$ADT"
rg -n 'function-(tx|rts|bt_wake|power_enable|battery_swi)|transport-speed|compatible' "$ADT"
```

Capture these facts in a sanitized evidence note: node paths, registers,
interrupts, clock gates, GPIO numbers/flags, compatible strings, speed,
vendor/product IDs, and property names. Do not copy serial numbers, MAC
addresses, NVRAM, nonces, keys, or calibration blobs into Git. SoMainline's
collection also requires those values to be censored before sharing.

ADT gate: UART3 and UART5 values must be taken from the private J81 capture.
If they match J82, record the match and proceed. Any difference overrides this
plan's J82-derived numbers.

## J81 ADT evidence (captured 2026-09-08)

Real J81 ADT captured via `boot/dump_adt.py` during a PongoOS stop, before
loading m1n1: 357,402 bytes, validated as this exact board (target-type J81,
platform-name t7001, regulatory-model A1566). Stored privately at
`artifacts/adt/20260908T082112Z-j81.adt` (git-ignored, `sha256=cf743765...`).
Inspected with the `rg` commands above; sensitive fields present in the
capture (Bluetooth TX/RX calibration arrays, `local-mac-address`, and the
POSM threshold/VAC-level battery calibration arrays) were read but are
intentionally **not** reproduced below.

**UART3 (Bluetooth transport)** -- `compatible = "uart-1,samsung"`,
`interrupts = 0xa1` (161), `clock-gates = 0x53` (83), register base low bits
`0x0a0cc000`. `function-tx`/`function-rts` are present (non-empty
Apple GPIO-function descriptors; exact AP GPIO pin numbers not decoded from
the binary encoding in this pass). Every one of these values is an **exact
match** to the J82 sibling reference this plan was drafted against.

**Bluetooth child node** -- `compatible = "bluetooth,n88"`,
`device_type = "bluetooth"`, `transport-speed = 0x002dc6c0`
(3,000,000 -- exact match to J82's 3 Mbaud), `transport-encoding = 0x3`,
`vendor-id = 0x05ac`, `product-id = 0x12a0` (both exact matches to J82),
`supported-profiles = 0x2ffb`, `coex = 0x2`. `function-bt_wake` and
`function-power_enable` are present and non-empty (host-wake/PMU
power-enable wiring confirmed present; exact GPIO numbers not decoded here).

**UART5 (battery transport)** -- `compatible = "uart-1,samsung"`,
`interrupts = 0xa3` (163), `clock-gates = 0x55` (85), register base low bits
`0x0a0d4000`, `no-flow-control` present. All exact matches to J82.
`function-tx` is present.

**Gas-gauge child node** -- `compatible = "gas-gauge,bq27540"`,
`"gas-gauge,hdq"` (exact match to J82), `device_type = "gas-gauge"`,
`battery-id-block = 0x1`, `update-sample-config = 0x10`.
`function-battery_swi` is present -- and its raw OIPG-encoded payload is
**byte-identical** to UART5's own `function-tx` payload. That's a real,
new-to-this-capture confirmation (not visible in the J82-only reference) of
the plan's HDQ-over-UART model: the battery's single-wire HDQ signal rides
the same physical pin as UART5's transmit line, rather than a separate GPIO.

**ADT gate result**: every structural value checked above (register base,
IRQ, clock gate, compatible strings, transport speed, vendor/product ID)
matches the J82 sibling reference exactly on real J81 hardware. Per this
plan's own rule, that clears the gate to proceed using the existing
J82-derived numbers in the BT-1/BAT-2 sections below with confidence, now
backed by this board's own data rather than sibling inference alone.

## Bluetooth implementation

### BT-1: describe UART3 and prove the transport

Add one kernel patch and apply it from `kernel/hoolock.nix` so the pinned source
remains reproducible.

In `t7001.dtsi`, add `serial3` following `serial0`:

- `reg = <0x2 0x0a0cc000 0 0x4000>` after J81 confirmation;
- AIC IRQ 161, level high;
- the same temporary `clkref` pair and clock names as UART0;
- `power-domains = <&ps_uart3>`;
- disabled at SoC level.

In the J81 board description, add the J81-confirmed TX/RTS pinmux, enable
UART3 with RTS/CTS, and add a serdev child with:

```dts
compatible = "brcm,bcm43540-bt";
max-speed = <3000000>;
```

Add `bluetooth0 = &bluetooth;` to `/aliases`. Hoolock m1n1 already copies
`/chosen/mac-address-bluetooth0` into `local-bd-address` for that alias and
swaps its byte order as the Linux binding expects.

Leave host wake and shutdown out of the first transport patch. Both are
optional to `hci_bcm`; this tests whether iBoot/m1n1 retained radio power and
avoids inventing an IRQ polarity or D2207 PMU GPIO register map. The standard
Broadcom binding allows exactly this incremental description.

Build and boot:

```sh
nix build .#packages.x86_64-linux.m1n1-hoolock-control \
  -o result-hoolock-control -L
```

From the USB shell, capture:

```sh
dmesg | grep -Ei '20a0cc000|ttySAC|bluetooth|hci|bcm'
find /sys/class/bluetooth -maxdepth 1 -type l -print
for f in /sys/class/bluetooth/hci0/address /sys/class/bluetooth/hci0/name; do
    [ -r "$f" ] && { echo "--- $f"; cat "$f"; }
done
```

BT-1 passes when UART3 probes and `hci0` registers with a non-placeholder
controller address. A firmware error after HCI registration is progress and
must be recorded verbatim; it gives the exact `.hcd` filename to supply.

### BT-1 result, 2026-09-08: UART3 probes correctly on real hardware; the serdev-child approach needed a real correction first

**Two corrections to this section's original description, found before
writing any DTS, by reading the actual driver source rather than assuming
the binding style this section describes would just work:**

1. **Pin numbers were independently decoded, not copied from J82.** The
   real J81 ADT's `function-tx`/`function-rts` properties on UART3 (and
   `function-battery_swi` on the gas-gauge, `function-bt_wake`/
   `function-power_enable` on the bluetooth child) are 16-byte Apple
   "OIPG" GPIO-function descriptors: 4 little-endian `u32` words --
   resource-type tag, the `"OIPG"` magic, a resource number, and flags.
   Decoding word 3 (the resource number) against every property gave:
   UART3 TX = AP GPIO 14, UART3 RTS = AP GPIO 32, gas-gauge
   `battery_swi` = AP GPIO 34 (identical encoding to UART5's own
   `function-tx` -- confirming HDQ rides UART5's TX pin), Bluetooth
   `bt_wake` = AP GPIO 164. The `power_enable` property carries a
   *different* resource-type tag (0x4e instead of 0x1f used by all the
   AP-GPIO properties above), consistent with it being a *PMU* GPIO (2)
   rather than an AP GPIO -- exactly matching this document's own
   "PMU power-enable GPIO2" description, decoded independently from a
   different, more structural signal in the data. Every one of these
   independently-decoded numbers matches this section's original
   J82-sourced numbers exactly, which is real confirmatory evidence for
   both the decode method and J81/J82 pin-compatibility -- not just an
   assumption carried over from the sibling board. Alt-function index 2
   (used in the `APPLE_PINMUX(pin, 2)` entries) is not encoded in the ADT
   itself; taken from this document's existing "alt2" annotation.

2. **The serdev child node in this section's original description would
   never have probed.** `apple,s5l-uart`'s actual driver
   (`drivers/tty/serial/samsung_tty.c`) never calls
   `serdev_tty_port_register()` and never registers as a
   `serdev_controller` -- confirmed by grepping the real driver source,
   not assumed. A `bluetooth { compatible = "brcm,bcm43540-bt"; ...};`
   child of `&serial3` requires the parent to be a working serdev bus;
   without that, the child node is simply inert data in the tree --
   `hci_bcm` never gets a chance to bind, no matter how correct the
   register/pinmux description is. **Implemented without the child node
   and without the `bluetooth0` alias** (which would otherwise be an
   unresolved-label compile error with no `bluetooth:` node to point at).
   `t7001.dtsi` gained `serial3` (register, IRQ 161, clocks,
   `power-domains = <&ps_uart3>`, disabled by default) plus a new
   `uart3_pins` pinmux group; `t7001-air2.dtsi` enables `&serial3` with
   `pinctrl-0 = <&uart3_pins>` and `uart-has-rtscts`. Both as real `.patch`
   files (`kernel/patches/0001-t7001-add-uart3-node.patch`,
   `0002-t7001-air2-enable-uart3.patch`, applied via `patch -p1` from
   `kernel/hoolock.nix`) rather than more `sed`, since the insertions are
   multi-line and a diff is far more reviewable than a sed one-liner here.
   Test-compiled locally (`clang -E` then `dtc`) before ever touching Nix,
   confirming clean compilation and correct pinmux/phandle encoding in the
   resulting DTB.

**Hardware result**: booted on the iPad, checked via `boot/ipad_console.py`'s
new UART3/Bluetooth dmesg and tty-device actions.
`[ 0.123640] 20a0cc000.serial: ttySAC1 MMIO32:0x000000020a0cc000 (irq = 47,
base_baud = 0) is a APPLE S5L` -- a second, distinct serial device
registered at exactly UART3's address, alongside the existing `ttySAC0`
console. `/proc/tty/driver/s3c2410_serial` confirms it:
`1: uart:APPLE S5L MMIO32:0x000000020a0cc000 irq:47 tx:0 rx:0
CTS|DSR|CD` -- flow-control flags active, confirming `uart-has-rtscts` was
read and applied. This is the "UART3 probes" half of BT-1's pass
criterion, hardware-confirmed. (Linux's own IRQ 47 here is a virtual IRQ
number the kernel's IRQ domain allocated when mapping AIC's hardware
IRQ 161 -- not expected to match 161 directly, and it doesn't need to.)

**The `hci0` half of BT-1 is not yet reachable, for a reason beyond the
serdev gap above**: the debug initramfs (`debug_initrd.img`) has *no*
Bluetooth userspace tooling at all -- no `btattach`, `hciattach`,
`bluetoothctl`, or BusyBox applet (checked the extracted image directly).
Without kernel serdev auto-probe (impossible per the correction above) or
a userspace tool to manually attach the HCI UART line discipline over
`/dev/ttySAC1`, nothing can drive this transport yet, regardless of how
correct the DTS description is.

### `btattach` built and bundled, 2026-09-08: hardware attach attempt still pending

BlueZ's own `./configure` unconditionally requires glib and dbus
(`configure.ac`'s `PKG_CHECK_MODULES(GLIB, ...)` / `(DBUS, ...)` have no
enabling `if` guard) even though `btattach` itself needs neither --
building the real package to get one tool pulled in that whole chain and
was confirmed painfully slow in practice (killed after 24+ minutes with
no visibility into what it was even doing). Instead,
[`boot/btattach.nix`](../../boot/btattach.nix) compiles just
`tools/btattach.c` plus the exact `src/shared/*.c` helper files its own
`#include` list touches (`util.c`, `queue.c`, `hci.c`, `mainloop.c`,
`mainloop-notify.c`, `io-mainloop.c`, `timeout-mainloop.c`) directly with
`$CC`, bypassing autotools/configure entirely -- found iteratively against
real linker errors (a first attempt with the *full* `shared_sources` list
`libshared-mainloop.la` bundles for every BlueZ tool pulled in unrelated
LE-GATT/audio-profile code and its own further dependencies). Statically
linked (`-static`): the debug initramfs's musl build is a separate,
externally-sourced artifact, not guaranteed ABI-compatible with this
project's own Nix-built musl. Confirmed via `file`: `ELF 64-bit ... ARM
aarch64 ..., statically linked`, 227 KiB.

Wired into `flake.nix` as `btattachPkg` (built with `pkgsCrossMusl`, same
cross instantiation the rest of the initramfs userspace already uses) and
bundled into `m1n1-hoolock-control`'s initramfs at `usr/bin/btattach`
alongside the image's other standalone tools (`usr/bin/evtest`,
`usr/bin/fftest`), via the same concatenated-newc-cpio-archive overlay
technique already used for the `ecm.usb0` deviceinfo override just above
it. Verified the append actually worked -- and worth recording *how*,
since a naive check is misleading: ordinary `cpio -it`/`cpio -id` (both
macOS's `bsdcpio` and a real GNU `cpio`) stop reading at the first
`TRAILER!!!` record, so a plain listing of the built `initramfs.gz` only
ever shows the *original* debug_initrd.img content, never the overlay --
this is expected (only the Linux kernel's own initramfs unpacker
continues past a `TRAILER!!!` into a concatenated second archive) but
looks exactly like a silent failure if you don't know that going in. Confirmed
correctly appended by parsing the first archive's cpio headers directly
(namesize/filesize fields, 4-byte alignment padding) to find the real byte
offset where the second archive begins, then listing/extracting *that*
segment on its own: both `etc/deviceinfo` (with the `ecm.usb0` override
line intact) and `usr/bin/btattach` (matching, `file`-confirmed static
ELF) are present.

Console tool gained two matching actions
([`boot/ipad_console.py`](../../boot/ipad_console.py)): "Bluetooth: hci0
status" (`ls /sys/class/bluetooth`) and "Bluetooth: attach HCI UART
(btattach)", which backgrounds `btattach -B /dev/ttySAC1 -P bcm -S
3000000` (device and baud rate both from this document's own ADT
evidence above -- `btattach` has no daemonize flag, so it has to be
launched with `&`/`disown` rather than run to completion like the
console's other actions), waits briefly, then prints `hci0` status,
`btattach`'s own log, and a focused `dmesg` filter.

**Not yet done**: actually running this against real hardware. The
build/bundle is verified at the Nix level (binary present, statically
linked, deviceinfo override intact); whether `hci_bcm` actually binds and
registers `hci0` -- or fails with a firmware-loading error, which is
itself progress and would give the exact `.hcd` filename BT-2 needs -- is
still an open, hardware-only question.

### Hardware attach attempt, 2026-09-08: `hci0` registers; the chip itself never answers

Ran `m1n1-hoolock-control` with `btattach` bundled, then used the
console tool's new "Bluetooth: attach HCI UART" action against the live
device. `hci_bcm` bound immediately:

```
lrwxrwxrwx  hci0 -> .../20a0cc000.serial:0/20a0cc000.serial:0.0/tty/ttySAC1/hci0
```

This is the "`hci0` half" of BT-1's original pass criterion, now also
hardware-confirmed -- UART3's register/pinmux/clock description, the
`hci_bcm` UART-transport driver, and the manual `btattach` line-discipline
attach all work correctly together. But every actual command to the chip
timed out:

```
[ 38.815423] Bluetooth: hci0: command 0xfc18 tx timeout
[ 38.815627] Bluetooth: hci0: BCM: failed to write update baudrate (-110)
[ 40.863451] Bluetooth: hci0: command 0xfc18 tx timeout
[ 40.863667] Bluetooth: hci0: BCM: Reset failed (-110)
```

`-110` is `-ETIMEDOUT`: the BCM43540 never sent a single byte back over
UART3, not even a response to a plain HCI Reset -- this fails *before*
firmware is even relevant, so it isn't BT-2's territory yet. The most
likely explanation, and the one this document's own "Bluetooth
implementation" section already anticipated: the chip has no power.
`function-power_enable` (independently decoded above as PMU GPIO2, tag
`0x4e`) is exactly the kind of line real BCM4354x designs require
asserted before the chip's UART interface does anything at all, and BT-3
("add wake and power control only when required") was deliberately left
unimplemented -- this hardware result is the "when required" signal.

**Deliberately not proceeding past this point without a separate
go-ahead.** This document's own "Stop conditions" say: "Do not add D2207
PMU GPIO control until its register layout and polarity are measured" --
that measurement (register layout, polarity, and safe sequencing for a
PMU-controlled supply rail) is real new hardware-facing work, not the
"bundle an already-working driver" class of task this initramfs/btattach
change was. Flagging back rather than continuing into it.

### BT-2: supply exact local firmware

Extract the requested Broadcom patchram file from the matching local IPSW or
device filesystem. Keep it under ignored `firmware/`, add it to the test
initramfs through an impure local input, and do not commit the blob.

BT-2 passes when the firmware loads, the controller powers up, and a scan sees
at least one known nearby device. Add BlueZ tools to the debug image only when
the sysfs/HCI gate passes; the kernel log and sysfs are enough for BT-1.

### BT-3: add wake and power control only when required

If UART3 probes but the controller never replies, first confirm pinmux and
traffic. Then determine whether PMU GPIO2 is low. Do not copy Corellium's D2333
PMU GPIO offsets onto this D2207/Arabela PMIC.

Once D2207 GPIO access is evidence-backed:

- describe PMU GPIO2 as `shutdown-gpios` with confirmed polarity;
- describe AP GPIO164 as `interrupts` plus
  `interrupt-names = "host-wakeup"`, using the observed polarity/trigger;
- add `device-wakeup-gpios` only if the J81 ADT exposes a distinct BT_WAKE
  output from the AP;
- extend m1n1's Bluetooth ADT path only for calibration properties the running
  controller proves it needs. Current m1n1 looks at `/arm-io/bluetooth`, while
  the J82 child is `/arm-io/uart3/bluetooth`.

BT completion criteria: cold-boot repeatability, firmware loaded, controller
address stable, scan works, and three minutes of connect/disconnect activity
produces no UART overruns or HCI timeouts.

## Battery implementation

### BAT-1: add an HDQ-over-serdev frontend

Add one focused driver,
`drivers/power/supply/bq27xxx_battery_hdquart.c`, plus its Makefile/Kconfig
entries. Reuse `struct bq27xxx_device_info`,
`struct bq27xxx_access_methods`, `bq27xxx_battery_setup()` and
`bq27xxx_battery_teardown()` from the existing core. Do not copy Corellium's
second power-supply implementation.

The transport should retain the proven Corellium wire behavior:

- serdev at 57,600 baud, no parity, two stop bits, no flow control;
- a break of 250-500 microseconds followed by 150-500 microseconds idle;
- each HDQ bit encoded least-significant-bit first as `0xfe` for one and
  `0xc0` for zero;
- set/clear the HDQ command's bit 7 for writes/reads and expose the core's
  single-byte and stable word callbacks;
- discard received bytes until the transmitted eight-byte command echo
  matches;
- one mutex-protected transaction at a time;
- 500 ms bounded completion timeout;
- stable 16-bit reads using high/low/high and retry if the high byte changes.

The first probe transaction must issue TI Control() `DEVICE_TYPE` and log only
the numeric response. The ADT string says `bq27540`, while upstream's enum has
`BQ27541` and `BQ27545` but no exact `BQ27540`. Map to a core layout only after
the returned ID and register behavior are checked against the TI documentation.
Unknown IDs must fail with `-ENODEV`; they must not silently select BQ27545.

Use a provisional, narrow development compatible such as
`ti,bq27540-hdq-uart`, with a matching YAML binding. Confirm or rename it from
the hardware ID before treating the patch as upstreamable.

One hardware-independent kernel test is sufficient: KUnit or a tiny extracted
test for byte encode/decode and echo alignment. The real acceptance test is on
the gauge.

### BAT-2: describe UART5 and the gauge

In `t7001.dtsi`, add `serial5` from the UART0 template:

- `reg = <0x2 0x0a0d4000 0 0x4000>` after J81 confirmation;
- AIC IRQ 163, level high;
- the same reference clocks;
- `power-domains = <&ps_uart5>`;
- disabled at SoC level.

In J81, add the confirmed AP GPIO34 alt2 pinmux, enable UART5 without flow
control, and add the gauge as its serdev child. Keep this patch separate from
Bluetooth so either subsystem can be reverted independently.

BAT-2 passes first when `DEVICE_TYPE` is stable across ten reads. After mapping
the correct bq27xxx core layout, these files must report plausible values:

```sh
find /sys/class/power_supply -maxdepth 2 -type f -print
for f in /sys/class/power_supply/battery/{present,voltage_now,current_now,temp,capacity,cycle_count}; do
    [ -r "$f" ] && { echo "--- $f"; cat "$f"; }
done
```

Compare voltage, temperature and charge percentage with an iPadOS reading at
approximately the same time. Exercise ten consecutive reads and one cold boot.
An absent/unresponsive gauge must time out without delaying boot by more than
the bounded probe transaction.

BAT completion criteria: `POWER_SUPPLY_TYPE_BATTERY` registers, readings are
stable and plausible, signed current direction is correct, and no writes to
gauge data flash or charging controls occur.

## Delivery order and commits

Implement and hardware-test one gate at a time:

1. `tools: add private J81 ADT capture` — capture tool, ignore rule and its
   hardware-free test. **Implemented by this plan's commit.**
2. `docs: record sanitized J81 UART3/UART5 ADT evidence` — after the next
   PongoOS stop.
3. `feat: describe J81 UART3 Bluetooth transport` — DT only.
4. `feat: supply J81 Bluetooth firmware locally` — build plumbing only; no
   firmware committed.
5. `feat: add bq27xxx HDQ UART transport` — driver and binding.
6. `feat: describe J81 UART5 battery gauge` — DT only.
7. Add Bluetooth wake/power or m1n1 calibration patches only if a recorded
   failure demands them.

For every hardware commit, preserve the current working USB network, RTC and
backlight baseline. Record the Git commit, payload SHA-256, full subsystem
`dmesg`, relevant sysfs output, pass/fail gate and next single experiment in
`docs/project-status.md`.

## Stop conditions

- Do not write a J81 GPIO or peripheral resource from J82 alone.
- Do not commit raw ADT/FDT, firmware, MAC addresses, serials or calibration.
- Do not add D2207 PMU GPIO control until its register layout and polarity are
  measured.
- Do not select a bq27xxx chip layout from the ADT string alone.
- Do not combine Bluetooth and battery into one kernel patch or hardware run
  until each independent transport gate passes.

## Primary references

- [PongoOS command sender](https://github.com/checkra1n/PongoOS/blob/master/scripts/issue_cmd.py)
- [PongoOS stdout reader](https://github.com/checkra1n/PongoOS/blob/master/scripts/fetch_stdout.py)
- [SoMainline ADT collection instructions](https://github.com/SoMainline/adt_collection)
- [SoMainline J82 ADT](https://github.com/SoMainline/adt_collection/blob/master/a8/J82.adt)
- [Hoolock Linux T7001 tree](https://github.com/HoolockLinux/linux/tree/6831bc701a6ce059e71e5aaa9488c9195bea6927)
- [Linux Broadcom Bluetooth binding](https://github.com/torvalds/linux/blob/master/Documentation/devicetree/bindings/net/bluetooth/brcm%2Cbluetooth.yaml)
- [Linux Broadcom HCI UART driver](https://github.com/torvalds/linux/blob/master/drivers/bluetooth/hci_bcm.c)
- [Linux bq27xxx core interface](https://github.com/torvalds/linux/blob/master/include/linux/power/bq27xxx_battery.h)
- [Linux bq27xxx HDQ frontend](https://github.com/torvalds/linux/blob/master/drivers/power/supply/bq27xxx_battery_hdq.c)
- [Corellium's Apple HDQ-UART implementation](https://github.com/corellium/linux-sandcastle/blob/sandcastle-5.4/drivers/power/supply/bq27545-battery-hdquart.c)
- [TI bq27541 HDQ datasheet](https://www.ti.com/lit/ds/symlink/bq27541.pdf)
