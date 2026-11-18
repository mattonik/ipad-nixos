# J81 GPU feasibility: what Orchard's A10 work gives us (2026-11-04)

Offline check only: no build and no boot. Sources: OrchardLinux/gpu at its
current `main` (`README.md`, `a10/FIRST-LOOK.md`, `a10/bringup/kernel.md`,
`a10/bringup/power-display.md`), the private J81 ADT capture
(`artifacts/adt/20260908T082112Z-j81.adt`, kept out of Git) and the live J81
FDT from the same day. Only resource names, addresses and counts are recorded
here.

## Short answer

Orchard's A10 driver does not port to the A8X directly. Its whole firmware
layer (gfx-kf coprocessor, A7 IOP mailbox, RTKit, the AGX init/doorbell
endpoints, init-data layout) assumes an Apple coprocessor that the J81 does
not have. What does carry over is the hardware-side knowledge: the Rogue core
location and identity registers, the single `GFX` power domain, the Rogue MMU
and the m1n1 performance-state plumbing. The A8X is most likely the older
design in which the firmware runs on the Rogue core's own META
microcontroller. That puts it closer to upstream `drm/imagination`'s model
than to Orchard's, but with Apple's own firmware and host protocol, which
nobody has documented. The GPU stays the project's largest open item.

## What the J81 ADT says

The `sgx` node (`compatible = "gpu,t7001"`, `device_type = "sgx"`):

| Property | J81 value | A10 (T8010) for comparison |
|---|---|---|
| `reg[0]` | `0x201000000`, 1 MiB | Rogue core at `0x201000000` (same address) |
| `reg[1]` | `0x201e00000`, 1 MiB | Fender at `0x201d00000` (gfx-kf at `0x201d20000`) |
| `interrupts` | 5 AIC IRQs, 134 to 138 | gfx-kf mailbox IRQs 189 to 192 |
| `meta-sw-interrupt` | AIC SW-generate set/clear words (`0x20e104010` / `0x20e104090`) with bits 6 and 10 | present too, but unused on A10 |
| `clock-gates`, `power-gates` | `0x7c` | one power state `GFX`, PMGR id `0x7c` |
| `perf-states` | 4 GPU states (`gpu-num-perf-states = 4`), about 365 to 550 MHz | 6 states |
| `opengl-standard`, `metal-standard` | `0x300`, `0x100` (GLES 3.0, Metal 1) | n/a |

Things that are *absent* from the J81 ADT matter more:

- **No `gfx-kf` node and no GFX IOP nub.** The only IOP nubs are SEP, ANS
  and SIO. On the A10 the GPU firmware runs on `gfx-kf`.
- **No GPU DART.** The DARTs are disp0, scaler, jpeg, isp, ave and apcie1.
  The A10 has no GPU DART either, because the Rogue core has its own MMU, so
  this is the expected case and not a gap.

The `meta-sw-interrupt` words decode as AIC software-generated-interrupt
registers (AIC is at `0x20e100000`; `+0x4000` set and `+0x4080` clear in
`irq-apple-aic.c`). Word 4, bits 6 and 10, are IRQs 134 and 138, the first
and last `sgx` interrupts. That fits an AP-to-META doorbell over the AIC.
This is a reading of the register layout, not a hardware result.

