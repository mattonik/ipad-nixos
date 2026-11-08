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

## Offline search for the perf-state selector (same day)

A search of both kernelcaches found no kernel code that selects a GFX perf
state:

- The `sgx` ADT node maps no PMGR registers. It does carry
  `meta-sw-interrupt`, which names PMGR addresses `0x20e104010` and
  `0x20e104090`, and two platform functions, `clpc_enabled` (on `pmgr`)
  and `clpc_gpu_feedback` (on `clpc`).
- J81 PMGR `perf-domains` lists only SOC and CPU. The iOS 15 ApplePMGR GFX
  clock-generator helpers (`readGFXClkGenReg` and related) and the GFX perf
  domain are generic code for other SoCs, and nothing on J81 points them at
  this block.
- In 12B410, the only kernel reader of `perf-states`, `perf-state-count`
  and `meta-sw-interrupt` is `IOAcceleratorFamily2`, at
  `0xffffff8003285468`–`854ec` and `0xffffff8003287384`. It copies the
  (frequency, voltage) pairs into its own object (`+0x5d2c`, count at
  `+0x5dac`). These are DVFS tables for the GPU power controller or
  firmware, not register writes.
- A scan of the 12B410 prelinked text and kernel text, and of the whole
  19H422 image, for an `add #0x1c, lsl #12` or a `0x1c000`/`0x1c200`
  immediate found nothing relevant. This is a pattern scan, not a full
  audit: a base pointer plus a table offset would not show up in it.

Reading: on iOS the kernel probably never selects a GFX perf state itself.
The selection is either made later by the GPU firmware, which runs after
the ID read, or made by hardware when GFX powers on. If it is the
firmware, Apple's ID read would also run at state 0, and 0 Hz cannot be
the whole cause of the hang. If it is the hardware, a read after power-up
will show a nonzero selection. So the after-power-up read is the deciding
check.

## Next

1. Done above, inconclusive on its own.
2. Hardware: repeat this read once right after the guarded PMGR power-up
   (`0x3ff`), with no bridge, GPC or RGX access. The boot used here runs the
   original GPU-test kernel (`/sys/kernel/notes` sha256 `82ff70e8...`, the
   value the 20261106 bundle wrappers check), but its device tree is the
   MCC payload's. Tried 2026-11-08 18:5x: `insmod gpu-pmgr-once.ko` failed
   with `EINVAL` before any register access, because the GFX power-state
   node lacks the `experimental,j81-gpu-test-no-poweroff` guard property
   that the module requires. Nothing was powered, and a perf read right
   after showed unchanged values (PS `0x300`, control `0x80000000`). The
   check needs a boot of the `gpu-pmgr-once` payload (DFU).

The stop rules in
[`2026-11-08-j81-next-mcc-experiment-decision.md`](2026-11-08-j81-next-mcc-experiment-decision.md)
still apply. No register was written.
