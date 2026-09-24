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

**Branch closed, 2026-09-13.** Hoolock's kernel (the other path) won
outright the very next day -- real DMA support just works, making the
whole forced-PIO question moot for this project's actual goal. The
branch's own one unique commit (Round 9, pure source analysis) is worth
keeping as a record: it ruled out a software fill-logic bug in
`dwc2_hsotg_write_fifo()` (byte-identical to mainline v7.2) and narrowed
the historical fork's asymmetric USB fault to somewhere downstream of the
software FIFO fill -- a real hardware completion-interrupt/bus-level
issue, or possibly host-side, neither confirmable from source reading
alone. Explicitly not resumed this session -- would need UART/JTAG-level
access or an independent Linux USB host to make further progress, and
the user has declined new hardware investment. The branch and its
`usb-diagnostic-round8-2026-09-07` tag remain in git, unmerged, as an
inert historical record.

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

**ASP cross-referenced against real Apple source, 2026-09-13.** A real
iPad5,3 iOS 8.1 kernelcache (pulled with `blacktop/ipsw`, remote
kernelcache extraction only, no multi-GB download -- see the touch entry
below) has Apple's own original ASP driver
(`com.apple.driver.ASPSupportNodes`,
`AppleStorageProcessorNodes-195.3.1`). Confirms the Linux `ans1` port's
namespace-to-class mapping from Apple's own code, that Apple's own
`SetWritable`/`ASPSetWritable` is called conditionally rather than
unconditionally (the pre-hardening Linux port's behavior), and that NAND
formatting really is opt-in on Apple's own side (`nand-enable-reformat`)
-- independent confirmation of conclusions this project already reached.
Full detail in `research/j81-long-term-subsystems.md`'s "Real Apple ASP
source cross-reference".

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

**TOUCH-3, 2026-09-13: touch-ASIC registers found, KLCT fully decoded --
no IPSW download needed.** A public repo of unstripped Apple driver kexts
(already cited in `docs/plans/2026-09-09-j81-touch-spi3.md`'s references,
fetched via a sparse `git clone`, a few MB) gave real, concrete
touch-controller-internal register addresses straight from
`AppleMultitouchSPIJ82.kext`'s `Info.plist` (`clk32-clock-enable-addr/-val`,
`fll-mval-addr/-mval`, `fw-execute-addr`, `cal-dl-addr`, `prox-cal-addr`)
-- enough to implement most of the touch bring-up sequence. Separately,
after an initial mistrace of the wrong generic class
(`ApplePMGRFunctionClockGate`), found and disassembled the real KLCT
handler -- `ApplePMGRFunctionEnableTouchClock`/`ApplePMGR::enableTouchClock`,
in the same repo's `ApplePMGR.kext` -- with Xcode's bundled `llvm-objdump`.
**KLCT's three ADT words are now fully decoded**: an 8 µs enable-settle
delay, a 100 µs disable-settle delay, and a 32.768 kHz target frequency
converted to a divisor of 732 against a fixed 24 MHz reference clock --
not a device-table index, as first assumed. Cross-validated PMGR's base
address (`0x20e000000`) against this project's own captured real ADT --
two independent sources agreeing. **Still open**: the one fixed register
offset `enableTouchClock` itself reads/writes -- confirmed (via a public
symbol-signature database) to be `_regGroups[kRegGroupTouch]`, group
index 3, the one gap `AppleT7000PMGR::initRegGroups()` never fills
(`0,1,2,4,5,6`). Tried a genuinely different iOS SDK build (iOS 11.0's
T7000 kernel, a different public repo) and the real ADT's own `pmgr`
"devices" table (a complete, human-readable device list with no
touch/multitouch entry); both ruled out. Every source found so far is an
iPhone build that merely bundles T7001 support, not an actual iPad5,3
firmware -- a real IPSW is now the best-motivated next step for this one
number.

**TOUCH-3, third pass, 2026-09-13: pulled a real iPad5,3 IPSW; register
offset still not pinned down.** Installed `blacktop/ipsw` (GitHub release
binary) and remote-extracted just the kernelcache -- no multi-GB
download -- from the genuine iOS 8.1 ship firmware (12B410), using a
publicly-known decryption key auto-fetched from TheiPhoneWiki. Confirmed
the same mechanism exists at ship under an earlier name
(`AppleT7000PerformanceControllerFunctionEnableTouchClock`, predating the
later `ApplePMGR` split), with new panic strings
(`"invalid target frequency: %d"`) independently corroborating the
frequency-based decode from a completely different Apple engineering
era. But this kernelcache generation has zero per-kext symbols at all
(confirmed via `LC_SYMTAB` directly) -- traced the class by address
anyway and found only trivial destructor-thunk vtable slots; the real
logic lives in the shared parent class, unreachable without a proper
decompiler (IDA/Hopper/Ghidra) rather than `objdump`+`grep`. Stopped
deliberately rather than open-ended address archaeology -- the rest of
the KLCT decode stands on its own regardless.

**TOUCH-3, fourth pass, 2026-09-13: got a real decompiler (Ghidra), still
genuinely exhausted.** Installed Ghidra 12.1.3 (`brew install ghidra`;
needs `JAVA_HOME` pointed at the `openjdk@21` keg, not symlinked into
`PATH`) specifically to get past the third pass's symbol-free-binary
wall. Imported the *entire* 14 MB `__PRELINK_TEXT` segment (all 169
kexts, one flat address space) as a raw ARM64 binary at its real load
address, ran full auto-analysis (~10.5 min headless), then scripted the
decompiler (Java `GhidraScript`, `DecompInterface`) to: (1) independently
re-confirm the string-xref dead end via real cross-kext-boundary
reference analysis, not per-kext text matching; (2) confirm zero
references anywhere in the full region to the panic strings; (3) dump
`AppleT7000PerformanceController`'s vtable -- caught and corrected a real
mistake here, the address named in the `OSMetaClass` constructor call is
the *MetaClass object's own* vtable, not the driver instance's, something
the decompiled `MetaClass::alloc()` body made obvious; (4) dump the *real*
instance vtable (80 slots). Result: the class overrides only 3 of ~80
inherited `IOService` methods -- it almost certainly does **not** override
`callPlatformFunction` at this iOS version at all. The real dispatch most
likely lives one level up, in `AppleARMPlatform.kext`'s own generic
platform-function framework (confirmed as a real, separate kext this
class imports symbols from) -- never examined this session. Four
independent techniques (manual disassembly, a real ship firmware, and a
full-region professional decompile) now converge on the same wall;
finding the offset from here means opening a new kext, a new
investigation, not a continuation of this one. **Not pursuing further
today.** Full detail in `docs/plans/2026-09-09-j81-touch-spi3.md`'s
"TOUCH-3, 2026-09-13 (fourth pass)".