The live FDT (Hoolock's `t7001.dtsi`) already has a `ps_gfx` power domain at
PMGR `+0x20320`, with no consumer. There is no GPU node.

## What carries over from Orchard

1. **Rogue core identity read.** Orchard read `RGX_CR_CORE_ID` (`+0x18`) and
   legacy `CORE_REVISION` (`+0x20`) at `0x201000000` once the core was powered.
   J81's core sits at the same address, so the same two reads give us the
   BVNC that Mesa and `drm/imagination` key on. This is the gate the
   long-term plan already named (`research/j81-long-term-subsystems.md`).
2. **Power before access.** On the A10 any RGX register access while the core
   is off raises an SError. Assume the same here: the `GFX` domain (and
   possibly a Fender-style perf-state write) must be on before the first read.
3. **Fender perf-state concept.** Orchard cites an iOS 10 unstripped kext
   class `G5::AGXMetaFender::enableGPCPerfStateOverride` for the same register
   (Fender `+0x1000`, write `0x10 | state`, poll the low bits). A "Meta" Fender
   class in an older namespace suggests the META-era chips have a Fender too.
   J81's `reg[1]` is the likely Fender, but its offset and register layout are
   unconfirmed.
4. **Rogue MMU.** Orchard uses upstream `pvr_mmu.c` page tables unchanged.
   Rogue's MMU should be the same on Series6XT.
5. **m1n1 OPP fill.** Orchard's m1n1 (`dt_set_gpu_pstates()`) fills a GPU
   `operating-points-v2` table from any A7 to A11 `sgx` node's `perf-states`.
   We already build m1n1 from Orchard's source, so this is available once a
   GPU node exists.
6. **Method.** Orchard's layout per fact (evidence, code, verify) and its
   tools (`gpu-probe`, `ios-capture`, `kc-kext-elf.py`) apply as they are.

## What differs on the A8X

- **GPU generation.** PowerVR Series6XT (GXA6850, 8 clusters). The A10 core
  reports BVNC 13.10.6.2, a newer Rogue. Mesa has partial Series6XT data
  (GX6250, GX6650 scaffolding), none for GXA6850.
- **Where the firmware runs.** Probably the core's own META processor, not an
  Apple ARM coprocessor. So Orchard kernel.md part 1 (mailbox, RTKit,
  endpoints 0x20/0x21, init page, firmware window) does not apply. Upstream
  `drm/imagination` has a META boot path (`pvr_fw_meta.c`), but it speaks
  Imagination's protocol (KCCB/FWCCB), and Apple's firmware almost certainly
  does not. Orchard notes that the AGX kext family keeps "META GPUs" code
  paths, probably for these older chips.
- **Firmware source.** It comes from the T7001 AGX kext in our iOS 8.1
  (12B410) kernelcache or the iPadOS 15.8.8 IPSW on the NAS. Its format is
  unknown: a META image, not Orchard's ARM32 `GFX` image.
- **Interrupts.** Five direct AIC lines plus AIC software interrupts, not four
  mailbox interrupts.
- **Shader ISA.** Unknown. The A10 runs Apple's ISA. Orchard's `metal-tt` probe
  settles it only if Xcode still ships an A8-class target.
- **Power domain offset.** Hoolock's `ps_gfx` at `+0x20320` does not equal
  `0x20000 + 0x7c * 8` (`+0x203e0`), the gate formula found in the touch
  work. Either the PMGR id and the register index differ (likely), or one of
  the two is wrong. Confirm this before using `ps_gfx`.

## Recommended first step

Offline, about an hour, using the existing 12B410 Ghidra project:

1. List the AGX kexts in the 12B410 kernelcache and note the T7001 class
   names: a `*RTBuddy` firmware class (Apple coprocessor) or a META loader.
   This confirms or rejects the "firmware on META" reading above.
2. In that kext, find the power-up path: the PMGR request, then any Fender
   write before the first `RGX_CR_*` access, with offsets relative to
   `reg[1]`.
3. Settle the `ps_gfx` offset question against the same code.

The first hardware gate comes after that and needs a separate go-ahead. It is
read-only: with `ps_gfx` (and any Fender write step 2 finds) on, read
`CORE_ID` and `CORE_REVISION` once with `devmem`, and record the BVNC. With
the BVNC, decide whether to extend `drm/imagination` or to write an
Orchard-style Apple variant. Until then, llvmpipe on simplefb stays the
display path.

## Not done here

No firmware was extracted and no kernelcache was opened. The META reading
rests on what is missing from the ADT and on the `meta-sw-interrupt` decode,
not on code.
