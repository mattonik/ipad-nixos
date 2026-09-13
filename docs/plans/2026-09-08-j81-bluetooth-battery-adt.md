# J81 Bluetooth, battery and ADT development plan

Status: UART3 is hardware-confirmed and the bundled `btattach` reaches `hci0`,
although the unpowered radio does not answer HCI commands. The battery path is
also hardware-confirmed: with AP GPIO34 on peripheral function 1, UART5/HDQ
identifies the BQ27545 and exposes stable Linux power-supply readings. The
permanent-DT reboot gate has passed; warm/cold reproduction remains. See
[`research/j81-battery-hdq.md`](../../research/j81-battery-hdq.md).

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
| Fuel-gauge child | `gas-gauge,bq27540`, `gas-gauge,hdq` | battery SWI AP GPIO34; J81 hardware requires peripheral function 1 |

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

### BT-1 result, 2026-09-08: UART3 probes correctly on real hardware

**The J81 pin decode below remains correct. A later audit corrected the
serdev conclusion that accompanied it.**

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
   J82-sourced numbers exactly, which confirms the resource-number decode and
   J81/J82 pin compatibility. Later BAT-4 hardware A/B testing proved the
   OIPG flags word is not a direct Apple pinmux selector: GPIO34 carries
   `0x102`, but its working UART5/HDQ route is peripheral function 1. UART3's
   function-2 setting remains valid because UART3 itself probed on hardware.

2. **Correction, 2026-09-08: Samsung UART does get a serdev controller.**
   `drivers/tty/serial/samsung_tty.c` calls `uart_add_one_port()`. The common
   `drivers/tty/serial/serial_core.c` path then calls
   `tty_port_register_device_attr_serdev()`, which registers a serdev
   controller whenever the UART DT node has a child. The earlier audit stopped
   one call too early in the stack. The built config already enables
   `CONFIG_SERIAL_DEV_BUS` and `CONFIG_SERIAL_DEV_CTRL_TTYPORT`, so a
   `brcm,bcm43540-bt` child can bind to `hci_bcm`; the same mechanism can bind
   the battery frontend on UART5. The BT-1 patch still intentionally shipped
   without the child node so the raw UART could be validated independently
   with `btattach`.

   The implemented DT change therefore remains useful:
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

**At this point in the work, the `hci0` half of BT-1 was not yet reachable**:
the debug initramfs (`debug_initrd.img`) had *no*
Bluetooth userspace tooling at all -- no `btattach`, `hciattach`,
`bluetoothctl`, or BusyBox applet (checked the extracted image directly).
Because the transport-only DT patch deliberately had no serdev child, a
userspace tool was needed to attach the HCI UART line discipline over
`/dev/ttySAC1` for that image. The later bundled `btattach` test reached
`hci0` and established that the remaining failure is radio power control.

### `btattach` built and bundled, 2026-09-08: `hci0` reached on hardware

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

The hardware attach attempt above supplied the "only when required" trigger
this section was waiting on. No PMU register has been written yet and no
Bluetooth power DTS has changed.

#### BT-3 register and polarity result, 2026-09-10

The register is now identified without a write. Disassembly of the unstripped
iOS 10.3 s8000 `AppleD2207PMU` driver, independently checked against a T8010
build of the same driver, gives the complete GPIO map:

- PMU GPIO indices 0 through 16 use configuration register
  `0x03e0 + 3 * index`; GPIO2 is therefore `0x03e6`.
- GPIO indices 17 through 20 use registers `0x0411` through `0x0414`.
- GPIO data is read at `0x0063 + index / 8`, using bit
  `1 << (index % 8)`; GPIO2 is bit 2 of `0x0063`.
- For this descriptor, function value 0 produces GPIO2 configuration `0x00`;
  value 1 produces `0x02` and drives the data bit high.

The separate Apple Bluetooth driver removes the last polarity ambiguity. Its
`BTReset::start()` obtains `function-bt_reset`, `function-bt_wake`, and
`function-power_enable`, then calls `function-power_enable` with value 1. Its
power character-device callbacks use value 0 for the power-off operation and
value 1 for power-on. The J81 descriptor `[2, 0x101]` therefore names PMU
GPIO2 as an active-high radio power enable.

The live Linux session matched that decode exactly:

```text
D2207 0x03e6 = 0x00       GPIO2 configured low
D2207 0x0063 = 0x20       GPIO2 data bit 2 is clear
/sys/class/bluetooth      empty
```

This explains the earlier HCI timeouts: UART3 and the HCI line discipline are
working, but the radio is electrically off. It also supersedes the historical
Stage A conclusion below that no GPIO register had been identified.