**TOUCH-3, fifth pass, same day: opened `AppleARMPlatform.kext`, the
dispatch mechanism is now fully mapped, register offset still open.**
Picked up exactly the thread the fourth pass left dangling. Pulled
`AppleARMPlatform.kext` (ships with real symbols, unlike the stripped
kernelcache) and disassembled it directly with `llvm-objdump`. Confirmed
`AppleARMFunction::callFunction` is a thin shim: it reads back the
cached `provider` pointer and makes a virtual call through **the
provider's own vtable at byte offset `0x3a0` (slot 116)** --
i.e. `provider->callPlatformFunction(...)`. Dumped slot 116 on
`AppleT7000PerformanceController`'s real instance vtable (the fourth
pass's 80-slot dump never reached that far) and found a real,
substantial (1024-byte) in-kext function, `FUN_ffffff80031e921c` --
genuinely `callPlatformFunction`. Decompiled it in full: it dispatches
on four verbs (cached `OSSymbol*` globals) and, within one verb, on five
4-char magics including `KLCT` (`0x54434c4b`, byte order confirmed).
The `KLCT` case doesn't write a register directly -- it allocates a
small token/handle object whose own vtable (dumped and decompiled too)
turned out to be nearly all inherited `OSObject` boilerplate, no
clock-specific logic. A *different* verb in the same function (guarded
by a `"Warning, this clock was not disabled..."` string) walks a
128-bit gate bitmask and calls a shared per-gate primitive whose body is
completely legible: **every PMGR clock gate lives at `ioBase + 0x20000
+ gate_index * 8`, one 32-bit register per gate, bit 28 (`0x10000000`)
as the enable/disable bit, across a 101-entry table** (gate `0x44`
specially excluded from auto-disable) -- real, general, reusable
T7000/T7001 SoC knowledge. The exact gate index for `KLCT`/touch itself
wasn't found this pass: the per-magic constant tables that would answer
it read back as all-zero. Full detail in
`docs/plans/2026-09-09-j81-touch-spi3.md`'s "TOUCH-3, 2026-09-13 (fifth pass)".

**TOUCH-3, sixth pass, same day: `__DATA_CONST` theory was wrong, but
found the complete touch bring-up write sequence anyway.** Checked the
fifth pass's "re-extract `__DATA_CONST`" plan before doing it: this
kernelcache is a legacy pre-iOS-12 layout with **no `__DATA_CONST`
segment at all** (`otool -l` shows only `__TEXT`/`__DATA`/`__KLD`/
`__LAST`/`__PRELINK_TEXT`/`__PRELINK_STATE`/`__PRELINK_INFO`/
`__LINKEDIT`; `__PRELINK_TEXT`'s filesize exactly equals its vmsize, no
BSS gap). Directly hex-dumped the fifth pass's zeroed template-blob
address from the *original* kernelcache file at its exact computed file
offset: genuinely zero, not an extraction artifact (most likely a
`IOSimpleLock`-style object, correctly zero at rest -- not a missing
per-magic constants table). Corrected the fifth-pass writeup
accordingly rather than let the wrong claim stand.

