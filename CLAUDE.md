# iPad NixOS

## Goal

Boot NixOS on old iPads (2011-2017, A5–A11 chips) via checkm8 bootrom exploit, turning e-waste into usable Linux machines.

## Status (2026-09-08): USB networking works -- real remote shell access to the device

The newer Hoolock kernel (`m1n1-hoolock-control`, Linux 7.3-rc1) booted
completely on its first hardware attempt and USB networking works
**bidirectionally** -- 0% ping loss, working telnet, genuine interactive
command execution on the live iPad over the network. This resolves the
entire USB investigation (Rounds 3-9) and reaches the actual goal that
work was chasing: not just Linux booting, but a working way to send it
input. Two overnight-bundled drivers (Apple PMIC RTC, backlight) were
also confirmed working on real hardware in the same session -- RTC set
the system clock from real hardware time, and the backlight physically
dimmed the screen on command (visually confirmed). Full transcript in
`docs/software-only-control.md`'s "Round 10."

Root cause in retrospect: the historical (2022) kernel had `dwc2` DMA
support hardcoded off, forcing a PIO mode that apparently can't reliably
complete bulk IN transfers on real T7001 silicon. Hoolock's kernel
restores real DMA hardware-capability detection, and that just works.

## Status (2026-09-07): Linux boots to an interactive shell

The `bootm` → m1n1 route (`docs/software-only-control.md`) got a real
hardware run on 2026-09-07 and, after four precisely-diagnosed bugs found
and fixed live across the session, **reached a live, interactive
postmarketOS `/ #` shell prompt on this exact iPad Air 2** -- the project's
primary goal, achieved in full. Bugs fixed in order: a missing newline in
the payload parser; a device-tree CPU-topology format mismatch; a misnamed
framebuffer node; and, decisively, a power-domain auto-shutdown
(`genpd_power_off_unused()`, a `late_initcall()` in Apple's PMGR driver)
that was killing the display's `disp0`/`dp` power domains right after
driver probing finished, fixed with `pd_ignore_unused clk_ignore_unused` on
the kernel command line. (An earlier theory blamed the bundled postmarketOS
Xperia Z5 debug initramfs hiding its own output -- ruled out once its own
unconditional startup marker never appeared on screen even after testing at
120fps, which is what led to finding the real, kernel-level cause instead.)

**Update, Round 6**: USB gadget enumeration is confirmed working on
hardware. `m1n1-control` now uses the *historical* kernel's own DTB (it
has the real `usbdev@20c100000`/`apple,t7000-usb` node mainline lacks),
patched with CPU-cell, framebuffer, and `cpu-release-addr` fixes (Rounds
3-5 below). On real hardware this boots Linux completely: `g_ether` binds
to the real USB controller, and the Mac sees a live USB device
(`0525:a4a2`, confirmed via `pyusb`/`ioreg`) with postmarketOS's
`172.16.42.1:23` telnet startup reported on screen. Remote interaction
has not yet been demonstrated.

**Current USB handoff, after Round 7 (2026-09-07):** disabling
`CONFIG_USB_ETH_EEM` lets macOS bind `AppleUSBCDCECMData` and create `en10`.
The host still receives zero packets, including after a verified direct
Mac-to-iPad connection. ARP is incomplete; ping and TCP port 23 time out.
The old assertion that this proves a DWC2 bulk-transfer bug was too strong:
we have not measured device-side RX/TX or USB completions. Forced-off DMA
explains the warning but does not validate PIO operation on T7001.

**Round 8 (2026-09-07): the diagnostic ran on hardware and found the fault
is asymmetric, not total.** `m1n1-usb-diagnostic` (preserves the working
kernel/DTB/bootloaders, overlays only a display hook) showed real
device-side evidence for the first time: `usb0` has 304 clean `rx_packets`
and a *complete* ARP entry for the Mac's exact MAC address -- proving
host-to-device traffic genuinely arrives and is processed. But
device-to-host fails: the bulk IN endpoint has a 90-byte packet programmed
into its transfer-size register that never reaches the physical TX FIFO
(`NPTxFEmp` asserted despite a pending transfer), while the CDC-ECM
control channel (`init ecm`, `activate ecm`, `SET_ETHERNET_PACKET_FILTER`
progressing to `0x0e`) negotiates completely normally. The generic PIO
fill-on-`NPTxFEmp` dispatch code read as unmodified mainline logic on
inspection, so the exact defect isn't pinned yet -- leading hypothesis is
a PIO partial-fill/re-arm bug specific to this forced-PIO (DMA hardcoded
off) historical fork. Full evidence in `docs/software-only-control.md`'s
"Round 8" and `research/t7001-usb-next.md`.

