# J81: live read of the GFX perf-state table (read-only)

Date: 2026-11-08. One read-only `/dev/mem` snapshot on the running J81
(Linux 7.3.0-rc1, about 30.8 h uptime). The boot had earlier run only the
MCC read-once test ([MCC read result](2026-11-08-j81-mcc-read-result.md)).
No GFX power-up, bridge write, GPC or RGX access happened in this boot.
Follows the [iBoot/LLB note](2026-11-08-j81-iboot-llb-gfx-perf-state.md).

Tool: [`boot/gpu-pmgr-perf-peek.c`](../boot/gpu-pmgr-perf-peek.c) (static
aarch64, sha256 of the stripped build
`eb446a661e5414e038b049d9ce425458234ef3464248b1c0e90e4c2316a49fc5`). It
maps two PMGR pages read-only and reads 18 words. The raw log is kept
private under `artifacts/live/gpu-pmgr-perf/`. The device answered a shell
command right after the read.

## Values

| Address | Raw | Decoded |
|---|---|---|
| `0x20e020320` (GFX PS) | `0x00000300` | target 0, actual 0 (GFX off) |
| `0x20e01c200` (control) | `0x80000000` | bit 31 set, all other bits 0 |
| `0x20e01c000` (state 0) | `0x00000000` | 0 Hz |
| `0x20e01c010` (state 1) | `0x6436d063` | 365 MHz, vidx `0x64` |
| `0x20e01c020` (state 2) | `0x7024b021` | 450 MHz, vidx `0x70` |
| `0x20e01c030` (state 3) | `0x7027d031` | 500 MHz, vidx `0x70` |
| `0x20e01c040` (state 4) | `0x7f313061` | 550 MHz, vidx `0x7f` |
| `0x20e01c050` (state 5) | `0x6436d067` | 182.5 MHz |
| `0x20e01c060` (state 6) | `0x7024b023` | 225 MHz |
| `0x20e01c070` (state 7) | `0x7027d033` | 250 MHz |
| `0x20e01c080` (state 8) | `0x7f313063` | 275 MHz |
| `0x20e01c090`–`0f0` (9–15) | `0` | unused |

The frequency formula, fitted to all eight nonzero entries and the saved
ADT `perf-states`, is

    f = 24 MHz × fb[20:12] / (pre[8:4] × (post[3:0] + 1))

Every entry matches the ADT exactly. This corrects the iBoot/LLB note on one
point: states 9–15 read as zero here, they do not repeat an entry.

## What it shows

- LLB's table is live in hardware on our boot chain, and the enable bit is
  set. The GPU clock source is configured; nothing before Linux is missing
  here.
- The control word has no bits set except bit 31. If its low bits hold the
  selected perf state, the selection is state 0, which is 0 Hz. That is an
  inference: the field layout of `0x20e01c200` is not decoded.
- GFX was off during this read, so the snapshot does not say what the
  hardware selects once GFX is powered. That is the one open question this
  check can still answer.

## Next

1. Offline: find who writes `0x20e01c200` (or another GFX perf-select
   register) on iOS, in the AGX kext or ApplePMGR, and whether it happens
   before the RGX ID read. That decides whether the core-ID hang is a 0 Hz
   clock.
2. Hardware, only if 1 is inconclusive: repeat this read once in a fresh
   GPU-payload boot right after the guarded PMGR power-up (`0x3ff`), with no
   bridge, GPC or RGX access. It needs a reboot through DFU.

The stop rules in
[`2026-11-08-j81-next-mcc-experiment-decision.md`](2026-11-08-j81-next-mcc-experiment-decision.md)
still apply. No register was written.
