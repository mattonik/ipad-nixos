# A11 GPU-WIP comparison for J81 (2026-11-08)

Read-only comparison of [iPhOmarchy GPU-WIP](https://github.com/ryzensnyper/iPhOmarchy/tree/main/GPU-WIP) with the local J81/A8X GPU record. No device or large checkout was used.

## Evidence boundary

GPU-WIP explicitly labels itself offline research: its iPhone 8 Plus/A11 GPU has **not** been booted, no job submitted and no frame drawn. The live survey was read-only. Its useful confirmed results are static: A11 is AGX G10P; its DT bases are RGX `0x04000000`, Fender `0x04D00000`, and gfx-kf IOP `0x04D20000`; IRQs 259–262; Fender offsets match A10 G9P. It extracted and validated a 126,608-byte T8015 PMP firmware payload, but did not install it. Its current Linux DT lacks a GPU node and the booted kernel lacks an Apple GPU driver; Mesa userspace alone does not provide one. See the [GPU-WIP summary](https://github.com/ryzensnyper/iPhOmarchy/blob/main/GPU-WIP/README.md).

J81 evidence is materially further along in *hardware observations*, but not in function: guarded PMGR reaches state 15; GPC state/control and two bridge words were read; a GPC init attempt reported state 1; the first direct RGX revision read did not complete. All 66 selector 9/10 table operations reached software checkpoints. The later post-GPC read of bridge address `0x201f00018` matched the value written by selector 9's first operation, so one table address/value pair has readback evidence; the other 65 operations do not. The separately read address `0x201f0001c` was not among the table writes. No J81 firmware execution or rendering is verified. See local [test4 boundary](2026-11-07-j81-test4-raw-readback-boundary.md), [GPU ID boundary](2026-11-06-j81-gpu-id-hardware-boundary.md), and [Orchard A10 delta](2026-11-05-orchard-a10-gpu-delta.md).

## What transfers

- Reuse the evidence labels (confirmed/candidate/negative/unknown) and treat hardware boot, power-up, ID read, firmware execution and rendering as separate milestones. The A11 report is careful not to promote static extraction to runtime success.
- Keep firmware images distinct by role, provenance, exact payload length and hash. GPU-WIP disentangles SmartIO, PMP, and the AGX kext blob; this is a good model for any future J81 firmware inventory.
- Reconstruct DT and power/interrupt dependencies as prerequisites before driver probing. For J81, this supports the existing offline work on Apple G4G provider order and missing wake/reset ownership, not importing A11/A10 addresses or sequences.
- Keep software checkpoints distinct from target readback. This is exactly the distinction needed for J81's 66 bridge stores.

## Non-transferable architecture

J81 is A8X/T7001, with the local project identifying its GPU as Imagination Rogue GXA6850 and tracing the iOS 8.1 G4G path. A11/T8015 is AGX G10P, with a different RGX/Fender map, gfx-kf/RTKit firmware arrangement, mailbox IRQs, firmware ABI and instruction dialect. A10 G9P Fender offsets are reported identical to A11 G10P, but that does not make either generation a J81 recipe. Do not copy its DT bases, PMP file, clock values, firmware path, command stream or register sequence into J81.

## Offline next work

1. Audit the J81 host/shared-memory plan for explicit cacheability, access attributes, address translation and buffer lifetime; leave any missing J81 evidence marked unknown. This is a review prompt, not a claim that attributes caused the hang.
2. Continue tracing the A8X-specific iOS setup and ownership sequence around GPC reset/wake and the first RGX read. Do not treat A11's successful static map or A10's Fender template as evidence that the A8X wrapper is ready.
3. Preserve the current hardware stop boundary: an incomplete direct RGX MMIO transaction is indeterminate; no retry, firmware upload or rendering follows from this comparison.

Skipped: no full clone, device access, A11 firmware installation, or attempt to port its driver. Risk: GPU-WIP's hardware and driver conclusions remain static/offline; its named G10P addresses and firmware do not apply to J81.