**Decision, 2026-09-07, after Round 8**: pursue Hoolock's newer kernel
(tracks mainline Linux 7.3-rc1, restores real dwc2 DMA hardware-capability
detection instead of forcing PIO) on `main`, while carrying the low-level
PIO-fill trace investigation forward independently on the
`usb-dwc2-pio-trace` branch (from tag `usb-diagnostic-round8-2026-09-07`)
so neither path blocks or discards the other -- "only positive in the
long run" regardless of which path resolves the USB fault first.

**Newer-kernel progress, same day: it builds.** `kernel/hoolock.nix` (new,
modeled on `kernel/historical.nix`) cross-compiles cleanly with this
project's existing GCC toolchain after one narrow, USB-unrelated fix (the
Apple PMIC backlight driver fails GCC's `-Werror=return-type`; disabled
via config, since Hoolock's own docs recommend Clang and backlight isn't
needed here). Produces a working `Image` and `t7001-j81.dtb` for this
exact board. That DTB already has `cpu-release-addr` and `enable-method =
"spin-table"` as proper mainline placeholders -- none of the CPU-topology
DTB patching Rounds 3-5 needed is required here; only the same
framebuffer-node rename Round 3 already proved was still needed, and is
now applied in a new `m1n1-hoolock-control` payload (also overrides
`deviceinfo_usb_rndis_function="ecm.usb0"` in the initramfs, since this
kernel has no `CONFIG_USB_ETH`/legacy `g_ether` at all and its configfs
gadget setup needs a function name this kernel actually has compiled in).
Builds cleanly, verified statically (DTB decompiled and checked, cpio
overlay parsed with the kernel's own last-entry-wins semantics rather
than assumed). **No hardware boot attempt on this kernel yet -- that's
next.** Full details, including the build and cpio-overlay bugs hit and
fixed along the way, in `research/t7001-usb-next.md`'s "Implementation
progress" and "Wired into a bootable payload."

Do not blindly swap only the DTB, enable DMA, or tune nonexistent FIFO
bootargs -- see [the complete research and implementation
log](research/t7001-usb-next.md) for what's actually been verified versus
assumed.

Full evidence and commands are in `docs/software-only-control.md`'s
"Round 3" through "Round 8".

**Bluetooth/battery execution plan, 2026-09-08**: USB is now a working control
channel. Live inspection over `172.16.42.1:23` confirmed Linux 7.3-rc1, the
correct `apple,j81` FDT, only UART0/`ttySAC0`, an empty Bluetooth class and an
empty power-supply class. The active 29,812-byte FDT was saved privately under
ignored `artifacts/adt/`; never commit it because it includes the device
serial. The focused plan is
docs/plans/2026-09-08-j81-bluetooth-battery-adt.md. The general roadmap remains
docs/plans/2026-09-08-ipad-air2-driver-bringup.md.

Key corrections: J82's T7001-family ADT identifies BCM4350 Wi-Fi on PCIe port
1, not BCM4354 over SDIO; Bluetooth is on UART3; the battery gauge uses HDQ on
UART5/GPIO34; and touch is on SPI3. Treat J82 as sibling evidence and compare
the live J81 ADT before committing board nodes.

The current Hoolock tip is already pinned. Do not update kernels blindly or
merge its test branches wholesale. RTC and backlight are hardware-verified.
Before adding UART3/UART5 board data, reboot only as far as PongoOS and run
`nix develop -c python3 boot/dump_adt.py`; the default output is private and
Git-ignored. Record only sanitized J81 resources and the capture hash. Then add
Bluetooth as a DT-only transport probe, followed by the battery HDQ serdev
frontend. Keep firmware, NVRAM, raw ADT/FDT, calibration data and per-device
identifiers outside Git.

