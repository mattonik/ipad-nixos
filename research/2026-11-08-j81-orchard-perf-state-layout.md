# J81 GPU perf-state layout vs Orchard's A7–A11 OPP importer

Date: 2026-11-08. Offline source comparison; no device access or edits to
boot payloads. This checks the data representation only. It does not show that
J81 selects any particular GPU performance level.

## Orchard importer contract

Orchard pins Asahi m1n1
[`c9ef56f7356e93e6f6cac116c529d31c277ef6a6`](https://github.com/AsahiLinux/m1n1/blob/c9ef56f7356e93e6f6cac116c529d31c277ef6a6/src/kboot_gpu.c#L25-L28),
which defines `struct perf_state` as two `u32` fields, `freq` then `volt`.
The existing GPU setup validates `perf-states` against
`sizeof(struct perf_state) * perf-state-count * perf-state-table-count` and
validates `perf-states-sram` separately
([pinned source](https://github.com/AsahiLinux/m1n1/blob/c9ef56f7356e93e6f6cac116c529d31c277ef6a6/src/kboot_gpu.c#L565-L577)).
Orchard's added A7–A11 path reads the ADT `perf-state-count` and
`perf-states`, accepts at least `count * sizeof(*ps)` bytes, then emits an OPP
from each nonzero row at its original index: `opp-hz=ps[i].freq`,
`opp-microvolt=ps[i].volt * 1000`, `opp-level=i`. It skips row 0 ([Orchard A7–A11 importer patch](https://github.com/OrchardLinux/orchard/blob/3b5108096f42e1fae3dd1a15664b650b708e5838/boot/m1n1/patches/orchard/0011-kboot-Fill-the-A7-A11-GPU-s-performance-states-from-.patch#L55-L83)).
The patch describes these rows as frequency-Hz/voltage-mV pairs and state 0
as off (same patch, lines 6–14 and 29–35).

## What J81 evidence supports

The J81 12B410 iBoot/LLB analysis reports an `sgx` ADT with
`perf-state-count = 16`, `gpu-num-perf-states = 4`, and 16 frequency/voltage
pairs: row 0 is 0 MHz/600 mV; rows 1–8 are 365, 450, 500, 550, 182.5, 225,
250 and 275 MHz; rows 9–15 are invalid (`research/2026-11-08-j81-iboot-llb-gfx-perf-state.md:24-29, 47-63`). The values are derived from the
PMGR table by iBoot's static code path. A separate live read confirmed the
16 PMGR slots and that only indices 1–8 have their valid bit set
(`research/2026-11-08-j81-gfx-perf-state-live-read.md:27-49, 86-94`).

The LLB's 20-byte-per-state fuse/config records are not the `perf-states`
property layout. LLB writes clock fields and a separate `+4` word into PMGR;
iBoot reads PMGR and constructs the ADT's frequency/voltage pairs. The extra
byte at source-record `+16` is associated with the separate SRAM table, not a
third field in each `perf-states` pair (`research/2026-11-08-j81-iboot-llb-gfx-perf-state.md:35-43`; `research/2026-11-08-j81-gfx-perf-state-live-read.md:86-93`).

## Bounded conclusion

The documented J81 pair shape is consistent with Orchard's 8-byte
`(u32 Hz, u32 mV)` importer, and its indices 1–8 would remain OPP levels 1–8;
there is no 20-byte-versus-8-byte mismatch in the **generated ADT property**.
This is a static format comparison, not a direct runtime check of the saved
ADT property's raw byte length or an integration test proving Orchard's parser
against J81's blob. Orchard's path also requires an FDT `gpu` node with an
empty `operating-points-v2` table; it does not create a J81 GPU node.

Keep performance level separate from PMGR domain power state: the J81 PMGR
read `0x20e020320 = 0x3ff` means GFX domain target/actual state 15, whereas
`perf-states` rows 1–8 are GPU clock/voltage levels. The J81 source review did
not find a boot-stage write selecting one of those levels, and the live table
snapshot was taken with GFX off (`research/2026-11-08-j81-gpu-id-hardware-boundary.md:5-12`; `research/2026-11-08-j81-iboot-llb-gfx-perf-state.md:64-80`).

Finally, this only transfers the **ADT-to-OPP data mapping**. A10's GPU driver
uses its T8010 Fender/A7-IOP firmware protocol to request performance states;
that control path is not evidence for an A8X/J81 selector or a substitute for
J81's own GPC/RGX bring-up contract (see the
[Orchard A10 GPU patch](https://github.com/OrchardLinux/orchard/blob/3b5108096f42e1fae3dd1a15664b650b708e5838/kernel/patches/drivers/gpu/0001-drm-imagination-Support-the-Apple-A10-T8010-GPU.patch#L187-L194)).