Pivoted to a better lead instead: `AppleMultitouchSPI`'s own real
compiled code is present in this same ship kernelcache
(`0xffffff8002fb7000`, 320 functions, found by parsing `__PRELINK_INFO`'s
plist). Found the actual register-write sequence for touch bring-up,
completely independent of KLCT: a function identified by its own debug
string as `MTSPIBootloader::performCalibration` writes, via one generic
"write ASIC register" helper (vtable slot `0x8c0`): `ref-clk-div-addr/-val`,
`const-cal-addr/-val` (swapped for a raw field value when the chip
version read at the start isn't `0x434d11a0`), and -- only when its
address is non-zero -- `clk32-clock-enable-addr/-val`. A neighboring
function sets the hardcoded defaults (`clk32-clock-enable` defaults to
`0`/`0`, i.e. off, confirming the J82 personality's `0x10003518`/`1`
genuinely turns it on rather than reflecting a universal baseline).
This fully confirms, from real ship driver code rather than Info.plist
inference alone, the values the very first same-day pass already found.

**Net effect: the touch bring-up register sequence is now fully known
and reproducible. Only the separate, upstream PMGR gate index (`KLCT`)
remains an open number** -- and it's plausible that gate doesn't block
a real bring-up attempt (it may be a shared bus-level clock already
enabled once SPI3 itself is up), worth testing on hardware rather than
continuing to chase statically. Full detail in
`docs/plans/2026-09-09-j81-touch-spi3.md`'s "TOUCH-3, 2026-09-13 (sixth pass)".

**WiFi (PCIe): evidence-gathering phase complete, 2026-09-13, no code
yet.** Picked as the next focus over touch (no UI to exercise touch
input with yet; WiFi is independently useful). Decoded the real J81
ADT's `apcie` PCIe host controller node in full -- register windows,
GPIOs, DART, real PHY tunables, IRQ numbers -- cross-validated exactly
against this project's own earlier J82-derived predictions
(wake/CLKREQ/PERST GPIOs 165/174/179, 2.5 GT/s link speed, DART IRQ216).
Confirmed mainline's own Apple PCIe driver is the wrong SoC generation
(M1-only) and pulled the real structural reference (Corellium's
`pcie-hx.c`, H9P-family). Concrete staged plan, no hardware needed for
any of it, in `docs/plans/2026-09-13-j81-wifi-pcie.md`.

**D2207 GPIO2 write: confirmed byte-correct, no further live testing
justified, 2026-09-13 overnight.** Offline disassembly of the real
iPad5,3 iOS 8.1 kernelcache, cross-checked against unstripped iOS
10.0/10.3 `AppleD2207PMU`/`AppleDialogPMU`/I2C drivers, confirms the
earlier GPIO2 write (`03 e6 02`) was already exactly Apple's own
transaction -- right address, right function bits, no missing
CRC/bank-select/commit/unlock step. The one unlock sequence in this
driver family belongs only to an unrelated GPU test-mode routine;
GPIO/LDO code never reaches it. Conclusion: the earlier "ACK but no
effect" isn't a framing bug -- it's a runtime ownership/lock condition
invisible to static analysis. **Do not repeat the write or try
alternate byte patterns.** The only next experiment that adds evidence
is passive SDA/SCL logic-analyzer capture during a real iPadOS
Bluetooth toggle -- which needs a logic analyzer, running into the
standing no-new-hardware rule; flag this to Martin rather than assuming
it's fine.

**2026-09-21: tested and ruled out one specific new hypothesis** (not a
blind retry -- one controlled variable, evidence-backed, matching the
project's own bar): does charging's `0x0010` bit 2 act as a master
enable that gates whether GPIO2's write actually takes effect? Set
`0x0010` bit 2, retried the exact `03 e6 02` GPIO2 write -- **still
reverted to `0x00`, identical to every prior attempt.** `btattach`
still gets `hci0` (that's just UART3, independent of radio power) but
HCI commands still time out (`0xfc18 tx timeout`, `BCM: Reset failed
(-110)`). Restored both registers immediately; `0x04c0` (charging,
running at the time) confirmed untouched. Full record in
`docs/plans/2026-09-13-pmic-pcie-execution.md`.

**T7000 PCIe compile-only skeleton: staged and cross-build verified,
2026-09-13/14.** Added an inert `CONFIG_PCIE_APPLE_T7000` driver
(validates window/interrupt counts, returns `-EOPNOTSUPP`; no MMIO,
clocks, GPIOs, or link training) plus a `status = "disabled"` T7001 DT
node built from the real J81 `apcie` ADT data (12 register windows, 4
ports/IRQs, resolved `ranges` apertures, a `dart_apcie1` node). Wired
into its own isolated flake package
(`hoolock-pcie-check-kernel`) so it cannot affect the real boot
payload. The overnight pass left the actual cross-build pending (no
local `nix`, builder VM down); **verified clean the next day** once the
VM was restarted (`docs/build-infrastructure.md`'s documented
procedure): `nix build
.#packages.x86_64-linux.hoolock-pcie-check-kernel --no-link -L` exits
0, `pcie-apple-t7000.c` compiles, no errors. Full record in
`docs/plans/2026-09-13-pmic-pcie-execution.md`.

**T7000 PCIe: real link/enumeration driver implemented and cross-build
verified, 2026-09-21.** Picked up per the approved plan
(`/Users/martinp/.claude/plans/mighty-snuggling-cocke.md`), after the
same-day background research pass fully recovered the exact
`_enablePortHardware` register sequence (offsets, bits, confirmed
microsecond delays via a traced `_IODelay` call) and confirmed windows
2/4/6/8 are genuinely unused by Apple's own host path.
`kernel/patches/0018-pcie-apple-t7000-enumeration-test.patch` layers on
top of `0016` (same discipline as ANS1's `0012` on `0013`/`0014`/`0015`)
and rewrites the inert skeleton into a real, strictly bounded driver:
brings up board port 1 only, uses the kernel's own generic ECAM
(`pci_host_common_init()`) and -- verified directly against the real
pinned kernel source, not assumed -- its *already-built-in* generic
PERST-GPIO deassertion (`pci_host_common_parse_ports()` auto-finds a
`device_type = "pci"` child node's `reset-gpios`, no hand-rolled GPIO
code needed). CLKREQ and windows 2/4/6/8 stay untouched; MSI properties
dropped from this test's DT since the driver implements no MSI domain.
New isolated build (`kernel/hoolock-pcie-test.nix`,
`m1n1-hoolock-pcie-test`), mirroring `hoolock-ans1-test.nix` exactly --
built on the same proven patch stack as the real control payload, never
touching its own build.

**Cross-build verified**: `nix build
.#packages.x86_64-linux.m1n1-hoolock-pcie-test --no-link -L` produced a
complete real payload (confirmed by listing the actual Nix store
output, not just trusting the log) -- `Pongo.bin`, `m1n1.bin`,
`t7001-j81.dtb`, `Image.gz`, `initramfs.gz`, `m1n1-linux.bin`, real
`SHA256SUMS`. `dtc` prints 4 new advisory warnings for the added
`pci@0,0` node (3 generic PCI-bridge-schema warnings that don't apply to
a bare `reset-gpios` carrier node, 1 "not a phandle reference" warning
that's the exact same pre-existing class this DTS already emits for the
hardware-proven `gpio-keys` buttons) -- none block the build, zero
`error:` lines anywhere. **No hardware boot attempted -- explicitly out
of scope for this pass, a separate later decision.** Full record in
`docs/plans/2026-09-13-j81-wifi-pcie.md`'s "PCIe link/enumeration test:
implemented and cross-build verified" section.

**T7000 PCIe: first hardware attempts hang before reaching a console,
2026-09-21.** The user made the hardware-boot decision explicitly and this
became the next step. Real recipe (not `gaster`+`irecovery`, which is
documented-unreliable on this Mac -- see `docs/project-status.md`'s "Clean
DFU relaunch attempt"): vendored `boot/vendor/palera1n-macos-arm64
--pongo-shell --override-pongo ...` with the two-replug sequence. **Two
attempts** with the write-capable `m1n1-hoolock-pcie-test` payload both
hung: black screen, backlight on, no framebuffer console, no USB networking
(`172.16.42.1` unreachable, device dropped off USB entirely). **A control
test** with the unmodified, already-proven `m1n1-hoolock-control` payload
booted normally immediately after on the same pipeline -- rules out
host/cable/DFU flakiness. Reviewed the register-window math (index 9 is
correctly sized, not an off-by-one); two live suspects remained: the
`reset-gpios` pin identity (OIPG 179, never confirmed on hardware) and the
`power-domains = <&ps_pcie>` power-up the DT status flip triggers
automatically during probe. Rewrote `0018` into a supposed **read-only
diagnostic** and observed the same hang, but a subsequent source review
corrected that conclusion: it still mapped shared MMIO/ECAM and entered the
generic PCI probe. The first build also never called the separate
`pci_host_common_parse_ports()` helper, so PERST was not deasserted, and it
omitted Apple’s DART ordering, port tunables, and final link-start write.
Do **not** rerun either existing PCIe payload or spend a boot on a standalone
DART probe: the stock DART driver resets the block before the recovered Apple
order makes it active. First recover PCIE/AUX/REF gate ownership and
`function-dart_force_active`, then make a true PMGR-only no-MMIO test. Full
record in `docs/plans/2026-09-13-j81-wifi-pcie.md`'s "Post-attempt
implementation review" section.

**T7000 PCIe: PMGR-only test hardware-verified clean, 2026-09-23.**
Independently re-verified the "PERST never deasserted" claim above against
the real pinned `pci-host-common.c` source directly (fetched from GitHub at
the exact locked rev) -- confirmed accurate: `pci_host_common_init()` never
calls `pci_host_common_parse_ports()`; that helper is opt-in only.
Implemented the review's proposed next step: `kernel/patches/0019-...`
(layered on `0016`, a clean branch, not on top of `0018` -- `0018` stays as
a record of the earlier inconclusive attempts). The driver's `probe()` does
nothing but `dev_info()` and return; the DT flips only `pcie` to `"okay"`
(`dart_apcie1` stays disabled) and drops `iommu-map` so DART is never even
looked up. New isolated build (`kernel/hoolock-pcie-pmgr-test.nix`,
`m1n1-hoolock-pcie-pmgr-test`). Cross-build verified after a real
infrastructure detour: the Linux-builder VM's disk was corrupted by an
earlier hard-kill and wouldn't boot at all for about a day across many
restart attempts; recreated it from scratch (Martin's explicit go-ahead --
~43 GB of disposable cached build state, not project work) and the guest
came back up cleanly.

**Hardware result: boots exactly like the unmodified control payload** --
postmarketOS, working USB networking (`172.16.42.1`, 0% ping loss), debug
shell reachable by telnet, and `dmesg` confirms the probe actually ran
(`t7000-pcie pmgr-only-test: probe reached (no MMIO, no PCI core, no
DART)`). This is the first PCIe-node hardware result that isn't a hang. It
rules out the `status = "okay"` DT flip and the automatic
`power-domains = <&ps_pcie>` genpd power-up as causes on their own. The
real suspect is now narrowed to `pci_host_common_init()`'s ECAM mapping /
generic PCI bus scan, which this working test deliberately never calls but
both hanging `0018` attempts did. Next diagnostic step (not yet attempted):
a single bounded shared-window MMIO read, still without ever calling
`pci_host_common_init()` or mapping ECAM. Full record in
`docs/plans/2026-09-13-j81-wifi-pcie.md`'s "PMGR-only test: hardware-verified
clean" section.

**T7000 PCIe: bounded shared-window read test also hardware-verified clean,
2026-09-23.** Implemented `kernel/patches/0020-...` (layered on `0016`, a
clean branch like `0019`): `probe()` maps only the shared register window
(reg index 9) via `devm_ioremap_resource()`, does one bounded `readl()` at
board port 1's LTSSM-start offset, logs it, returns -- no ECAM, no PCI
core, no DART. Cross-build verified clean. **Hardware result: boots
exactly like every other clean payload so far** -- postmarketOS, working
USB networking, and `dmesg` confirms the whole sequence including the
actual read: `window 9 at [mem 0x600000000-0x600001fff]` (matches the DT
`reg` entry exactly) then `port 1 ltssm=0x00000000` -- a sane "not yet
enabled" value, not a bus fault. This rules out the shared-window MMIO
access itself as a cause. Two clean tests in a row (`0019`, `0020`) now
leave only `pci_host_common_init()`'s remaining two pieces as suspects --
ECAM mapping and the generic PCI bus scan -- both of which the hanging
`0018` attempts called and neither working test does. Next diagnostic
step (not yet attempted): a bounded ECAM-only read, still without the
generic bus scan. Full record in `docs/plans/2026-09-13-j81-wifi-pcie.md`'s
"Bounded shared-window read test: hardware-verified clean" section.

**T7000 PCIe: bounded ECAM-window read test also hardware-verified clean,
2026-09-23.** Implemented `kernel/patches/0021-...` (layered on `0016`,
same clean-branch pattern as `0019`/`0020`): `probe()` maps only the ECAM
config-space window (reg index 0) via `devm_ioremap_resource()`, does one
bounded `readl()` at config offset 0, logs it, returns -- no
`pci_ecam_create()`, no `pci_ops`, no `pci_host_probe()` bus scan, no DART.
Cross-build verified clean. **Hardware result: third clean payload in a
row** -- postmarketOS, working USB networking, and `dmesg` confirms the
window mapped exactly where expected (`0x610000000`, `0x1000000` bytes)
and the bus0/dev0/fn0 config-space read returned `0xffffffff` -- the
correct, ordinary "no device present" response, not a fault.

Three clean tests in a row (`0019`, `0020`, `0021`) now rule out the DT
status flip, the power-domain attachment, the shared-window MMIO access,
and a single ECAM read as causes. Only `pci_host_probe()`'s full generic
bus scan is left untested. Leading hypothesis, not yet a conclusion: `bus-
range = <0 4>` means a full scan walks far more of the declared 16 MiB
ECAM window (multiple buses, many device/function slots) than this test's
single offset-0 read did -- if only part of that window is genuinely
mapped/safe silicon, a full scan would reach the rest while one bounded
read at the very start would not. Next diagnostic step (not yet
attempted): a handful of additional bounded reads at other ECAM offsets
(a higher bus number, and/or the exact device/function slot the real ADT's
`pci-bridge1` occupies) to try to localize a bad region before ever
re-running the full generic bus scan, which would just reproduce the
original hang without saying where in the address space it happens. Full
record in `docs/plans/2026-09-13-j81-wifi-pcie.md`'s "Bounded ECAM-window
read test: hardware-verified clean" section.

**T7000 PCIe: multi-offset ECAM read test also hardware-verified clean,
2026-09-23.** Implemented `kernel/patches/0022-...` (layered on `0016`,
same clean-branch pattern): to avoid a separate hardware round per offset,
`probe()` reads three points in one boot -- bus 0 (repeated sanity anchor),
bus 1 (the leading suspect for board port 1 under standard ECAM
addressing), and bus 4 (the boundary edge) -- each independently logged.
Cross-build verified clean. **Hardware result: all three reads succeeded,
no hang** -- postmarketOS, working USB networking, `dmesg` confirms every
step including all three reads returning `0xffffffff` cleanly (bus 0, bus
1, bus 4).

This **rules out the "unsafe region" hypothesis entirely** -- bus 1 (the
real suspect) and bus 4 (the boundary) are exactly as safe as bus 0. Every
raw MMIO read tried anywhere on this controller across four tests (`0019`
shared-window read, `0021` ECAM offset 0, `0022` ECAM at three bus
offsets) is safe. Sharper hypothesis now: `pci_host_common_init()` sets
`pci_add_flags(PCI_REASSIGN_ALL_BUS)` before calling `pci_host_probe()`,
and generic PCI enumeration performs *writes* as part of standard resource
discovery (BAR-sizing: write all-1s to a BAR, read back the size mask;
bus-number programming while walking bridges) that no read-only test has
exercised. The real suspect may not be "touching ECAM" at all, but
specifically the write side of generic enumeration, or some other piece of
`pci_host_probe()`'s logic a handful of plain reads can't reach. Next
diagnostic step (not yet attempted): call `pci_host_common_init()` itself
in complete isolation from everything else `0018` also did (no register
writes, no PERST/GPIO, no DART/iommu-map) to test that one remaining code
path directly. Full record in `docs/plans/2026-09-13-j81-wifi-pcie.md`'s
"Multi-offset ECAM read test: hardware-verified clean" section.

**T7000 PCIe: isolated pci_host_common_init() test hardware-verified
clean -- investigation conclusively narrowed, 2026-09-23.** Implemented
`kernel/patches/0023-...` (layered on `0016`, same clean-branch pattern):
`probe()` calls `devm_pci_alloc_host_bridge()` + `pci_host_common_init()`
with a bare ECAM ops struct and nothing else -- no shared-window writes,
no PERST/GPIO, no DART. This is the exact code path both hanging `0018`
attempts called. Cross-build verified clean. **Hardware result: boots
cleanly, `pci_host_common_init()` returns 0** -- postmarketOS, working USB
networking, `dmesg` shows the full generic PCI probe running to
completion (host bridge ranges parsed, ECAM mapped for buses 00-04, "PCI
host bridge to bus 0000:00" logged, clean return).

**This clears the generic PCI path, but not DART.** Five clean hardware
tests (`0019`-`0023`) verify the DT status flip, power-domain attachment,
the shared-window read at `0x860`, ECAM mapping/reads, and generic PCI bus
scan. All intentionally kept `dart_apcie1` disabled and removed
`iommu-map`; both hanging `0018` variants enabled them. Read-only `0018`
also read four shared offsets that `0020` did not isolate. The remaining
differences are therefore DART/IOMMU activation, those four passive reads,
and the shared-window enable writes. Do not stage writes now. First run the
four missing reads sequentially with DART still disabled; then recover
`function-dart_force_active` and PCIE/AUX/REF gates before a DART-only test.
Full record in `research/t7000-pcie-hardware-findings.md`.

**T7000 PCIe: remaining shared offsets test hardware-verified clean --
the passive-read gap is fully closed, 2026-09-23.** Implemented
`kernel/patches/0024-...` (layered on `0016`, same clean-branch pattern):
reads port 1's `REFCLK_EN` (`0x180`), `PERST_INTERNAL` (`0x188`), the
undocumented `0x18c`, and `LINK_ENABLE` (`0x198`) -- the port-stride-
adjusted registers read-only `0018` read but `0020` never independently
isolated (`0020` only re-checked the LTSSM register). Still DART-disabled,
no `iommu-map`, no ECAM, no writes. Cross-build verified clean. **Hardware
result: boots cleanly, all four reads succeed** -- postmarketOS, working
USB networking, `dmesg` shows real, non-trivial "at rest" values:
`refclk_en=0x11010100`, `perst_internal=0x00000100`, `unknown_10c=
0x00000001`, `link_enable=0x00000000`. Each is at least loosely
consistent with the recovered `_enablePortHardware` sequence's own
behavior on that register (e.g. `link_enable` and `0x10c` match the
sequence's first-step clear/no-op state).

**Every register either hanging `0018` driver ever read is now
independently confirmed safe, and so is the complete generic PCI bus
scan.** Six clean hardware tests in a row (`0019`-`0024`) all kept DART
disabled and removed `iommu-map`; both hanging `0018` attempts enabled
them. **DART is now the sole remaining common difference.** Next is a
research task, not a hardware test: recover Apple's
`function-dart_force_active` semantics and the PCIE/AUX/REF power-gate
operations from the real iOS kernelcache, before attempting a DART-only
hardware probe (DART enabled, PCIe inert, no IOMMU consumer). Full record
in `research/t7000-pcie-hardware-findings.md`.

**T7000 PCIe: `function-dart_force_active`/gate semantics recovered offline
-- corrects the documented call order, 2026-09-23.** Ghidra analysis of
`AppleEmbeddedPCIE.kext` and `AppleS5L8960XDART.kext` (same pinned iPad5,3
12B410 kernelcache) using a Ghidra project reused from an earlier session
(PRELINK_TEXT already imported, no fresh ~10 min import needed). Found and
decompiled `AppleEmbeddedPCIEPort::enableGated()` -- its confirmed order is
power gate → clock gate → **`function-dart_force_active(true)`** →
(optional NVMe-MMU force-active) → wait for gate active → conditional
setup → **only then** the first shared-window register writes. This
**corrects the earlier documented assumption** that DART force-active
happens after port hardware setup -- it's actually one of the very first
steps, before the driver even confirms the gate is active.

On the DART side, `AppleS5L8960XDART::_forceAvailable(bool)` sets an
internal flag and calls `_updateAvailability()`, which only actually uses
that flag if `_manualAvailabilityEnabled` is already true -- otherwise it
silently ignores the forced value and re-derives availability from
registered IOMMU mapper activity (of which there'd be none yet). Where
that flag gets set was not traced this pass -- a real open gap. Separately,
`power-gates`/`clock-gates` are never referenced by name in the PCIe port
driver -- only one gate index (`power-gates`, `57`) is ever used by the two
gate-enable calls -- implying `PCIE_AUX`/`PCIE_REF` (`58`/`56`) are walked
automatically by the underlying PMGR machinery, not explicit driver code.
Whether Linux's `power-domains = <&ps_pcie>` binding (already proven clean
by `0019`) covers all three gates the same generic way is unverified and
should be checked against the Hoolock kernel's own PMGR/genpd source.

**Not yet done**: locating the `_manualAvailabilityEnabled` setter, and
confirming `ps_pcie`'s real gate coverage. A DART-only Linux hardware test
is next, once those are resolved or explicitly accepted as open risk.
Full record in `research/t7000-pcie-hardware-findings.md`'s
"`function-dart_force_active` and gate semantics, recovered 2026-09-23"
section.

**T7000 PCIe: DART-enable test hangs on real hardware, 2026-09-23.**
Implemented the corrected two-test plan from the section above:
`kernel/patches/0025-...` (test 1, DART enabled, no `iommu-map`) and
`kernel/patches/0026-...` (test 2, `iommu-map` restored), both layered on
`0016` with `0019`'s exact inert PCIe probe unchanged -- only `dart_apcie1`'s
DT status differs. `CONFIG_APPLE_DART` was already `=y`. Both cross-build
verified clean and built alongside each other (`result` = test 1,
`result-dart-b` = test 2, staged ahead of time so no second build wait is
needed), but per the plan's own conditional gate only test 1 was run first.

**Hardware result: test 1 hangs.** Same DFU/palera1n recipe as every prior
round. The iPad showed the normal m1n1 logo/sequence, then went to a black
screen with only the backlight on -- no console text at all, unlike all six
prior clean tests. Polled USB enumeration and `ping 172.16.42.1` for 30+
seconds after handoff: neither ever came up. Same observable signature as
both original `0018` hangs. Since `0019`'s PCIe PMGR-only node is
independently proven clean six times over and unchanged in this test, the
fault isolates to `dart_apcie1` alone -- the stock Linux `apple-dart`
driver's real probe (register map, IRQ registration, and most likely its
reset step, the first actual register touch).

**ADT follow-up corrects the gate hypothesis.** The saved J81 ADT is already
textual: `dart-apcie1` has no `power-gates` or `clock-gates` property. It
does have `manual-availability = 1`, directly matching the recovered
`_manualAvailabilityEnabled` DART field. Do not add or probe AUX/REF domains
next. Recover the `manual-availability` setter and `_updateAvailability()`'s
"become available" handler in `AppleS5L8960XDART`; the stock Linux driver's
immediate reset likely violates that Apple availability order.

**Availability setter now recovered, 2026-09-23.** Focused Ghidra analysis
of the exact 12B410 `AppleS5L8960XDART.kext` proves its only
`manual-availability` reference is the initializer, which stores the
non-zero ADT value directly at `_manualAvailabilityEnabled` (`+0xf5`). Its
`tcaF` platform-function selector calls `_forceAvailable(bool)`, which
stores `+0xf6` and invokes virtual slot `+0x610`. A focused import including
the adjoining `IODARTFamily` code confirms that the call remains a true
virtual dispatch. The unresolved work is now runtime vtable/superclass
resolution and its first hardware action. Do not run `0026` or add another
DART payload before that evidence exists.

**Superseded (kept for the record):** the paragraph above originally
speculated an AUX/REF PMGR-gate cause. The captured J81 ADT is textual and
directly disproves it -- `dart-apcie1` has no `power-gates`/`clock-gates`
property at all; it has `manual-availability = 1` instead, matching the
recovered `_manualAvailabilityEnabled` field. See the two entries below for
what actually explains the hang.

**Availability transition fully decompiled, 2026-09-24.** Picked up
exactly where the entry above stopped: resolved the virtual `+0x610`
target. It's `_updateAvailability()` itself -- found directly via its own
pretty-function string (`FUN_ffffff80026c49b8`, one xref, no constructor
tracing needed). Decompiled in full: with `manual-availability` set (true
here), it takes `_forceAvailable`'s forced flag directly (skipping the
mapper-poll fallback), compares it against a cached state, and on a change
dispatches one of two further virtual calls -- `+0x5d8` on becoming
available, `+0x5d0` on becoming unavailable. Found the real instance
vtable by scanning process memory for the already-known
`_updateAvailability` pointer at its confirmed offset (one clean,
unambiguous match at `0xffffff80026c7140`), then read both slots directly
-- both resolve to concrete functions inside the same kext, no superclass
tracing needed after all.

**Become available**, decompiled: asserts not-yet-available and the lock
held, then calls **two enable-flagged operations on a cached helper
sub-object** (object offset `0xe8`) -- the same two-call shape already
established for the PCIe port's own `enableGated()` (power gate, then
clock gate). Only *after* that does it mark itself available and enable
its own interrupt event source(s). Become-unavailable is the exact
mirror (disable IRQ first, release the same two gates last). **This gives
a concrete mechanism, not just a corrected guess**: Apple's DART has its
own dedicated availability state machine that requests its own power/clock
gate as part of becoming available; the stock Linux `apple-dart` driver has
no equivalent concept at all and resets the unit unconditionally on probe
with no gate of its own ever requested (`dart_apcie1` has no
`power-domains` property). If the DART's own gate is genuinely required
before any register access lands, that fully explains the observed hang.
**Helper object identified, 2026-09-24: `AppleARMPerformanceController`.**
Found by where it lives rather than chasing the unreadable on-disk
`OSSymbol*` chain further: the cached lookup target's address falls inside
`com.apple.driver.AppleARMPlatform`'s load range in the pinned kernelcache
(cross-checked via `ipsw kernel kexts -j`) -- the same kext this project's
TOUCH-3 investigation already opened for the `KLCT` gate trace, and one
~30 other kexts also reference, confirming a widely shared utility class.
Fetched a real unstripped `AppleARMPlatform.kext` (different build, same
technique TOUCH-3 used for `KLCT`) from
`github.com/userlandkernel/ios-unstripped-kexts` and read its real symbols
with `nm`: `AppleARMPerformanceController::enableDeviceClock(unsigned long,
unsigned long)` and `::enableDevicePower(unsigned long, unsigned long,
unsigned long*)` -- a 2-arg and 3-arg method matching `+0x560`/`+0x568`'s
call shapes exactly, in the same order. This is the same
performance-controller family already partially reverse-engineered for
touch's `KLCT` (`ioBase + 0x20000 + gate_index*8`, bit 28 enable, 101-entry
table).

**Conclusion, now solid**: the DART requests its own clock and power gate
through the SoC-wide performance-controller framework -- the same one
touch's `KLCT` uses -- not through `ps_pcie`/`PCIE_AUX`/`PCIE_REF` at all.
Linux's current DT and driver have no representation of this gate-request
path whatsoever; it isn't a "missing power domain," it's a different
mechanism entirely. Call-site arguments are readable: become-available
calls `enableDeviceClock(1, 0)` then `enableDevicePower(1, 0, 0)`;
become-unavailable calls the same two with `0`. First arg tracks
availability directly; second arg (constant `0`) is most likely a
device/gate-index selector, not yet confirmed against a physical register.
**Physical register: four independent techniques tried, genuinely not
resolved, 2026-09-24.** After the first three static-analysis attempts
(vtable-offset math, string-xref, function-cluster search) each hit a
wall, ran a real (not `-noanalysis`) Ghidra auto-analysis pass scoped to
just `AppleARMPlatform.kext` + `AppleT7000.kext` (12 seconds, not the
~10 minutes a full-image re-analysis would cost). It confirmed the
earlier function boundaries were already correct -- ruling out "bad
analysis" as the explanation, and revealing the earlier `+0x560`/`+0x568`
identification itself was likely wrong (the confirmed 2-parameter shape
at `+0x568` doesn't match `enableDevicePower`'s 3-parameter signature).

Pivoted to the real, unstripped reference binary and disassembled
`enableDeviceClock`/`enableDevicePower` directly by symbol name
(`llvm-objdump --disassemble-symbols=...`, no decompiler ambiguity).
**Both are thin delegating shims, confirmed byte-for-byte**: each checks
its own presence flag, then forwards to a *shared cached delegate object*
via the *same* vtable slot (`+0xe0`) for both clock and power requests.
This is genuine new architectural insight -- the real gate toggle lives in
a separate delegate object, not inside `AppleARMPerformanceController`
itself -- explaining the earlier "unsupported stub" finding exactly (the
shared fallback when no delegate is configured). A similar
delegate-dispatch shape exists in our own kernelcache too, but wasn't
confirmed as these exact methods (different field offset, mismatched
argument count).

**Do not treat any offset from this investigation as confirmed** -- they
are leads, not conclusions. Four independent techniques across two
research passes have narrowed the picture (mechanism, class, and now the
delegate architecture are solid) without landing on the final register.
Matching this project's own TOUCH-3 precedent, **not pursuing this
further via static analysis alone.** Still do not run `0026` or build
another DART payload. Full record in
`research/t7000-pcie-hardware-findings.md`'s "Scoped auto-analysis pass
and real-symbol disassembly" section.

**DART helper review correction, 2026-09-24.** The manual-availability
state-machine and its ordered helper calls are proven. The helper is *not*
proven to be `AppleARMPerformanceController`: a reference binary maps the
same `+0x560`/`+0x568` slots to `AppleARMIODevice` gate-wrapper methods,
which use a provider's `clock-gates`/`power-gates` arrays. J81's PCIe DART
has neither property. Treat the helper class, its return values, the
physical gate, and the claim that it is independent of PCIe PMGR domains as
open. Trace the 12B410 `+0xe8` store and then hook `+0x5e8` if the calls are
unsupported; do not run `0026` or build another DART payload yet. Full
record: `research/t7000-pcie-hardware-findings.md`.

**DART helper resolved, later 2026-09-24.** Exact 12B410 tracing proves
`+0xe8` is the DART provider cast to `AppleARMIODevice`; its `+0x560` and
`+0x568` calls are `clock-gates[0]`/`power-gates[0]` wrappers. J81 declares
neither array, both return unsupported, and Apple ignores both. The first
remaining hardware path is `_dartRecoverFromPowerdown()`: Apple writes
`0x0020ffff` to DART `+0x24` and restores state before Linux first reads
`+0x00`. Implement and cross-verify only an evidence-gated first-write
payload next; do not run it or `0026` until hardware testing is requested.

**Recovery-write evidence gate implemented and cross-build verified,
2026-09-24.** `kernel/patches/0027-...` layers on `0016` like every prior
DART/PCIe test: `pcie` is `0019`'s unchanged inert probe, `dart_apcie1`
stays enabled but its `compatible` is redirected to a new
`"apple,t7000-dart-recovery-test"` string so the stock `apple-dart` driver
(proven to hang in `0025`) can never bind to this node. A new dedicated
driver maps the DART's register window, writes `0x0020ffff` to offset
`0x24` (Apple's exact recovered formula), logs before/after, and aborts
probe -- nothing else. New isolated build
(`kernel/hoolock-pcie-dart-recovery-test.nix`,
`m1n1-hoolock-pcie-dart-recovery-test`). **Cross-build verified clean**:
exit 0, complete payload, only the same benign pre-existing `dtc`
warnings -- and verified beyond the exit code, matching this project's
standard: the built DTB's strings carry the new compatible string (not
the real DART one), and the kernel's `System.map` has the new driver's
probe/init/exit symbols and driver struct, confirming it's genuinely
compiled and linked in. `result` now points to this payload.
**`0027` hardware result: hangs -- an informative negative result,
2026-09-24.** Same signature as `0018`/`0025`: black screen, no USB
re-enumeration, no networking over 30+ seconds, reconfirmed after a
replug. This is more informative than a repeat: `0027`'s driver performs
*only* a write to `DART+0x24`, no read at all -- if the hang were about
read-before-write ordering, this should have been clean. It wasn't. The
most consistent reading is that essentially any MMIO touch to the DART's
register window hangs, regardless of operation order. That reopens the
power/clock-gating question through a **different, never-tested**
mechanism than the disproven `AppleARMIODevice` gate-wrapper theory:
`dart_apcie1` has no `power-domains` property of its own anywhere in the
DT (only `pcie` has one, `<&ps_pcie>`). Whether the DART's own MMIO window
needs an explicit `power-domains` reference has never actually been
tried on hardware. **Do not build or run another DART payload without an
explicit go-ahead** -- `0026` stays untested and doubly premature now.
Full record in `research/t7000-pcie-hardware-findings.md`'s "`0027`
hardware result: hangs" section.

**Domain-gate plan implemented and cross-build verified, 2026-09-24.**
Three new patches matching the ordered plan exactly: `0028` (Test A,
`0027`'s driver unchanged plus `power-domains = <&ps_pcie>` directly on
`dart_apcie1` -- tests the real genpd-ordering guarantee a device's own
domain reference gives, which `pcie`'s reference never provided for the
DART's own probe), `0029`/`0030` (Tests B1/B2, a new no-MMIO logging
driver mirroring `0019`'s inert probe exactly, with `ps_pcie_aux`/
`ps_pcie_ref` respectively -- never combined, never with `ps_pcie`). All
three layered directly on `0016`, independent branches, same
reconstruct/diff/verify methodology as every prior patch. **All
cross-build verified clean**: exit 0, complete payloads; verified beyond
the exit code (DTB strings carry the correct compatible string per test,
`System.map` has each driver's probe symbol and driver struct). `0029`/
`0030` are built and staged ahead of time but must not run on hardware
unless Test A hangs. `result` points to Test A.

**Test A hardware result: clean -- the hang is resolved, 2026-09-24.**
postmarketOS visible, USB networking up (0% ping loss), debug shell
reachable. `dmesg` confirms the DART write to `+0x24` completed in 14
microseconds and boot continued normally -- the exact same driver and
write that hung in `0027`, the only change being `dart_apcie1` gaining
its own `power-domains = <&ps_pcie>` reference. **This resolves the
investigation**: not a missing AUX/REF gate, not read-before-write
ordering -- genpd power-up ordering is scoped per consumer device, and
`pcie`'s own `power-domains` reference never guaranteed `ps_pcie` stayed
powered for the DART's own, later probe. `ps_pcie_aux`/`ps_pcie_ref` were
never the answer; **Tests B1/B2 (`0029`/`0030`) are no longer needed and
should not be run.** Natural next step, not yet built: restore the stock
`apple-dart` driver on `dart_apcie1` (undo the test compatible redirect)
while keeping `power-domains = <&ps_pcie>` -- effectively `0025` with this
one fix. Full record in `research/t7000-pcie-hardware-findings.md`'s
"Test A (`0028`) hardware result: clean" section.

**Buttons hardware-verified, 2026-09-21.** `evtest /dev/input/event0` on
the existing `gpio-keys` device captured clean press/release events for
Home (`KEY_HOMEPAGE`), Power, Volume Up and Volume Down. No driver work
needed; item closed.

**CHG-1 hardware-verified, then CHG-2 traced to a real write path,
2026-09-21.** The read-only D2207 charger observer confirmed live
hardware: `MATCH` on both `input_current_limit` (100 mA, raw `0x04c0 =
0x02`) and `constant_charge_current_max` (3 A, raw `0x04cf = 0x3c`); the
gauge read `Discharging` at the time. Martin confirmed the same
cable/connector charges normally under stock iPadOS and owns no USB
power meter, so investigation stayed entirely software-only. Two live
checks ruled out the obvious theory: the USB gadget is fully
`configured` at `high-speed` right now (not stuck unconfigured), and
this kernel has zero charger-detection code at all --
no `/sys/class/extcon`, no `/sys/class/typec`, zero `dmesg` lines
matching charger/extcon/role-switch, a charger DT node with only
`compatible`+`name`. **Conclusion: nothing in Linux has ever attempted
to raise the current limit; 100 mA is almost certainly the D2207's
untouched power-on default**, not a live detection result.

Re-extracted the same iPad5,3 12B410 kernelcache
(SHA-256 `19c277d60e0a1185b1e4a1b72cda4f1f550c0b0bf670791542234a6dbbcc28bf`,
matching every prior use this project) and disassembled
`AppleD2207PMU.kext` (`0xffffff8002b44000`, found via its own
`CFBundleIdentifier` declaration, not a dependency reference -- a looser
substring search this same session initially grabbed the wrong kext's
address; caught and corrected by checking actual string content, not
just trusting the plist parse). Class `AppleD2207PMUPowerSource`'s
current-limit setter (`0xffffff8002b4c574`) **reads `0x04c0`, clamps a
target through Apple's classic charger-ID tiers (100/500/1000/2100/2400
mA, each derated a few percent -- matches the found log strings
`p1000 = %d, p500 = %d` / `p2100 = %d, p2400 = %d` / `target = %d,
adjusted = %d` exactly), and writes the byte back to `0x04c0`** via the
same read/write I2C vtable ABI (`+0x5a8`/`+0x5b0`) already established
for GPIO2. A neighboring decode helper was initially (wrongly) assumed
to be `0x04c0`'s own byte-decode formula -- **corrected by the live
test below: that helper actually reads `0x04cf`
(`constant_charge_current_max`), a different register.** `0x04c0`'s
real formula is the one `boot/ipad_console.py`'s observer already used
(`code >= 0xfe ? 3262 : 75 + (100*code+7)//8`, mA), now independently
confirmed live. A second helper in the same call path toggles bit 2 of
register `0x0010`. Its public unstripped symbol is
`setCurrentLimitSuspend`; setting the bit suspends USB input current, and
the conversion helper requests it only for targets below 75 mA.
(Xcode.app's own `llvm-objdump`/`otool`/`strings` are gated behind an
unaccepted license on this Mac -- worked around by invoking
`/Library/Developer/CommandLineTools/usr/bin/<tool>` directly, a
separate, unaffected install; flag the license prompt to Martin if it
matters for anything else.)

**Live write test, same day: it works.** Martin authorized a single,
small, reversible, monitored write of `0x04c0` specifically (not the
`0x0010` bit -- untested). Baseline: `0x04c0=0x02`, sysfs `100000`,
gauge `Discharging` at `-689000` uA. Wrote
`i2ctransfer -f -y 0 w3@0x3c 0x04 0xc0 0x0a` (same transaction shape as
GPIO2). Immediate readback: **`0x0a` -- the write took and persisted,
unlike GPIO2's ACKed-but-unchanged result.** Sysfs decoded it to
`200000` uA, matching the corrected formula exactly. More significantly:
the gauge's discharge current **dropped to `-567000` uA**, a real ~120
mA change in measured battery current, not just a changed register.
Restored to `0x02` immediately after; readback, sysfs, and `dmesg` all
confirmed clean restoration, no errors throughout. **This is the first
live PMIC write this project has found to actually take effect on real
J81 hardware** -- doesn't by itself prove full charging (`STATUS`
stayed `Discharging`, `0x0010` untouched at this point), but establishes
`0x04c0` as a real, live, AP-writable register with a measurable
power-behavior effect.

**Then tested `0x0010` bit 2 the same way, same day -- writable, but not
confirmed as charge-enable.** Isolated from `0x04c0` (reread and
confirmed `0x02` throughout, so any effect is attributable to this one
register alone). Baseline `0x00`; wrote `0x04` (set bit 2, same
transaction shape); readback confirmed it took and persisted, same as
`0x04c0`. But the effect went the wrong way: `STATUS` stayed
`Discharging` throughout, and discharge current *increased*
(`-709000` -> `-809000` uA, ~100 mA more draw, not less) -- then settled
back to baseline (`-701000` uA) within 8s of restoring to `0x00`, good
evidence the bump really was caused by the write, not coincidence.
**Corrected interpretation after resolving the unstripped symbol:** this is
the USB input-current suspend bit. The extra ~100 mA of battery discharge is
the loss of the approximately 100 mA USB contribution, not a newly enabled
load. Clear permits input according to `0x04c0`; set suspends it.

**Then tried both registers together, same day -- combination is worse
than `0x04c0` alone, not better.** Baseline confirmed clean
(`0x04c0=0x02`, `0x0010=0x00`, `-705000` uA). Wrote both in Apple's own
call order (enable bit, then current limit): `0x0010<-0x04` then
`0x04c0<-0x0a`, both took and persisted, sysfs correctly decoded `0x0a`
to `200000` uA. But `STATUS` stayed `Discharging`, and current sat at
`-809000`/`-808000` uA -- **matching the `0x0010`-alone result, not the
improved `-567000` uA seen with `0x04c0` alone.** The bit's quiescent
penalty looks like it dominates regardless of current-limit setting,
rather than the two effects adding toward charging. Restored both in
reverse order; clean readback on both, sysfs back to `100000`, current
settled to `-701000` uA eight seconds later, `dmesg` clean throughout
all three tests.

**Net result of all three live tests: `0x04c0` alone helps (~120 mA less
draw); `0x0010` bit 2 alone hurts (~100 mA more draw, no `STATUS`
change); together, roughly cancel out. Nothing tried produced an actual
`Charging` transition.** Whatever really triggers charging -- if
software-controlled at all, rather than autonomous D2207 hardware gating
independent of both these registers -- remains unidentified.

**Caller trace: genuinely exhausted, same day.** Set up the same
full-`__PRELINK_TEXT` Ghidra project used for KLCT and asked
`ReferenceManager.getReferencesTo()` who calls the setter. Found exactly
one reference -- the vtable's own data slot -- and **zero references to
that vtable slot from anywhere in the 14 MB region.** The calling object
gets its vtable pointer from something not resolvable to a static
constant (almost certainly obtained dynamically at runtime, the same
dead-end shape touch's fourth pass hit). Not answerable from this
kernelcache's disassembly alone.

**Breakthrough, same day: real `Charging` achieved with one register.**
Martin proposed raising `0x04c0` clearly above the measured drain instead
of continuing to chase the caller. Wrote `0x04c0 = 0x4a` (1000 mA,
`0x0010` deliberately left untouched this time). **`STATUS` transitioned
to `Charging` immediately** -- current went positive (`+44000` uA rising
to `+76000` uA over the next minute), voltage rose in step, temperature
held flat at 33.6-33.7 C throughout. **The 100 mA default was never a
detection failure -- it was simply too low a ceiling for input current
to ever exceed system draw.** No `0x0010`, no other register, no Apple
driver code path needed at all.

**Currently left charging on Martin's explicit standing instruction**:
keep `0x04c0` at `0x4a` until the next test step, a safety concern, or
temperature reaches 42 C -- whichever comes first -- and **automatically
restore to `0x02` the instant capacity reaches 80%** as a conservative
cutoff. Monitored on a recurring check-in basis (not continuous polling);
full running log with each observation in
`docs/plans/2026-09-13-pmic-pcie-execution.md`'s "Charging monitor log".
If you're picking this thread up in a later session: check that log
first for the latest state before assuming what `0x04c0` is currently
set to.

**Automatic charging plan approved and Stage 0/1 implemented, same day.**
Full plan at `/Users/martinp/.claude/plans/mighty-snuggling-cocke.md`.
Stage 0 (live, no code): tested whether `0x0010` bit 2 is a Bluetooth
master enable -- **ruled out**, GPIO2's write still didn't persist even
with it set, HCI commands still timed out. Stage 1 (built and shipped):
`boot/ipad_console.py` has a new "Charging: switch current tier" action
(100/500/1000/2100/2400 mA + custom), reusing the exact validated
`0x04c0` formula, never touching `0x0010`, with a 42 C thermal abort and
automatic restore to `0x4a` (the validated resting state, not Apple's
factory `0x02`) baked in. Two offline tests added
(`boot/test_ipad_console.py`); both pass. **Live-validated against real
hardware**: selected 500 mA, watched it poll for 30s (dropped to
`Discharging` -- 500 mA alone isn't quite enough right now), declined to
keep, watched it auto-restore to `0x4a`, confirmed `Charging` resumed at
`+68000` uA five seconds later.

**Higher tiers validated, same session: 2100 and 2400 mA both clean.**
Ran both through the new tool. Both: voltage held essentially flat with
no droop (`2400` mA's poll window showed `3781000` uA unchanged for the
full 30s), current stable ~100-115 mA net charging, temperature flat at
33.3 C, no USB link instability, `dmesg` clean. Net charging current did
**not** meaningfully increase from 1000 to 2100 to 2400 mA -- all landed
in the same ~100-115 mA band, suggesting the battery's own
charge-acceptance rate, not the input-current ceiling, is the real
bottleneck once it clears system draw. **All five planned tiers now
validated live; currently running at 2400 mA by explicit choice.** Stage
2 (kernel-level writable sysfs property, `kernel/patches/0017-...`) is
now well-motivated by a complete sweep, not started -- pick that up next
if asked to continue this thread. Full record in
`docs/plans/2026-09-13-pmic-pcie-execution.md`.

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