**BT-1, 2026-09-08: UART3 hardware-confirmed.**
Real J81 ADT captured; UART3/UART5/battery pin numbers independently
decoded from its raw OIPG GPIO-function bytes (not copied from J82) --
every one matched J82 exactly, which is itself confirmatory evidence.
Added `serial3`/`uart3_pins` to `t7001.dtsi` and enabled `&serial3` with
RTS/CTS in `t7001-air2.dtsi`, as real `.patch` files under
`kernel/patches/` (multi-line DTS insertions, much more reviewable as a
diff than more `sed`), applied via `patch -p1` from `kernel/hoolock.nix`.
Implemented first without a Bluetooth child so the UART could be tested
independently. Booted on hardware: `ttySAC1`
registered at `0x20a0cc000` with `CTS|DSR|CD` active, confirming the
register/clock/power-domain/pinmux description is correct. Reaching
`hci0` in that transport-only image needs `btattach` in the initramfs.
Full detail in
`docs/plans/2026-09-08-j81-bluetooth-battery-adt.md`'s "BT-1 result".

**Serdev correction, 2026-09-08.** A later exact-source audit found the
earlier “Samsung UART has no serdev” conclusion stopped one call too early:
`samsung_tty.c` calls `uart_add_one_port()`, and common serial core then calls
`tty_port_register_device_attr_serdev()`. The built config already enables the
tty-backed serdev controller. UART3 Bluetooth and UART5 battery DT children
can therefore bind normally. The actual battery API gap is two-stop-bit
selection, which mainline serdev lacks even though `samsung_tty.c` honors
`CSTOPB`. Full research and the corrected implementation plan are in
`research/j81-battery-hdq.md`.

