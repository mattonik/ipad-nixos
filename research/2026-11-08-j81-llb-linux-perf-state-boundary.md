# J81 LLB GFX state across Linux handoff

Date: 2026-11-08. Offline source comparison plus an existing read-only Linux
capture; no new device access or register writes.

## State observed after the Linux handoff

LLB writes the GFX perf-state words at `0x20e01c000 + n*0x10` and sets bit 31
of `0x20e01c200` (see the [LLB write scan](2026-11-08-j81-llb-pmgr-write-scan.md)
and [iBoot/LLB analysis](2026-11-08-j81-iboot-llb-gfx-perf-state.md)). A
read-only capture made after Linux boot found the same eight valid table
entries at indices 1–8, zeros at 0 and 9–15, and `0x20e01c200 = 0x80000000`
(the [live read](2026-11-08-j81-gfx-perf-state-live-read.md)). This confirms
those values were present in that Linux session; it does not establish who
last wrote them, that they survived continuously from a particular boot
stage, or the selected GFX performance level.

## Boot-chain attribution boundary

The repository's documented Linux route is DFU/checkm8 -> PongoOS -> m1n1 ->
Linux. `boot/run_m1n1_debug.sh` invokes palera1n with `--pongo-shell
--override-pongo boot/Pongo.bin`; `boot/load_m1n1.py` waits for PongoOS USB
`05ac:4141`, uploads the m1n1 payload, then sends `bootm\n`. The palera1n
binary strings independently identify its `src/stage1/checkm8.c` and the
messages “Booting PongoOS” / “Failed to load PongoOS.” This documents a direct
checkm8-to-Pongo path, with no LLB or iBoot handoff in the recorded Linux
sequence. It does not rule out those stages running earlier, before DFU was
entered. The palera1n source checkout is not present here, so its binary
strings are corroborating identifiers rather than a complete control-flow
audit; no trace captures every instruction between DFU entry and the Linux
payload. The supported statement is that the documented run does not invoke
or record LLB/iBoot as part of its handoff.

The live PMGR snapshot matches the output attributed to the local 12B410 LLB
disassembly, but that binary is an offline source comparison, not a trace of
the installed iOS 15 boot. The matching live values therefore establish
post-handoff presence and an LLB-compatible configuration, not that LLB ran
in this Linux boot or uniquely supplied the values. There is no pre-DFU
snapshot or write trace to establish the values' origin or continuity across
the transition. The saved Pongo ADT's `original-base-os-version` property is
not proof that iBoot/LLB executed in the Linux boot.

## Linux selector gap

The inspected [Linux PMGR power-state driver](https://github.com/torvalds/linux/blob/v7.3-rc1/drivers/pmdomain/apple/pmgr-pwrstate.c)
manages each child’s single PMGR power-state word and reset bit. A search of
the [J81 m1n1 patch set](../boot/m1n1/patches) found no GFX/perf-state
programming path. The separate Orchard A7–A11
[m1n1 patch](https://github.com/OrchardLinux/orchard/blob/3b5108096f42e1fae3dd1a15664b650b708e5838/boot/m1n1/patches/orchard/0011-kboot-Fill-the-A7-A11-GPU-s-performance-states-from-.patch)
imports ADT `perf-states` into Linux OPP entries; it does not select a J81 GFX
state or program these PMGR registers. The guarded Linux GFX test demonstrates the
power-domain transition (`0x20e020320` from `0x300` to `0x3ff`), not a
performance-state selection (see the [hardware boundary](2026-11-06-j81-gpu-id-hardware-boundary.md)).

Thus, available evidence confirms the LLB-matching table/control values were
present in the Linux session alongside a Linux GFX power-on, but identifies no
Linux code that selects a GFX perf level. This is a bounded source finding, not
proof that no indirect or uninspected code can select one. The LLB scan’s
other PMGR operations remain unmapped and have no corresponding Linux
readback; they cannot yet be called missing or tied to the GPU.
