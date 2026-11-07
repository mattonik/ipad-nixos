# J81 DISP0 dependency: Linux mapping and observation limit

Offline follow-up to `2026-11-07-j81-disp0-record-consumer-trace.md`. No
device action or MMIO read was performed.

## Linux mapping

The Apple path is `AppleMobileADBE0` gate-array index 0 → device-clock ID 112
(`DISP0-V`) → dependency ID 28 (`DISP0`) → PMGR power-state index 86 (PS86).
The 44-byte iOS 8.1 table row for ID 112 has dependencies `[28, 0, 0, 0]`
and power-state indices `[0, 0, 0, 0]`: ID 112 has no direct PMGR state
register of its own. ID 28's row has PS index 86. Separately, the row named
`UART6` is device ID 86 and maps to PS index 58, not PS86.
Linux's live FDT has a generic `apple,t7000-pmgr-pwrstate` platform node at
`/soc/power-management@20e000000/power-controller@202b0`, corresponding to
PS86. Its parent driver is `apple-pmgr-pwrstate`; the node has no raw-state
sysfs attribute, and its `runtime_status=unsupported` / `runtime_usage=0`
are Linux runtime-PM bookkeeping, not PMGR register readback.

The Linux display inventory is only the inherited simple framebuffer / DRM
fbdev at 1536×2048. No Linux DCP/KMS driver consumes Apple's `disp0`
`clock-gates` / `power-gates` arrays, and Linux does not reconstruct the
Apple device-clock table's ID-112 dependency dispatch or `+0x980` mode
callback. So PS86's generic power-domain node is a register-shaped match,
not an equivalent display policy path. The snapshots' sysfs/FDT dumps show
the node and its `reg`; they do not contain the PS86 word value. The Nov. 7
read-only control snapshot contains no PMGR MMIO capture.

## Smallest existing observation

There is no need for a new module merely to sample PS86. Existing
`boot/uartpeek.c` has a read-only `uartpeek pmgr` mode that maps
`0x20e020000` with `PROT_READ`/`O_RDONLY` and reads only PS indices
`0x50..0x59`. Index `0x56` gives PMGR state index 86 at `0x20e0202b0`
(the first word is PS86); index `0x3a`, outside that capture range, is the
actual UART6-associated PS register at PMGR offset `0x201d0`. Therefore the
tool's former `UART6` label for PS index `0x56` was false for this J81 table:
it treated the numeric index as though it were a device ID. The saved
Oct. 11 sample `0x1f0002ff` at `0x56` is a historical PS86/DISP0 word sample,
not UART6 and not from the Nov. 7 control boot. This is the least additional
mechanism for a future, authorized point-in-time sample; it does not write
PMGR or change the display path.

That sample can say whether PS86's target/actual/auto/reset bits are set at
the instant of reading. It cannot establish whether Apple ID 112 transitioned,
whether its dependency dispatch set runtime `+0x980`, or whether that mode
was active before the GFX busy edge. A newly loaded read-only module has the
same limit; resolving edge ordering needs a passive trace at the Apple/Linux
provider boundary, which is unavailable in this boot. Do not interpret the
old `uartpeek` label “UART6” as evidence that PS86 is a UART state.

Evidence: `research/2026-11-07-j81-disp0-record-consumer-trace.md`,
`research/2026-11-07-j81-disp0-ps86-linux-boundary.md`,
`artifacts/live/j81-readonly-20261107T114456Z/{fdt_display_controller,sysfs_display_controller,display_classes}.txt`,
`boot/uartpeek.c`, `tools/gpu_apple_clock_model.py` (44-byte table decoder),
and `research/2026-10-11-uart3-register-capture.md`.