**Battery BAT-1/2/3 implemented and compile-verified, 2026-09-08.** Four
kernel patches (`kernel/patches/0003`-`0006`): a serdev stop-bit API
mirroring the existing `set_parity` op exactly; a new
`bq27xxx_battery_hdq_uart.c` frontend reusing the existing `bq27xxx` core
(identifies the real chip via a live TI `DEVICE_TYPE` readback rather
than trusting the ADT's compatible string); UART5 + the gauge serdev
child in DTS. A real `nix build` of both the kernel and the full
`m1n1-hoolock-control` payload succeeds; `System.map` and the built DTB
both confirm the new code and DT nodes actually compiled in. **Not
hardware-tested yet** -- nothing has been flashed to the device with
this kernel. Full detail in `research/j81-battery-hdq.md`'s
"Implementation result, 2026-09-08".

**Battery pre-hardware review, 2026-09-09.** Fixed three transport bugs before
the first device boot: `serdev_device_write()` requires a client
`write_wakeup` callback or returns `-EINVAL`; separate echo and response waits
could strand bytes delivered together by tty; and gauge pulses must use
Corellium's `>= 0xf0` one-bit threshold instead of exact UART-byte equality.
The receiver is now armed before transmit for one combined echo/response
buffer, consumes noise while synchronizing on the command echo, checks break
errors, and waits for TX drain. `kernel/test_hdq_uart_patch.py` guards these
invariants and all 256 byte round trips.

**Touch (SPI3) groundwork started, 2026-09-09 -- not wired into the
build.** `kernel/patches/0007` ports and cleans Hoolock's `tests/kat-spi`
(`c065201`, confirmed the more complete of the two referenced branches,
correcting a doc citation of the less-complete `0019398`) into
`drivers/spi/spi-apple.c`: drops a `dev_info()`-per-transfer spam and a
global `bool defered` hack that forced every probe to defer once
unconditionally. `0008`/`0009` add and enable the SPI3 DTS node
(`apple,s5l8960x-spi`, register/IRQ/clock-gate real-ADT-confirmed) --
including a real correction, not an assumption: the CS0 pinmux alt-function
is `1`, not `2` like UART3/UART5's pins, confirmed by pulling every
`function-tx`/`function-rts` pair across every UART instance in the ADT
first (the field genuinely varies per pin). All three patches individually
apply cleanly and the DTS compiles with the real `dtc`. A pre-build review
fixed reversed MC/S5L bit-order selection, a completion IRQ returned as
`IRQ_NONE`, completion reinitialization after IRQ enable, and an uninitialized
S5L RX count; `kernel/test_spi_s5l_patch.py` guards them.

**TOUCH-1 software gate passed, 2026-09-10.** All three patches are wired
into `kernel/hoolock.nix` and the full payload cross-builds. Verified rather
than inferred from exit status: `apple_s5l_spi_irq` is in the built
`System.map` (so the ported code is genuinely compiled in, not merely
patched into a file), the DTB carries an enabled `spi@20a08c000` with the
right register window and IRQ 155, its `power-domains` resolves to the
distinct `power-controller@20198` labelled `"spi3"`, and its pinmux is
`0x10033` -- `(function 1 << 16) | pin 51`, the same encoding form BAT-4
proved correct on GPIO34's `0x10022`. `CONFIG_SPI_APPLE` was already `=y`
upstream, so no config change was needed. Remaining for TOUCH-1 is the
hardware gate only; the CS0 function is still provisional and wants the
bounded live A/B test. Nothing is flashed, so the previous payload restores
the known-good battery state.

**TOUCH-1 hardware gate passed, 2026-09-12.** Booted on real J81 hardware.
The controller registered a working `spi_master` -- as `spi0`, not `spi3`,
because `apple_spi_probe()` doesn't consult the DT alias for bus numbering
and this is the only SPI controller in the system; confirmed it's genuinely
our node via `readlink -f /sys/class/spi_master/spi0` resolving to
`.../20a08c000.spi/spi_master/spi0`. Power domain and pinctrl suppliers both
resolved before probe (visible as reverse-dependency links in sysfs), no new
dmesg errors, battery driver unaffected, 4 minutes stable uptime. TOUCH-1 is
complete. CS0 itself is still untested -- no real transaction has happened
without a child device, which is TOUCH-2's job.

**TOUCH-2 research, 2026-09-10.** The child `reg` blocker is **resolved by
reading the mainline binding rather than by decoding Apple's packing**: the
parent's `#address-cells = 1` makes the 32-byte ADT `reg` parse as chip
select `0` plus seven Apple-private cells Linux never reads, and
`apple,z2-multitouch.yaml`'s own example uses `reg = <0>`. Also found a
concrete crash to avoid: `apple_z2_probe()` dereferences
`spi_get_device_id(spi)->driver_data` unchecked, and DT-probed SPI devices
match that table by modalias, so a J81 compatible must be added to
`apple_z2_of_id[]` as well as `apple_z2_of_match[]` or probe NULL-derefs.
Still open: `KLCT`'s argument layout, and the binding-required
`touchscreen-size-x/y` (no `spi-frequency` exists on the `multi-touch` node
at all -- only `mesa` has one). Full detail in
`docs/plans/2026-09-09-j81-touch-spi3.md`.

**TOUCH-1 CS0 pinmux confirmed on hardware; TOUCH-2 crash-fix implemented,
2026-09-12.** Booted the TOUCH-1 payload on real J81 hardware: the SPI3
controller genuinely probes (registers as `spi0`, not `spi3` -- cosmetic,
`apple_spi_probe()` doesn't consult the DT alias for bus numbering; confirmed
via `readlink -f /sys/class/spi_master/spi0` resolving to
`.../20a08c000.spi/spi_master/spi0`). Same session, live pinctrl debugfs
confirmed `pin 51 (PIN51): device 20a08c000.spi function periph1` -- the
provisional `APPLE_PINMUX(51, 1)` was correct, no A/B test needed. Touch
pins 55/82/84/95 read cleanly unclaimed, a clean baseline for TOUCH-2.
Then implemented the already-documented `apple_z2` crash-fix:
`kernel/patches/0011` adds `apple,j81-touchscreen` to both its match tables,
`CONFIG_TOUCHSCREEN_APPLE_Z2=y`/`CONFIG_INPUT_TOUCHSCREEN=y` are set,
cross-build verified (`apple_z2_probe`/`apple_z2_of_id` in `System.map`).
Checked this Mac's local `AppleD2207PMU`/`AppleMultitouchSPI` kext copies for
the `KLCT` clock-enable path -- both dead ends (metadata-only stub; the only
real binary found is a decade too modern) -- so a fresh local IPSW
extraction is the real next step for `KLCT` and `touchscreen-size-x/y`. The
child DT node itself stays a documented draft, deliberately not written as a
real patch: enabling it now would fail for three compounding unresolved
reasons at once (no firmware, unconfirmed size, unimplemented power
sequence), which would make any hardware result impossible to attribute.

**Internal storage (ANS1): hardware gate passed, 2026-09-13.** Hoolock's
`ans1` branch (real, credible upstream work by Nick Chan) compile-verifies
in isolation, but its default behavior unconditionally unlocks writes to
the iPad's real internal NAND on probe and has three reachable
`BUG()`/`BUG_ON()` calls. `kernel/patches/0012` removes the unlock command
outright, rejects all block writes/flushes at a single dispatch point,
marks every namespace (including user data) read-only, and downgrades all
three fatal assertions to graceful errors -- cross-build verified alone
first, then reconciled onto this project's own patched tree (17/19 ans1
files applied with zero conflicts; only `t7001.dtsi`/`t7001-air2.dtsi`
needed one trivial hand-reconciled `aliases` entry) as a **separate,
dedicated payload**, `packages.x86_64-linux.m1n1-hoolock-ans1-test`
(`kernel/hoolock-ans1-test.nix`), deliberately not merged into
`kernel/hoolock.nix`/`m1n1-hoolock-control` so ANS1 never runs as a side
effect of routine touch/battery work. **Booted on real J81 hardware**:
`apple-asp 208040000.block` probed all ten namespaces with genuine RTKit
firmware traffic (EFFACE/NVRAM/SYSCFG/PANICLOG/LLB/UTILDM/CTRLBITS/FW/DM),
every `asp0n{1..10}` device came back `ro=1` read directly from sysfs,
`asp0n1` (USERAREA) reported a real 128 GB capacity, zero occurrences of
`WRITE_UNLOCK` and zero crash indicators appeared anywhere in dmesg, and a
gated single 4096-byte read against USERAREA succeeded cleanly with the
system stable throughout (3 min uptime, no crash loop).
`m1n1-hoolock-control`'s output hash was separately re-verified
byte-identical to before this work. One real Nix bug found and fixed
along the way: a config derivation used `cp` on an existing store path
(read-only, `-r--r--r--`) and inherited that permission, breaking a
following append -- fixed with `cat ... > "$out"`, which always creates a
fresh writable file. Making the storage actually usable (filesystem,
writes) is future work, not implied by this result. Full detail in
`docs/plans/2026-09-13-j81-ans1-observation-only.md`.

