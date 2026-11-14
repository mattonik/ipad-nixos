# J81 iPadOS PMGR boot setup: voltage-manager enable (first pass)

Offline only, 2026-11-14. Inputs: the private 19H394 kernel
(`ios1585-19H394-kernel`), the existing T7001 PMGR decompile
(`ios15t7001pmgr.c`) and the captured J81 ADT text. No device access.
Follows the [PongoOS run 1 result](2026-11-14-j81-pongo-gpu-split-run1-result.md),
where `0x20e02300c` stayed `0` before any OS.

## What iPadOS does with the voltage manager

The T7001 PMGR code has two near-identical functions, at
`0xfffffff006c8a164` and `0xfffffff006c88cf8`. Each is reached only
through a pointer in `__PLK_DATA_CONST` (file offsets `0x2493058` and
`0x24924c0`), which looks like a vtable slot. No direct `B`/`BL` reaches
either one. Each takes `(pmgr, enable)`:

- **enable = 0:** read `PMGR+0x23000`, set bits 11:8 (`| 0xf00`), write it
  back.
- **enable ≠ 0:** clear bits 11:8 of `0x23000`. Then read the CPU cluster's
  current p-state from the ACC block (`0x220020`, region 8), look up its
  voltage code in the ACC table at `0x220068 + 8*state`, and write it to
  `0x23010` (the CPU rail code). The `c8a164` variant also writes an SRAM
  code from `0x220110` to `0x23004`. The `c88cf8` variant instead takes the
  SRAM code from the PMGR perf table at `0x1a018 + 16*(0x1a000 & 0xf)`.

So iPadOS enables the voltage manager by clearing a 4-bit field in
`0x23000` and seeding the CPU and SRAM codes from the current CPU state.
The bit meanings are inferred from the code shape, not documented.

## How that compares

| | `0x23000` | `0x2300c` after GPC request |
| --- | --- | --- |
| PongoOS, before any OS (run 1) | not read | `0` |
| Linux (m1n1 `cpufreq_init` writes `0x23000 = 1`) | `1` | `0x164` |
| iPadOS 19H394 | `1` | `0x164` |

Linux ends up with the same `0x23000` value as iPadOS, and its GFX code
reaches `0x164` like iPadOS. That matches the PongoOS result: with the
voltage manager not yet enabled, `0x2300c` stays `0`. **The voltage-manager
enable is a real step that iPadOS performs and PongoOS lacks, but Linux
already has it through m1n1, and page-5 bit 30 still stays clear on Linux.**
On its own it does not explain the stall. On Linux, the first "seed" step
uses m1n1's values rather than iPadOS's ACC lookup; no difference has been
observed in the resulting words.

## Other PMGR boot inputs checked and set aside

The J81 ADT `pmgr` node has `noise-hack = 1`, `soc-tvm`/`cpu-tvm = 1`,
`dvd-period-us`, `dvd-threshold-us`, `dvd-factor`, `dpe-thrtl`,
`perf-domains` (SOC, CPU), `perf-regs` and `voltage-states0/1`. In the
19H394 kernel, the names `noise-hack`, `soc-tvm`, `cpu-tvm`, `dpe-thrtl`,
`dvd-*` appear only in a flat list of string pointers at
`0xfffffff006fce480…`. The `dvd-*` entries are next to
`AppleARMPerformanceControllerDVD…` registry key names. That looks like a
property-publishing list, not a hardware programming path. Only
`perf-regs` (`0xfffffff006bc0214`) and `perf-domains`
(`0xfffffff006bc0a98`) have direct code references, both in ApplePMGR
initialization. Neither path is traced yet.

## Next

- Cheapest live check, read-only and needing no script: on the next PongoOS
  boot, read `0x20e023000` and the six PLL pages (`0x20e000000`–
  `0x20e005018`) from the Pongo shell with `peek`, before any `poke`. This
  gives the true pre-OS state for comparison with Linux and iPadOS.
- Offline: trace the two ApplePMGR init sites that read `perf-regs` and
  `perf-domains`. The SOC perf domain is the remaining boot-time PMGR
  mechanism with no Linux equivalent that is not yet traced.
- If neither gives a candidate, use the XNU boot bisection (direction 2 of
  the [strategy note](2026-11-14-j81-gpu-strategy-reset.md)).

## Second pass: `perf-regs` and `perf-domains` (2026-11-14)

Traced from the two `ApplePMGR` init sites in 19H394, using plain
`objdump` on the private kernel. String operands were resolved through the
Mach-O segment map.

**`perf-regs` (`0xfffffff006bc0214`).** The J81 value is one 16-byte entry:
`{reg 0, offset 0x28000, 0x2f, flags 0}`. Init does three things:

1. It stores the array at `this+0x2628`, with the count at `+0x2630`.
2. It validates each entry's register index against the mapped regions
   (`0x6bc5184`, a lookup only).
3. It calls `0x6bc59f4`, which only logs.

The array is read again only in `0x6bbe500`, the loop that builds IOReport
channels for `ps-regs` devices, `clocks` (`%s_CLK_ON`), `power-domains`
(`%s_POWER_ON`) and `events` (`TVM_TEMP_REG0-3`). Its callees
(`0x6bd337c`, `0x6bd36ec`, `0x6bd37ac` and `0x6bd3860`) build channel IDs
and register them with IOReport (`EVT`, `ACT`, `INACT` keys). They do not
program hardware. So `perf-regs` describes the PMGR residency-counter
block at `PMGR+0x28000`, used for statistics. **No PMGR writes; set aside.**

**`perf-domains` (`0xfffffff006bc0a98`).** The table has two 28-byte entries:

| Name | Voltage table | Type | ID |
| --- | --- | --- | --- |
| `SOC` | `voltage-states0` | 0 | 1 |
| `CPU` | `voltage-states1` | 1 | 2 |

Init allocates `0x110`-byte domain records (`this+0x2730`). It loads
`voltage-states%u` and `voltage-states%u-sram`, and counts the non-zero
states. On J81, `voltage-states0` is 8 zero bytes, so **the SOC domain has
no usable states and iPadOS has nothing to apply to it**. The CPU domain is
ordinary CPU DVFS. There is no GFX entry: GFX DVFS lives in the `sgx` node
and the GPU firmware, not in this table. **Set aside.**

**Method note.** `ApplePMGR` does all its MMIO through virtual read/write helpers
(`0x6bd3d38` writes, `0x6bd3d54` reads, base table at `this+0x2668`). No
direct `BL` reaches them, so a complete static list of boot-time PMGR
writes means resolving vtable calls one by one. That is the slow part
direction 2 warned about.

## Where this leaves the offline trace

None of the three iPadOS PMGR boot inputs traced here explains the stall:
the voltage-manager enable, `perf-regs` and `perf-domains`. Two candidates
remain that have no Linux equivalent:

- `AppleT7000CLPC`, the separate closed-loop performance controller kext
  (listed in 19H394). It is the most likely owner of SoC/GFX
  performance-state setup at boot. It has not been opened yet.
- The direction-2 boot bisection, which avoids enumerating writes by hand.
