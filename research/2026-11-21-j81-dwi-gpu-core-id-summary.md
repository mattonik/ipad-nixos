# J81 GPU: the core-ID read works once the DWI power line is on (summary, 2026-11-21)

Device: one iPad Air 2 Wi-Fi (`iPad5,3`, J81, Apple A8X/T7001, Imagination GXA6850). Linux 7.3.0-rc1
(Hoolock `6831bc7`), RAM-root "observer" boots started from checkm8/PongoOS/m1n1.
Evidence labels: **E** = observed on the device, **I** = inference, **U** = unknown.

## Result in one paragraph

The first GPU register read, the core ID at `0x201000020`, hung the bus on Linux in every earlier
run. It returns `0x00070500` (the value iPadOS reads) when one extra store is made before the GFX
activation: switching the PMGR `dwi` power state (`0x20e020120`) from `0x200` (off) to `0xff` (on).
Two of two runs with it returned the ID and did not hang (E). Linux switches that domain off about
0.7 s into every boot as "unused"; LLB and iPadOS keep it on (E). Nothing was rendered, no firmware
was loaded, and no other GPU register has been read yet.

## What `dwi` is and why it matters (E unless marked)

- `dwi` carries the voltage requests from the SoC's voltage manager to the PMIC (Dialog D2207, I2C
  bus 0, address `0x3c`). With `dwi` off the request is made (the GFX voltage word `0x20e02300c`
  goes to `0x164`) but the PMIC never acts on it.
- PMIC buck row `0x0128` reads `00 00 40 00 40 e0 0f 31` before the request. With `dwi` on it reads
  `64 00 64 00 40 e0 0f 31` after the GFX request and keeps that for at least 10 s. With `dwi` off
  it never left `00/40` (observed in a snapshot campaign on the same day). The other three buck rows
  (`0100`, `0150`, `01c8`) were unchanged (row `0100` moved `6d`->`88`->`6d` in one run only).
- **I:** buck 1 (row `0x0128`) is the GPU rail. **U:** whether the rail actually reaches its target
  voltage; `64/64` is a register value, not a measurement.
- Why earlier "DWI is not the cause" tests (14 Nov) did not settle it: they predate the MiscACG store
  (19 Nov), so the page-5 condition and the DWI condition were never tested together.

## The recipe (order is Apple's; every store verified by readback; one shot per boot)

1. Boot to a RAM-root Linux with the observer kernel; the dwi domain is already off.
2. PLL1 +8, PLL4 +8 (`boot/pmgr-pll-set.c`), MCC bank bit 31 on five words
   (`boot/pmgr-mcc-set.c`), MiscACG `0x20e032000 = 1` (`boot/pmgr-miscacg-set.c`),
   SoC TVM `0x20e02d000`-area store (`boot/pmgr-tvm-set.c`). Each runner stops if any other PMGR word
   changed.
3. **DWI on:** one store of target 15 to `0x20e020120` (`boot/pmgr-dwi-on.c`); refuses unless the
   word reads exactly `0x200`; requires readback `0xff`. A snapshot after it must show no other change.
4. One GFX power activation (single `pm_runtime_get_sync`, no off/on cycle).
5. One in-kernel batch with interrupts masked (`kernel/gpc-page5-kpoll-*`): 66 bridge stores
   (33 per table, `0x201f00000`/`0x201f80000`), GPC `+0x10000 = 0xffff0000`, `+0 = 0x40000000`,
   `+0x1000 = 0x11`, poll until state 1, page-5 `+4` sample (bit 30 set), core ID read.
6. Read PMIC rows before the batch, after it, and 10 s later (`tools/pmu-peek`, read-only I2C).

## Runs on 21 November (all fresh boots)

| Run | What | Result |
| --- | --- | --- |
| single activation | one GFX request instead of off/on | core read still hangs |
| compressed batch | bridge+GPC+page5+core in one irq-off context, non-posted mappings | still hangs |
| no-core control | same, core load compiled out | batch returns; the stall is the core load itself |
| bridge readback | 66 words read back before/after GPC | 66/66 equal the plan |
| DWI snapshot | dwi off, request made | PS stays `0x200`; PMIC row stays `00/40` |
| **DWI on, no core read** | recipe above, control module | batch returns; PMIC `0128` -> `64/64`, held 10 s |
| **DWI on + core read, run 1** | crumbs-core module | **`core=0x00070500`**, core read 500 ns, no hang |
| **DWI on + core read, run 2** | repeat, fresh boot | **`core=0x00070500`**, core read 458 ns, no hang |

Per-run notes: `research/2026-11-21-j81-*-result.md`.

## What this does not show

- Not a driver; no firmware, no job, no frame. One register read only.
- One device, two successful runs with the same module and runner; no run with different parameters.
- Whether a smaller recipe suffices (which of PLL/MCC/MiscACG/TVM are still needed with `dwi` on) is untested.
- Whether keeping `dwi` on from early boot, instead of the post-boot store, behaves the same is untested.

## Making it permanent (not yet verified on hardware)

The PMGR driver already honours `apple,always-on` (it powers the domain on at probe and marks it
`GENPD_FLAG_ALWAYS_ON`). `kernel/patches/0125-j81-dwi-always-on.patch` adds `&ps_dwi { apple,always-on; };`
to `t7001-j81.dts`; `kernel/dwi-always-on/build.nix` builds a test kernel/payload with it. Orchard's
T7000-handheld trees already carry an equivalent through the `dwi_bl` node. A side effect worth
having regardless of the GPU: with `dwi` off the CPU and SRAM rails do not follow DVFS requests.

## For other A8/A8X/A9 researchers

If your core-ID read hangs although the PMGR/GPC/page-5 sequence matches iPadOS, check first:
`cat /sys/kernel/debug/pm_genpd/pm_genpd_summary` (or the genpd debugfs entry for `dwi`) and the
PMGR word at `+0x20120` after boot. A domain that LLB left on but Linux turned off before your
GFX activation is the lead.

## Next

1. Read a bounded, read-only set of further GPU registers after the core ID.
2. Keep `dwi` on from early boot (patch 0125) and repeat.
3. Narrow the recipe to what is needed.