The next hardware test is one bounded A/B test, with the user present:

1. Read and save `0x03e6` and `0x0063`; require the observed baseline
   `0x00` and GPIO2 low.
2. Write only `0x02` to `0x03e6`, read both registers back, and require GPIO2
   data bit 2 to become high.
3. Wait 100--120 ms, matching Linux `hci_bcm`, then run the existing
   `btattach` action and record the first controller response or firmware
   filename.
4. Restore `0x03e6` to `0x00` and verify GPIO2 low, regardless of the HCI
   result.

Do this direct one-register test before writing a GPIO driver. If the radio
answers, add the smallest D2207 GPIO child needed by `hci_bcm`, describe the
Bluetooth serdev child with `shutdown-gpios`, and keep firmware local. If the
GPIO rises but HCI stays silent, investigate reset/wake sequencing and the
exact local firmware before changing any other PMIC register.

#### What the evidence already shows (no new measurement needed for this part)

Re-decoding `function-power_enable`'s raw bytes against m1n1's own `Function`
struct (`proxyclient/m1n1/adt.py`: phandle `u32`, name `FourCC`, args
`u32[]`) rather than my earlier informal byte-offset read:

```
function-power_enable   4e 00 00 00 4f 49 50 47 02 00 00 00 01 01 00 00
                         └─ phandle ─┘└── "OIPG" ──┘└── args: [2, 0x101] ──┘
```