**Bluetooth GPIO2 write attempted, 2026-09-13: safe, no effect.** Followed
the plan's own pre-committed 7-step process for the first live PMU
register write: fresh baseline matched the 2026-09-08 record exactly
(`0x03e6=0x00`, `0x0063=0x20`, GPIO2 low), the read-modify-write to `0x02`
via `i2ctransfer` completed with no I2C bus error, but neither an
immediate nor a delayed readback showed any change -- the write never
actually landed, so there was nothing to revert. No dmesg error, no
instability, no harm. This chip's actual write path is evidently not a
plain 2-byte-address-plus-1-data-byte transaction (the same shape that
reads it fine); real research into the disassembled PMIC driver's write
routine is the next step before trying again, not another raw byte
pattern. Full detail in
`docs/plans/2026-09-08-j81-bluetooth-battery-adt.md`'s "Stage B attempt".

**TOUCH-3, 2026-09-13: touch-ASIC registers found, KLCT partially traced
-- no IPSW download needed.** A public repo of unstripped Apple driver
kexts (already cited in `docs/plans/2026-09-09-j81-touch-spi3.md`'s
references, fetched via a sparse `git clone`, a few MB) gave real,
concrete touch-controller-internal register addresses straight from
`AppleMultitouchSPIJ82.kext`'s `Info.plist` (`clk32-clock-enable-addr/-val`,
`fll-mval-addr/-mval`, `fw-execute-addr`, `cal-dl-addr`, `prox-cal-addr`)
-- enough to implement most of the touch bring-up sequence. Separately,
disassembled `ApplePMGRFunctionClockGate::callFunction` (the real KLCT
handler, in the same repo's `ApplePMGR.kext`) with Xcode's bundled
`llvm-objdump`, tracing `function-clock_enable` through
`ApplePMGR::_enableDevice` → `_enableDeviceGated` → `_updateDeviceStatus`,
and cross-validated the PMGR base address (`0x20e000000`) against this
project's own captured real ADT -- two independent sources agreeing.
**Still open**: the exact register KLCT's device-index `8` resolves to --
mainline's own `t7001-pmgr.dtsi` has no touch/multitouch entry to compare
against (only `ps_spi0`-`ps_spi3`), so this needs more disassembly of
already-fetched binaries (a data table lookup, not yet located), not a
new download. Full detail in `docs/plans/2026-09-09-j81-touch-spi3.md`'s
"TOUCH-3, 2026-09-13".

**BAT-4 hardware gate: real result, 2026-09-10.** UART5 (`ttySAC2`) registers
cleanly on hardware, and independent cross-checks (live pinctrl debugfs, the
real ADT, the decompiled DTB) confirm pinmux, power-domain, IRQ and register
wiring are all correct -- but HDQ identification hard-ETIMEDOUTs. A
raw-byte-count diagnostic (`kernel/patches/0004`, dev_info-only, no protocol
change) pinned the failure precisely: **`got 0/16 bytes`** -- total RX
silence, not even our own transmitted command looping back. Since HDQ's
single-wire design depends on exactly that loopback, this points at a
hardware mux, not a protocol/timing bug: Corellium's own reference driver
explicitly switches a charger-IC-controlled HDQ mux on/off around every
transaction, which this frontend never does. J81's ADT does have a
`charger,k48` node, but no i2c address or mux-control property was found on
it yet -- next research target, not yet resolved. Full detail in
`research/j81-battery-hdq.md`'s "BAT-4 result, 2026-09-10" section.

Also found and fixed along the way: the macOS Linux builder VM was being
started wrong twice over (a plausible-looking `nix run
nixpkgs#darwin.linux-builder-vz` creates a different, wrong-directory VM;
then a fresh from-scratch disk -- rather than the real, warm, in-repo one --
produced three consecutive segfaults before that was understood) -- now a
documented, git-tracked flake output
(`packages.aarch64-darwin.linux-builder`, run from inside this repo, see
`docs/build-infrastructure.md`). Also found the kernel config had
`CONFIG_DEBUG_INFO=y`, whose DWARF sections were what actually exhausted the
builder's disk during the final kallsyms/link step even on a warm,
just-garbage-collected 40 GB disk -- disabled, not needed for this
project's goal.

**`btattach` built and bundled, 2026-09-08.** `boot/btattach.nix` compiles
just `tools/btattach.c` and the handful of `src/shared/*.c` files it
actually needs, directly with `$CC` -- bypassing BlueZ's autotools, whose
`./configure` unconditionally requires glib+dbus for every tool
regardless of which one you want (confirmed slow in practice: killed a
full-package build after 24+ minutes). Statically linked, since the debug
initramfs's musl is a separate build from this project's own. Wired into
`flake.nix` as `btattachPkg` and bundled into `m1n1-hoolock-control` at
`usr/bin/btattach` via the same cpio-overlay technique already used for
the `ecm.usb0` deviceinfo override. Console tool gained matching actions
("Bluetooth: hci0 status", "Bluetooth: attach HCI UART"). Verified at the
Nix level only (binary present, genuinely static, deviceinfo override
intact -- see the plan doc for how, since a naive `cpio -it` listing looks
like a silent failure here and isn't one).

**Hardware-tested, 2026-09-08: `hci0` registers, chip stays silent.**
`hci_bcm` bound to `/dev/ttySAC1` immediately and `hci0` appeared in
`/sys/class/bluetooth` -- BT-1's full pass criterion, now hardware-proven
end to end. But the chip never answered a single command: `Bluetooth:
hci0: command 0xfc18 tx timeout` / `BCM: Reset failed (-110)`. This fails
before firmware is even relevant, and points at `function-power_enable`
(PMU GPIO2, independently decoded earlier) needing to be asserted first --
exactly the gap BT-3 left open. **Stopping here deliberately**: the plan
doc's own stop condition is "Do not add D2207 PMU GPIO control until its
register layout and polarity are measured" -- that's real new
hardware-facing work, not more bundling, so it needs its own go-ahead.
Full detail in `docs/plans/2026-09-08-j81-bluetooth-battery-adt.md`'s
"Hardware attach attempt, 2026-09-08".

**BT-3 scoped, 2026-09-08 (no hardware touched).** Byte-exact ADT decode
confirms `power_enable`'s phandle points at the real `pmu,d2207` node
(I2C `0x3c`, same chip already backing RTC/backlight) requesting its
resource 2. `t7001-air2.dtsi`'s `pmic@3c` uses the generic
`simple-mfd-i2c.c` MFD driver, so a new `gpio@` child is additive, not new
transport plumbing -- but no driver anywhere in this kernel tree (or in
m1n1 upstream's own D2207-aware Python tooling) implements PMU-GPIO
control for this chip family, confirming real measurement is unavoidable.
`hci_bcm`'s standard `shutdown-gpios` binding is DT-reachable through its
serdev driver; the plain `platform_driver` path is ACPI-only by mainline's
design. The corrected serial-core audit confirms the standard serdev path is
available here, so no Samsung UART or `hci_bcm` probe-path patch is needed.
The remaining Bluetooth dependency is the unimplemented D2207 PMU GPIO
provider and measured GPIO2 register/polarity.

**BT-3 Stage A done, 2026-09-08: read-only scan complete, no register
write yet.** m1n1's USB proxy mode never enumerates on this hardware
(four separate attempts, real gap in this m1n1 fork's gadget support, not
a workflow mistake) -- pivoted to reading the same `pmu,d2207` chip from
Linux instead, over `/dev/i2c-0` (needed `CONFIG_I2C_CHARDEV=y`, off by
default, and a statically-linked `i2c-tools` bundled the same way as
`btattach` -- the stock dynamic build hit the identical ELF-interpreter
problem `btattach` did). Protocol verified against the known
`nvmem@0x4004` register before trusting anything new (decoded as a
plausible timestamp, matching `i2c_pmu_rtc.py`'s own documented offset
for this chip family). Full `0x0000`-`0x0400` dump done; a structured
table at `0x0300`-`0x03a0` looks plausibly like a per-rail config table
but isn't confirmed as anything specific. **Deliberately stopped before
writing any register** -- nothing in the read-only data justifies picking
one candidate over another yet; that's a real decision needing its own
go-ahead, not a mechanical next step. Full writeup in
`docs/plans/2026-09-08-j81-bluetooth-battery-adt.md`'s "Stage A result".

**Why Stage B needs its own go-ahead, recorded 2026-09-08 before any
write is attempted**: a PMU register write is a different risk category
from everything else in this project, not because the byte itself is
hard to revert (the full dump means any prior value is on record), but
because a wrong write's *live effect* -- a fault latch, a one-shot
command register, an adjacent bit in the same byte controlling something
else -- can land before anything gets a chance to undo it, and there's
no datasheet to rule that out ahead of time. checkm8 bounds the worst
case (a hang/reset is always DFU-recoverable), but doesn't make the
write itself risk-free. Full reasoning and the process to follow when
this is actually attempted (read-modify-write one bit, verify by
readback, test immediately, revert immediately, one candidate at a time)
in `docs/plans/2026-09-08-j81-bluetooth-battery-adt.md`'s "Why Stage B
is a different category of risk".

The historical-PongoOS control is a separate, lower-priority experiment,
still blocked: `palera1n`'s stager rejects its 708,704-byte binary (limit
is 0x7fe00 = 523,776 bytes) -- unresolved, not needed now that m1n1 works.

Do not resume blind changes to the modern PongoOS fork's direct-jump path;
that specific mechanism has been tried seven ways and ruled out each time.
A7–A8X Linux uses 4 KiB pages; older 16 KiB claims in historical logs are
superseded. Touch and Wi-Fi work follows the evidence and staged hardware
gates in the current driver plan.

## Target Hardware

- **Primary target**: iPad Air 2 (A8X, 2014) — 3-core ARM64, 2GB RAM, PowerVR GXA6850 GPU
- **Exploit**: checkm8 (permanent, unpatchable bootrom vulnerability for A5–A11)
- **Boot chain**: checkm8 → pongoOS → Linux kernel → NixOS userland

## Project Structure

```
ipad-nixos/
├── research/          # Phase 0 output — feasibility analysis
│   ├── landscape.md   # Existing projects analysis
│   ├── hardware.md    # iPad Air 2 hardware mapping
│   ├── boot-chain.md  # Full boot path documentation
│   ├── driver-gap.md  # Driver status matrix
│   └── feasibility.md # Final assessment and roadmap
├── boot/              # Boot chain tools and configs
├── kernel/            # Kernel configs and patches
├── nixos/             # NixOS configuration for iPad
├── drivers/           # Custom driver work
├── devenv.nix         # Development environment
├── flake.nix          # Nix flake
└── CLAUDE.md          # This file
```

## Phase 0: Research & Feasibility (autonomous)

Systematic analysis of all existing work. No hardware needed.

1. **Landscape analysis** — deep-dive every existing project:
   - checkm8 / checkra1n (bootrom exploit)
   - pongoOS (pre-boot environment)
   - Project Sandcastle (Android on iPhone)
   - postmarketOS iPhone/iPad support
   - linux-on-iphone GitHub projects
   - Asahi Linux (Apple Silicon Macs — different but relevant techniques)
   - Corellium (commercial iOS virtualization — published research)

2. **Hardware mapping** — iPad Air 2 (A8X) specifics:
   - SoC architecture, memory map, peripheral addresses
   - Device tree sources (from iOS firmware, existing Linux DTs)
   - Display controller, touch controller IC identification
   - WiFi/BT chip (Broadcom model, firmware requirements)
   - GPU (PowerVR GXA6850) — driver status in Mesa/open-source

3. **Boot chain documentation** — full path for iPad specifically:
   - checkm8 exploit execution
   - pongoOS loading and capabilities
   - Linux kernel handoff (how pongoOS passes control)
   - Device tree passing, initramfs requirements
   - What works on iPhone 7 that could transfer to iPad Air 2

4. **Driver gap matrix** — per subsystem:
   - Display: existing framebuffer support, DRM/KMS status
   - Touch: multi-touch controller RE status
   - WiFi: Broadcom chip model, firmware, driver (brcmfmac? wl?)
   - GPU: PowerVR open-source driver status (Mesa PVR?)
   - Audio: codec identification, ALSA/PipeWire feasibility
   - Battery/charging: power management IC
   - USB: host/device mode capabilities
   - Bluetooth: chip, firmware, driver
   - Sensors: accelerometer, ambient light, etc.

5. **NixOS scaffolding** — aarch64 cross-compilation:
   - Base NixOS config targeting A8X
   - Cross-compilation flake setup
   - Minimal rootfs generation

## Phase 1+: Hardware-in-the-loop (interactive)

Requires physical iPad + USB connection to NixOS workstation.

### Feedback Loop Setup

```
NixOS ThinkPad ──USB──► iPad Air 2
     │                      │
     ├─ Claude reads serial ◄─ /dev/ttyACM0 (boot logs)
     ├─ Claude builds kernel
     ├─ Claude prepares flash scripts
     │
     └─ User: runs ./flash.sh, takes photos for display testing
```

### Tools

- `libimobiledevice` — iOS USB communication
- `libirecovery` — recovery/DFU mode
- `picocom` — serial console reader
- `ghidra` / `radare2` — binary analysis
- Nix cross-compilation for aarch64

## Guidelines

- Research first, code second
- Document every finding in research/ directory
- Be honest about blockers and difficulty
- Cross-reference multiple sources before concluding anything
- Focus on iPad Air 2 (A8X) specifically — don't generalize across all iPads
