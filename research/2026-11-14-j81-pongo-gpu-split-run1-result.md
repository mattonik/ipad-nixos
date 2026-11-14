# J81 PongoOS GPU split test: run 1 result (`--no-core-read`)

Run on 2026-11-14 at 11:45 UTC with Martin's `boot/pongo_gpu_split.py`. That
script was uncommitted on his `main` at the time of the run. The test
followed the [plan](2026-11-14-j81-pongo-gpu-split-plan.md) and ran on a
fresh DFU → PongoOS boot. The PongoOS banner read `pongoOS 2.6.3-bb492b00`,
`Booted by: iBoot-7459.140.15`, `Running on: Apple A8X (T7001)`. No XNU or
m1n1 ran on this boot. The private transcript is in
`artifacts/live/gpu/pongo-split-20261114T114518Z/`.

| Step | Value |
| --- | --- |
| GFX PS before | `0x300` (off) |
| page 5 `+4`, perf control, `0x2300c` before | `0`, `0x80000000`, `0` |
| GFX PS after power-on | `0x3ff` |
| GPC state before the bridge stores | `0` |
| bridge stores, GPC writes | 66 + 3, every `poke` echo confirmed |
| GPC state after the request | `1` on the first poll |
| page 5 `+4` after GPC, 3 samples | `0`, `0`, `0` (bit 30 clear) |
| perf control after GPC | `0x80110100` (same as Linux and iPadOS) |
| `0x2300c` after GPC | **`0`** (Linux and iPadOS: `0x164`) |
| GPC control | `0x40000000` |

No core read was made.

## Reading

- From PongoOS, before any OS runs, the GFX PLL status bit stays clear, as
  it does on Linux. m1n1 and Linux do not cause the page-5 difference;
  iPadOS's boot does something PongoOS (and therefore Linux) lacks. Under
  the plan's decision rule, the next work is direction 2 (bisect the XNU
  boot), not the m1n1/Linux side.
- New observation: the GFX voltage-manager word `0x20e02300c` stays `0` in
  PongoOS after the GPC request. On Linux it becomes `0x164`, most likely
  because m1n1's `cpufreq_init` writes `PMGR+0x23000 = 1`. iPadOS reads
  `0x23000 = 1` and `0x2300c = 0x164`. So before any OS, the voltage
  manager is not enabled; iPadOS must enable it itself, and Linux has it only
  as a side effect of m1n1. `0x23000` was not read in this run.
- The core read (run 2) was not made. Every earlier read with bit 30 clear
  hung, so it is expected to hang. It would confirm the fork result but adds
  little; it is optional.

## Pre-OS PMGR snapshot (2026-11-14, read-only)

A second fresh DFU → PongoOS boot ran only 34 `peek`s, with no `poke`, no GFX power-on
and no GPC or core access. Private log:
`artifacts/live/gpu/pongo-peek-20261114T123332Z.log`.

| Word | PongoOS (pre-OS) | Linux / iPadOS (earlier samples) |
| --- | --- | --- |
| GFX PS `0x20e020320` | `0x300` | `0x300` before cycle |
| VM ctrl `0x20e023000` | `0xf01` (bits 11:8 set = disabled) | `0x1` on both |
| VM `0x23004`/`08`/`0c`/`10` | all `0` | SRAM/CPU/GFX codes non-zero |
| VM `0x23014`-`0x23020` | `0xbb81ac05` each | not sampled |

PLL pages (`+0` / `+4` / `+8` / `+0x18`):

| Page | `+0` | `+4` | `+8` | `+0x18` | State |
| --- | --- | --- | --- | --- | --- |
| 0 | `0x1010` | `0x80000001` | `0x80480348` | `0x1` | bypass |
| 1 | `0x80085040` | `0x40000000` | `0x80480348` | `0x04000040` | running |
| 2 | `0x1010` | `0x80000001` | `0x80480348` | `0x1` | bypass |
| 3 | `0x8003201b` | `0x40000000` | `0x80480348` | `0x04000040` | running |
| 4 | `0x80032010` | `0x40000000` | `0x88480348` | `0x04000040` | running |
| 5 (GFX) | `0x1010` | `0x0` | `0x81480348` | `0x1` | off, bypass cleared |

Reading:

- PLL5 leaves LLB exactly as LLB's page-5 routine sets it: bypass request
  (bit 0 of `+4`) cleared, `+8` bit 24 set, `+0` at the reset value `0x1010`.
  These three words equal the Linux samples (`0x1010`, `0`, `0x81480348`)
  and the iPadOS `+0`/`+8` samples. iPadOS never rewrites them. Its only
  difference is `+4` bit 30 after the GPC request. So nothing in the PLL5 page
  itself is missing on Linux. PLL5 is started by something else (the GFX
  perf-state engine), and that engine does not start it on Linux or in PongoOS.
- Before any OS runs, the voltage manager is disabled (`0xf01`) with every code at 0,
  the CPU code included. iPadOS and m1n1 each enable it. This is consistent with
  run 1 (`0x2300c` stayed 0 in PongoOS). It is not the Linux difference,
  because on Linux it is enabled and `0x2300c` reaches `0x164`.
- The untraced iPadOS startup paths (`perf-regs`, SOC `perf-domains` init)
  remain the next offline step, followed by direction 2.