Phandle `0x4e` is not a loose "resource-type tag" (my BT-1-result wording
undersold it) -- it is a literal ADT phandle, and the *same* J81 ADT has a
node with `AAPL,phandle = 0x0000004e`, `name = "pmu"`,
`compatible = "pmu,d2207"`, `reg = <0x3c 0x9c4>` (I2C address `0x3c`,
matching this board's already-working `pmic@3c` exactly), `device_type =
"interrupt-controller"`. So `power_enable`'s target is unambiguous:
resource **2** ("PMU GPIO2", args[0]) on the `pmu,d2207` chip at I2C
address `0x3c` -- the identical physical PMIC this board's kernel already
talks to for RTC and backlight. `args[1] = 0x101` doesn't have a confirmed
meaning: it's identical on `bt_wake` (AP GPIO164) and on an unrelated
   `function-keepact` (AP GPIO87) property elsewhere on the `pmu` node, so it
   can't be a per-pin polarity encoding -- more likely a generic "plain GPIO
   resource" tag. BAT-4 later proved that the `0x102`/`0x002` OIPG flags on
   UART resources do not directly encode the Apple pinmux selector; each route
   still needs hardware or driver evidence.
At the 2026-09-08 stage, this confirmed the resource number and exact chip but
not polarity. The later Apple Bluetooth driver cross-check documented above
resolves that final ambiguity as active high.

#### Where PMU GPIO2 sits in the Linux binding this board already uses

`t7001-air2.dtsi`'s `pmic@3c` (`compatible = "apple,arabela-pmic",
"apple,i2c-pmic"`) is bound by `drivers/mfd/simple-mfd-i2c.c` -- a fully
generic MFD driver (matches plain `"apple,i2c-pmic"`, no board-specific
code) that auto-populates whatever register-offset child nodes are present
(`rtc@5c0`, `backlight@600`, `nvmem@4000` today) as their own regmap-backed
platform devices. A `gpio@<offset>` sibling of those three, once the offset
is known, is an additive change to an already-working I2C path -- no new
transport code, same pattern already proven twice on this exact chip.

`drivers/gpio/gpio-regmap.c` is present in this kernel tree: a generic,
already-upstream `gpio_chip` implementation driven entirely by a
`struct gpio_regmap_config` (register address, bit width, optional
separate set/direction registers) supplied by a small glue driver. Standard
polarity handling (`GPIO_ACTIVE_HIGH`/`_LOW` in the consumer's DT cell) is
gpiolib's job, not this driver's -- the glue driver only needs to report
the pin's *raw* electrical state faithfully.

**Checked and ruled out, so this isn't reinvented later:** no driver
anywhere in this kernel tree (all Apple boards, not just T7001) implements
GPIO control for any `apple,i2c-pmic`-compatible chip -- confirmed by
grepping `drivers/gpio`, `drivers/mfd`, `drivers/regulator` and every Apple
DTS/DTSI in the tree. m1n1 upstream's own Python tooling
(`proxyclient/m1n1/hw/pmu.py`, `proxyclient/experiments/i2c_pmu_rtc.py`)
already has real, working D2207-family register knowledge -- RTC at
`0x5c6`, NVMEM at `0x4004`, panic-counter at `0x4002`, shared across the
`d2045`/`d2089`/`d2186`/`d2207` chip family -- but *no* GPIO register at
all. Corellium's own linux-sandcastle tree (searched directly via GitHub's
tree API, and via full-text code search across all of GitHub for "d2333")
has no findable D2333 PMU GPIO source either; this document's warning not
to copy Corellium's offsets is sound caution, not a reference to a
specific file that could be consulted instead. This was the state on
2026-09-08. The later Apple-driver disassembly above is the missing
independent evidence and supplies the exact mapping.

#### A real complication found while checking how `hci_bcm` would actually consume this

The original bullet list ("describe PMU GPIO2 as `shutdown-gpios`...")
assumed the standard `hci_bcm` DT binding would just pick this up. Reading
`drivers/bluetooth/hci_bcm.c` closely shows that's not automatic on this
platform:

- `shutdown-gpios`/`device-wakeup-gpios`/`host-wakeup-gpios` are read in
  `bcm_get_resources()`, called from **two** probe paths: `bcm_serdev_probe()`
  (a `serdev_device_driver`) and `bcm_probe()` (a plain `platform_driver`).
- The plain `platform_driver` (`bcm_driver`) has **no `of_match_table` at
  all** -- only `acpi_match_table`. Its own source comment says why: "we
  need to keep both platform device driver (ACPI generated) and serdev
  driver (DT)" -- i.e. mainline deliberately restricts DT boards to the
  serdev path only; the platform-device path exists solely for
  ACPI-described x86 Macs. `bcm_bluetooth_of_match` (which lists
  `"brcm,bcm43540-bt"`) is wired to the *serdev* driver only.
- The later serial-core audit established that `apple,s5l-uart` does expose a
  serdev controller when its DT node has a child. The standard DT path can
  therefore consume these GPIOs once the D2207 GPIO provider exists.
- One structural detail worth keeping for later, though: `bcm_open()` (the
  path `btattach`'s manual ldisc attach actually takes, `!hu->serdev`)
  *does* still look for a matching `struct bcm_device` by comparing
  `hu->tty->dev->parent == dev->dev->parent` -- i.e. `hci_bcm` was written
  to support GPIO/clock resources on a manually-attached tty too, provided
  some driver has already populated a `bcm_device` for a platform device
  sharing the tty's parent. That's *how* ACPI Mac laptops get GPIO-managed
  power on a plain USB-attached ldisc. It just needs a probe path that can
  reach it via DT, which doesn't exist upstream today.

The corrected implementation choices are:

1. **Preferred: use the existing serdev path.** Once the D2207 GPIO provider
   is implemented, add the Bluetooth child below UART3 and let unmodified
   `hci_bcm` consume `shutdown-gpios`, wake GPIOs, and the UART.
2. **Keep `btattach` as the transport diagnostic.** It already proved UART3
   and the HCI line discipline independently and remains useful while PMU
   power control is being developed.
3. **Userspace-only fallback.** Bundle one more small
   static tool (same pattern as `btattach` itself) that pokes the measured
   I2C register/bit for PMU GPIO2 directly via `/dev/i2c-N`, run once
   before `btattach`. No DTS change, no new kernel driver, nothing for
   `hci_bcm`'s own resource management to get wrong -- it already runs
   today with `bcm->dev == NULL` and silently skips all power management,
   which is consistent with the observed hardware failure. Loses
   `hci_bcm`'s own suspend/resume power sequencing, which doesn't matter
   yet since nothing here is suspend-aware.

The 2026-09-10 result locks in the shortest order: use the existing
`i2ctransfer` binary for the single reversible proof, then implement the
kernel GPIO/serdev path only after the radio responds.

#### BT-4 safe live probe tool, 2026-09-10

`boot/bt_probe.py` adds a host-side, bounded snapshot for the working telnet
channel. It runs only fixed reads for kernel/DT identity, UART3/serdev state,
Bluetooth class and HCI processes, D2207 GPIO2 (`0x03e6` and `0x0063`), the
charger/event status blocks, GPIO/pinctrl ownership, power domains, IRQs and
focused kernel messages. Its `i2ctransfer` calls use the PMIC register address
as the read transaction's address phase (`w2 ... rN`); no register data is
written. There is no arbitrary-command option, attach operation or reboot
operation. Bluetooth addresses are redacted from reports, and `--output`
accepts only a new file under ignored `artifacts/live/` with mode `0600`.

The existing `boot/ipad_console.py` menu now has the same probe as
“Bluetooth: safe read-only snapshot”. Repeated host-side captures are useful
for before/after comparison around the existing manual `btattach` action:

```sh
python3 boot/bt_probe.py --repeat 3 --interval 2 \
  --output artifacts/live/$(date -u +%Y%m%dT%H%M%SZ)-j81-bt-before.txt
```

After any explicitly supervised `btattach` attempt, run it again with an
`-after` filename and compare the `bluetooth`, `pmic-gpio2`, `power-and-
interrupts` and `kernel-log` sections. This keeps the current GPIO2 write
gate untouched while still showing whether the UART, HCI class, interrupt
count or PMIC state changes.

The first host attempt could not run the live collection: `172.16.42.1:23`
timed out and the route selected the normal LAN (`en5`); the USB network
interface was inactive. No command reached the iPad. Offline validation passed
with `python3 -m py_compile boot/bt_probe.py boot/ipad_console.py` and
`python3 boot/test_bt_probe.py`.

#### BT-5 transport-only attach result, 2026-09-10

The iPad was subsequently booted into the same postmarketOS image and became
reachable at `172.16.42.1` over USB networking. A three-sample read-only
baseline was saved privately as
`artifacts/live/20260910T182540Z-j81-bt-before.txt`
(`sha256=1b7bd41e90ba3932cd6bb033ffc2f8388635ec1a89bc65cf091c3a4aa55c7395`).
It confirmed J81/T7001, UART3 at `ttySAC1`, no HCI class device, and D2207
GPIO2 configuration/data reads of `0x00 0x00` and `0x20` (bit 2 low).

The already-bundled transport tool was then launched without changing any
PMIC or GPIO register:

```sh
btattach -B /dev/ttySAC1 -P bcm -S 3000000 >/tmp/btattach.log 2>&1 &
```

The shell does not provide `disown`, so that suffix printed `disown: not
found`; the background process still started and was cleaned up after the
capture. The post-attach snapshot is private at
`artifacts/live/20260910T182540Z-j81-bt-after-attach.txt`
(`sha256=d2d40bc60af31376740ed761b372185f2b2e67fca516b7aa8699de36b241b5e2`).

The result is the same transport boundary seen on 2026-09-08, now with a
before/after trace from the live session:

- `/sys/class/bluetooth/hci0` registered and linked to UART3, proving that
  `btattach`, the H4/Broadcom line discipline and the UART3 path all work.
- UART3 counters changed from `tx:0 rx:0` to `tx:14 rx:0`; the controller sent
  no byte back. The partial `hci0` sysfs link exposed no address or name.
- The kernel reported `command 0xfc18 tx timeout`, `BCM: failed to write
  update baudrate (-110)`, then `BCM: Reset failed (-110)`.
- PMIC GPIO2 remained `0x00 0x00` / `0x20` in every after sample, and no PMIC
  write was issued. The event/status reads only changed from transient event
  bytes to zeroed event bytes; the charger/status block stayed stable.
- No firmware or BlueZ scan was attempted because the controller did not
  answer the first Broadcom command. The next experiment remains the single,
  supervised GPIO2 A/B test documented in BT-3, with immediate read-back and
  restore.

#### Historical Stage A result, 2026-09-08: read-only scan before the GPIO map was recovered

The original plan was to do this via m1n1's own USB proxy mode, before
Linux boots at all. **That channel doesn't work on this hardware**: m1n1
reaches its own `Running proxy...` state cleanly and repeatably (confirmed
via the framebuffer console, four separate attempts -- cold restart, cable
left alone, cable reconnected, reconnected again), but the Mac never
enumerates a USB device from it at all, under any VID/PID, across every
variation tried. Not a workflow mistake; a real gap in this m1n1 fork's
USB gadget support for T7001, distinct from Linux's own `dwc2` gadget
driver (proven solid all session -- 0% packet loss). Pivoted to reading
the same chip from **Linux** instead, over `/dev/i2c-0` -- functionally
identical read semantics, just after Linux (not m1n1) has already touched
this PMIC for RTC/backlight, which isn't a real risk given those already
run constantly without issue.

Two small, real additions were needed, both now in `flake.nix`:

- `CONFIG_I2C_CHARDEV=y` in `patchedHoolockConfig` (was off; `CONFIG_I2C`
  and `CONFIG_I2C_APPLE` were already on, i.e. the bus itself already
  works, just not exposed to userspace). Purely additive -- doesn't touch
  existing driver behavior.
- `i2cToolsPkg`: the real `i2c-tools` package (small, dependency-free,
  unlike bluez -- the stock derivation cross-compiles directly). Had to
  override it to build statically (`BUILD_DYNAMIC_LIB=0
  BUILD_STATIC_LIB=1 USE_STATIC_LIB=1 LDFLAGS=-static` as real `make`
  variables, not `NIX_LDFLAGS` -- that route left the final tool-link step
  still pulling in shared `libgcc_s`, "cannot find -lgcc_s", since it
  doesn't reach gcc's own driver-level static-link detection the same
  way): confirmed via a *dynamically*-linked build first that its ELF
  interpreter path genuinely doesn't exist in this initramfs (same class
  of bug `btattach` hit and fixed the same way). Bundled into
  `m1n1-hoolock-control`'s initramfs via the same cpio-overlay pattern,
  alongside `btattach`.

Bus number turned out trivial to confirm, not needed to guess ahead of
time: `/sys/class/i2c-dev/i2c-0/name` reads `PA Semi SMBus adapter
(20a110000.i2c)` -- bus 0 is `i2c0`, matching `pmic@3c`'s parent exactly,
and `/sys/bus/i2c/devices/0-003c` confirms the kernel's own driver is
bound there (so every `i2ctransfer`/`i2cget` call needs `-f`, since the
address is "reserved" from i2c-dev's point of view -- expected, not an
error, and harmless for a read).

**Protocol verified before trusting anything unknown**: read the already
-documented `nvmem@0x4004` register (`i2ctransfer -f -y 0 w2@0x3c 0x40
0x04 r4`) and got `ef 93 2a 64` -- decoded as a little-endian u32 that's
a plausible mid-2023 Unix timestamp, consistent with `experiments/
i2c_pmu_rtc.py`'s own documented `NVMEM=0x4004` for this exact chip
family (`d2045`/`d2089`/`d2186`/`d2207`) and with this being a persistent
epoch-anchor value, not current time. This confirms the wire format (16
-bit big-endian register address, little-endian multi-byte values) is
correct.

Then a broad read-only dump: `0x0000`-`0x0400`, plus the known
`0x4000`/`0x5c00` regions for completeness. Full raw bytes kept private
in gitignored `artifacts/i2c/` (PMIC configuration state, not
device-identifying data, but kept to the same privacy convention as
`artifacts/adt/` regardless). Notable, but **not conclusive**:

- `0x0300`-`0x03a0` has an obvious structured, repeating 8-byte-stride
  table (`XX XX 00 YY 00 02 00 00`-shaped rows) -- looks like it could be
  a per-rail/regulator configuration table, which is exactly the kind of
  place a Bluetooth/WiFi combo chip's own supply might live. This is an
  observation worth carrying into Stage B, not a claimed identification --
  nothing ties any specific row to "resource 2" without either a
  datasheet (doesn't exist, checked) or an actual write-and-observe test.
- `0x5c00`-`0x5c30` (the documented live RTC counter region) read all
  -zero, which could look like a protocol failure but isn't necessarily
  one: this is a volatile, free-running counter (unlike nvmem, which is
  persistent), and this board has been power-cycled many times this
  session -- zero is also consistent with "recently reset". Noted
  honestly rather than treated as either a confirmed problem or explained
  away.

**Deliberately stopping before Stage B** (writing a candidate bit and
observing whether the chip responds). Nothing in the read-only dump gives
strong enough confidence in one specific register to justify a write yet
-- picking one to try is a real decision, not a mechanical next step, and
this document's own stop condition is exactly about not doing PMU GPIO
work on inferred-not-measured evidence. Flagging back rather than
guessing.

#### Why Stage B is a different category of risk than everything above it, 2026-09-08

Written before any register write is attempted, so the reasoning is on
the record independent of how the actual attempt goes later. This is not
a restatement of the stop condition (which already says "don't write
without measuring") -- it's the reasoning for *why* that condition
exists here specifically, since "measure first" alone doesn't explain
what could actually go wrong or how to bound it.

**What makes this different in kind, not just degree, from everything
else done in this project so far.** Every action up to this point --
reading ADT/FDT data, dumping PMU registers read-only, building and
bundling static tools, flipping kernel config options for buses that
were already proven working, even patching DTS to add new (disabled by
default, or additive) nodes -- has a bounded failure mode: "it doesn't
work" or "the build breaks", fixed by editing code and reflashing.
Nothing physical happens to the hardware if any of that is wrong. A
register write to a live PMIC is not in that category, because the
write's *effect* happens in real hardware the instant it lands, before
any script can inspect the result and decide whether to undo it.

**The write itself is trivially reversible; the reasoning below is about
what a wrong write can trigger before it's reversed, not about the byte
value.** The full `0x0000`-`0x0400` dump above means for any candidate
register there's already a known-good prior value on record, and writing
it back takes one more `i2ctransfer` call. That's not in question.

**Why "the prior byte value is known" isn't the same as "the risk is
bounded":**

1. **No datasheet exists for this exact chip.** Checked directly (this
   document's own earlier research, plus a live web search this session)
   -- nothing public documents `pmu,d2207`'s register map. Every
   candidate register's meaning is inferred from a byte pattern (the
   `0x0300`-`0x03a0` table looking regulator-shaped) or from a resource
   *number* (`2`) whose relationship to any specific register address is
   not established at all yet. "Plausible" is not "known."

2. **A byte write touches every bit in that byte, not just the one bit
   believed relevant.** If a candidate register packs multiple unrelated
   controls into one byte (common in compact PMIC register maps -- the
   `0x0300` table's own row shape, e.g. `14 14 00 20 00 02 00 00`,
   already shows multiple distinct-looking fields packed together), a
   write aimed at "the GPIO2 bit" that doesn't first read-modify-write
   around the other bits could change something else in the same byte
   without that being the intent, even if the byte is later restored.

3. **Fault-latching is a real, common PMIC behavior that a follow-up
   write doesn't necessarily clear.** Overcurrent/overvoltage/undervoltage
   protection circuits on a rail typically *latch* into a fault state
   once tripped, requiring an actual power-on-reset (not just "write a
   different value to the same register") to clear. If a wrong write
   trips a protection latch on some rail, writing the original byte back
   fixes the register's *stored* value, not necessarily the *live*
   fault state the hardware is already sitting in.

4. **Some PMIC registers are commands, not persistent state.** A write
   might not set a bit that stays set until changed again -- it might
   trigger a one-shot action (a reset pulse, a sequencer step, an NVM
   commit) the instant it lands. If that's what a candidate register
   turns out to be, "write the old value back" doesn't undo anything,
   because the action already happened and there was never a persistent
   bit to restore.

5. **The PMU supplies real power rails, and resource-number indexing
   into it is not yet cross-validated against a second data point.** The
   OIPG decode gives exactly one PMU resource number seen so far (`2`,
   from `power_enable`) -- there's no second, independently-confirmed
   PMU resource number to check the indexing scheme against. If the
   *addressing scheme itself* is misunderstood (not just "which specific
   register is GPIO2" but "how resource numbers map to registers at
   all"), a write aimed at "resource 2" could land somewhere entirely
   unrelated to any GPIO, peripheral-adjacent or otherwise.

**What bounds the risk, and why this is worth doing carefully rather
than not at all:**

- checkm8 is a permanent, unpatchable bootrom exploit (the whole reason
  this project's boot chain is possible at all) -- even a full hang or
  unexpected reset is recoverable via a DFU cycle, which this session
  alone has done more than a dozen times. The device cannot be
  soft-bricked out of checkm8's reach by anything done from a booted
  Linux userspace.
- Every PMU interaction confirmed working so far (RTC, backlight, and
  this session's own read-only scan) has stayed entirely within
  peripheral-adjacent functionality -- nothing so far suggests this PMIC
  exposes SoC-core or DRAM rail control to this register space at all.
- The specific candidate this document has evidence for (the `0x0300`
  table) is a small, bounded region, not an unconstrained sweep of the
  full address space.

**The process this project will follow whenever Stage B actually
happens** (recorded now, before it happens, so it isn't improvised under
time pressure with the device already in a modified state):

1. Take a fresh, complete read-only dump of the target register (and
   ideally its whole surrounding page) immediately before writing
   anything -- not relying on this session's dump, which may be stale by
   then.
2. Change exactly one bit via read-modify-write (read the current byte,
   flip one bit, write the modified byte) rather than writing a new
   full byte from assumption.
3. Read the register back immediately after the write to confirm what
   was actually stored, rather than trusting that the write command
   exiting cleanly means it landed as intended.
4. Test the hypothesis immediately (attempt `btattach`) rather than
   leaving the device in a modified, unverified state for any length of
   time.
5. Revert the byte immediately after testing, regardless of outcome, and
   read it back again to confirm the revert actually took.
6. One candidate register at a time -- never a sweep -- so that any bad
   outcome can be attributed to a specific, known cause rather than
   requiring a search after the fact.
7. Confirm the DFU/checkm8 recovery path is available and uncomplicated
   by anything else in progress before starting, so recovery is never
   competing with some other unrelated mid-flight experiment.

Not a blocker on doing this work -- a record of why it needs its own
explicit go-ahead and a deliberate process, rather than being treated as
a natural continuation of the read-only work above it.

#### Stage B attempt, 2026-09-13: write had no effect, no harm done, stopped there

Ran the exact 7-step process above, with the user present and this
document's own bounded test procedure, using `m1n1-hoolock-ans1-test`
(happens to carry the same UART3/BT-1 and PMU support as
`m1n1-hoolock-control`; unrelated to its ANS1 payload).

1. **Fresh baseline, re-confirmed live rather than trusting the
   2026-09-08 dump**: `0x03e0`-`0x03ef` read all-zero (so `0x03e6 = 0x00`)
   and `0x0060`-`0x0067` read `0f 03 42 20 7e 00 00 00` (so
   `0x0063 = 0x20`, GPIO2's bit -- mask `0x04` -- clear). Exact match to
   the prior record; `/sys/class/bluetooth` empty, `/dev/ttySAC1` present.
2. **Read-modify-write**: current byte `0x00`, target byte `0x00 | 0x02 =
   0x02`. Wrote it with
   `i2ctransfer -f -y 0 w3@0x3c 0x03 0xe6 0x02` -- exit code `0`, no I2C
   bus error, nothing new in dmesg at all.
3. **Immediate readback**: `0x03e6` still `0x00`, `0x0063` still `0x20`
   (GPIO2 bit still clear). The write did **not** take effect, despite
   the transaction itself completing cleanly on the bus.
4. **Delayed re-check** (a full console round-trip later, well past any
   plausible race): still `0x00` / `0x20`. Not a timing artifact.

**Stopped here, per the plan's own "one candidate at a time, don't push
past an unexpected result" rule** -- did not proceed to `btattach` (the
required precondition, GPIO2 data bit going high, never held), and did
not try alternate write patterns or byte values in the same session, since
that would be exactly the "sweep" this process was written to avoid.

**No harm done**: the register never actually changed from its recorded
baseline at any point (confirmed immediately and again after a delay), so
there was nothing to revert, and no dmesg error, PMIC fault indication,
or instability of any kind appeared anywhere in this or later checks.

**What this actually shows**: a plain 2-byte-address-plus-1-data-byte
I2C write -- the same shape that reads this exact chip perfectly -- is
not sufficient to change `arabela-pmic`'s stored GPIO2 configuration.
Either this chip needs something read-back-and-writes don't share (an
additional protocol element such as a checksum/CRC trailer, a different
opcode for writes than reads, or a lock/unlock sequence), or the kernel's
own `arabela-pmic` MFD driver (bound to this exact address, confirmed via
`/sys/bus/i2c/devices/0-003c/modalias` = `apple,arabela-pmic`) is
authoritative over this register in some way a raw `i2c-dev` write from
userspace doesn't route around. This is genuinely unknown, not yet worth
guessing at -- the productive next step, before any further live
attempt, is finding a real write path in the disassembled Apple PMIC/GPIO
driver code (the same `AppleD2207PMU`/backlight kext lineage already used
to decode the register map) rather than trying more raw byte patterns
against real hardware.

BT completion criteria: cold-boot repeatability, firmware loaded, controller
address stable, scan works, and three minutes of connect/disconnect activity
produces no UART overruns or HCI timeouts.

## Battery implementation

The complete source audit, timing analysis, and commit-level plan are in
[`research/j81-battery-hdq.md`](../../research/j81-battery-hdq.md). It
supersedes this section where the details differ.

**Implemented, compile-verified and hardware-confirmed, 2026-09-10.** BAT-1/2/3
added the serdev stop-bit API, the `bq27xxx_battery_hdq_uart.c` frontend and
the UART5/gauge DTS. BAT-4 found the DTS pinmux bug: AP GPIO34 must use
peripheral function 1, not the low byte of its `0x102` OIPG flags. With that
single live change, the driver reports `DEVICE_TYPE = 0x0545`, registers
`bq27545-battery`, and returns stable voltage, current, capacity, temperature
and cycle count. Ten unbind/rebind cycles repeated the same device ID and
plausible readings without an error. The remaining gate is booting the rebuilt
permanent DT and repeating across warm and cold boots.

**Pre-hardware review, 2026-09-09:** fixed the frontend's required serdev
`write_wakeup` callback, receive-before-transmit ordering, combined
echo/response collection, response-pulse threshold, break error handling, and
TX drain. These were caught before BAT-4; see the dedicated research document
and `kernel/test_hdq_uart_patch.py`.

### BAT-1: add an HDQ-over-serdev frontend

Add one focused driver,
`drivers/power/supply/bq27xxx_battery_hdq_uart.c`, plus its Makefile/Kconfig
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

The pinned kernel already registers Samsung UARTs with the tty-backed serdev
core, but mainline serdev has no stop-bit setter. Add the small generic
`CSTOPB` serdev operation used by Corellium before this frontend; do not patch
`samsung_tty.c`. Its existing termios implementation already honors two stop
bits.

The first probe transaction must issue TI Control() `DEVICE_TYPE` and log only
the numeric response. The ADT string says `bq27540`, while upstream's enum has
`BQ27541` and `BQ27545` but no exact `BQ27540`. Map to a core layout only after
the returned ID and register behavior are checked against the TI documentation.
Unknown IDs must fail with `-ENODEV`; they must not silently select BQ27545.

Use a provisional development compatible tied to the ADT evidence, then
finalize the TI-compatible name from the hardware ID before treating the patch
as upstreamable.

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

In J81, add the hardware-confirmed AP GPIO34 function-1 pinmux, enable UART5 without flow
control, and add the gauge as its serdev child. Keep this patch separate from
Bluetooth so either subsystem can be reverted independently.

BAT-2 passed with `DEVICE_TYPE = 0x0545` across ten live rebinds. After mapping
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
7. Prove Bluetooth PMU GPIO2 with the exact `0x03e6` A/B test, then add the
   standard serdev power/wake description if the radio responds.

For every hardware commit, preserve the current working USB network, RTC and
backlight baseline. Record the Git commit, payload SHA-256, full subsystem
`dmesg`, relevant sysfs output, pass/fail gate and next single experiment in
`docs/project-status.md`.

## Stop conditions

- Do not write a J81 GPIO or peripheral resource from J82 alone.
- Do not commit raw ADT/FDT, firmware, MAC addresses, serials or calibration.
- Do not add D2207 PMU GPIO control beyond the identified GPIO2 path until the
  exact `0x03e6` mapping and active-high polarity are reproduced by the bounded
  live A/B test.
- Do not select a bq27xxx chip layout from the ADT string alone.
- Do not combine Bluetooth and battery into one kernel patch or hardware run
  until each independent transport gate passes.

## Primary references

The working copies of `AppleD2207PMU` and `AppleBluetooth` used for the symbol
and disassembly cross-check remain local research artifacts and are not
committed; their public source artifacts are linked below.

- [PongoOS command sender](https://github.com/checkra1n/PongoOS/blob/master/scripts/issue_cmd.py)
- [PongoOS stdout reader](https://github.com/checkra1n/PongoOS/blob/master/scripts/fetch_stdout.py)
- [SoMainline ADT collection instructions](https://github.com/SoMainline/adt_collection)
- [SoMainline J82 ADT](https://github.com/SoMainline/adt_collection/blob/master/a8/J82.adt)
- [Hoolock Linux T7001 tree](https://github.com/HoolockLinux/linux/tree/6831bc701a6ce059e71e5aaa9488c9195bea6927)
- [Linux Broadcom Bluetooth binding](https://github.com/torvalds/linux/blob/master/Documentation/devicetree/bindings/net/bluetooth/brcm%2Cbluetooth.yaml)
- [Linux Broadcom HCI UART driver](https://github.com/torvalds/linux/blob/master/drivers/bluetooth/hci_bcm.c)
- [Unstripped iOS 10.3 s8000 AppleD2207PMU kext](https://github.com/userlandkernel/ios-unstripped-kexts/tree/master/kexts/10.3/s8000/AppleD2207PMU.kext)
- [Unstripped iOS 10.0 T8010 AppleD2207PMU kext](https://github.com/userlandkernel/ios-unstripped-kexts/tree/master/kexts/10.0/T8010/AppleD2207PMU.kext)
- [Unstripped iOS 10.3 s8000 AppleBluetooth kext](https://github.com/userlandkernel/ios-unstripped-kexts/tree/master/kexts/10.3/s8000/AppleBluetooth.kext)
- [Linux bq27xxx core interface](https://github.com/torvalds/linux/blob/master/include/linux/power/bq27xxx_battery.h)
- [Linux bq27xxx HDQ frontend](https://github.com/torvalds/linux/blob/master/drivers/power/supply/bq27xxx_battery_hdq.c)
- [Corellium's Apple HDQ-UART implementation](https://github.com/corellium/linux-sandcastle/blob/sandcastle-5.4/drivers/power/supply/bq27545-battery-hdquart.c)
- [TI-hosted bq27541-V200 datasheet](https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/196/bq27541_5F00_V200_5F00_DS.pdf)
- [Dedicated J81 battery/HDQ research](../../research/j81-battery-hdq.md)
