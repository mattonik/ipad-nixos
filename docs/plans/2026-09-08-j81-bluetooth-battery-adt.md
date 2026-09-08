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

The hardware attach attempt above supplied the "only when required" trigger
this section was waiting on. This section is a **scope**, written 2026-09-08
by reading the real driver/DT/ADT evidence rather than guessing -- no PMU
register has been written yet, no DTS has changed. Confirming the plan
before touching hardware again, per this document's own stop condition.

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
resource" tag. (By contrast, `function-tx`/`function-rts`'s args both carry
`0x102`/`0x002`, sharing a low byte of `0x02` that matches the
`APPLE_PINMUX(pin, 2)` alt-function-2 already used in `kernel/patches/`;
worth a small corrective note in the BT-1 section since it contradicts that
section's claim that alt-function isn't ADT-encoded, but doesn't change
anything already implemented.) **This confirms the resource number and the
exact chip, but not polarity** -- consistent with, and not overriding, this
section's original stop condition.

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
specific file that could be consulted instead. **There is no shortcut here
-- the register has to be measured, exactly as the stop condition says.**

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
- We already know from BT-1 that `apple,s5l-uart` has no serdev support.
  So neither existing `hci_bcm` probe path can ever fire on this board,
  no matter how the DTS describes the Bluetooth node -- the
  `shutdown-gpios` binding is currently unreachable here, independent of
  the register-measurement question.
- One structural detail worth keeping for later, though: `bcm_open()` (the
  path `btattach`'s manual ldisc attach actually takes, `!hu->serdev`)
  *does* still look for a matching `struct bcm_device` by comparing
  `hu->tty->dev->parent == dev->dev->parent` -- i.e. `hci_bcm` was written
  to support GPIO/clock resources on a manually-attached tty too, provided
  some driver has already populated a `bcm_device` for a platform device
  sharing the tty's parent. That's *how* ACPI Mac laptops get GPIO-managed
  power on a plain USB-attached ldisc. It just needs a probe path that can
  reach it via DT, which doesn't exist upstream today.

Three implementation options follow from this, independent of the
measurement step below (which is required no matter which is chosen):

1. **Add minimal serdev support to `samsung_tty.c`.** Reuses `hci_bcm`'s
   existing, standard, already-correct `shutdown-gpios` DT binding exactly
   as the original bullet list assumed, with zero changes to `hci_bcm.c`.
   Real driver work (a `serdev_controller` needs `.write_buf` and flow
   control wired through the existing UART TX path) but self-contained to
   one driver, and benefits every other serdev-shaped peripheral on this
   SoC too (this board's own HDQ/BAT-1 section already wants serdev on
   UART5).
2. **Teach `bcm_driver` a DT match table.** A few lines in `hci_bcm.c`
   (add `.of_match_table = bcm_bluetooth_of_match` to `bcm_driver`) plus a
   plain sibling `platform_device` node (child of `/soc`, which is
   `compatible = "simple-bus"` and auto-populates its children -- checked)
   rather than a child of `&serial3`. Smaller kernel diff than option 1,
   but rides on `bcm_open()`'s parent-pointer matching as an
   implementation detail mainline's own comment frames as legacy/ACPI-only
   -- more opportunistic, could break on an unrelated `hci_bcm` refactor.
3. **Userspace-only: no kernel GPIO driver at all.** Bundle one more small
   static tool (same pattern as `btattach` itself) that pokes the measured
   I2C register/bit for PMU GPIO2 directly via `/dev/i2c-N`, run once
   before `btattach`. No DTS change, no new kernel driver, nothing for
   `hci_bcm`'s own resource management to get wrong -- it already runs
   today with `bcm->dev == NULL` and silently skips all power management,
   which is consistent with the observed hardware failure. Loses
   `hci_bcm`'s own suspend/resume power sequencing, which doesn't matter
   yet since nothing here is suspend-aware.

No recommendation is being locked in yet -- (3) fits this project's
demonstrated preference (this session's own `btattach` work) for a small
bundled userspace tool over new driver code, and needs no DTS or driver
change until BT-3 is proven working at all, but that's a judgment call
worth revisiting once the measurement below actually says what register
and polarity are involved.

#### Stage A result, 2026-09-08: read-only scan done, protocol confirmed, no GPIO2 register identified with confidence yet

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
