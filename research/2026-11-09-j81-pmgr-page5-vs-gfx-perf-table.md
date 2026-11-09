# J81 PMGR page 5 versus the GFX perf table

Date: 2026-11-09. Offline comparison of the local 12B410 LLB/iBoot analysis,
iOS 15.8.8 PMGR/AppleT7000 analysis, and saved J81 ADT. No device or MMIO.

> Follow-up: both inspected LLB versions later include page 5 in a
> rate-calculation loop; the bounded iOS 15 selector-table scan found no
> direct selection of its calculated slot. See the
> [page-5 data-flow trace](2026-11-09-j81-llb-page5-clock-dataflow.md).

## What the evidence establishes

- LLB writes 16 GFX perf slots at `0x20e01c000 + n*0x10` from its
  fuse/config records. The slot fields contain valid, feedback, pre-divider,
  post-divider, voltage-index, and companion-word data. iBoot reads these
  slots and computes the ADT `sgx` `perf-states` frequency/voltage pairs.
  This is a direct data path from the GFX table to the ADT; the records are
  not copied as-is. See
  [`LLB/iBoot analysis`](2026-11-08-j81-iboot-llb-gfx-perf-state.md) and
  [`table read`](2026-11-08-j81-gfx-perf-state-live-read.md).
- In the same LLB routine, after those writes, code polls `0x20e005000` bit
  25, clears bit 0 at `+4`, and sets bit 24 at `+8`. The address lies in the
  PMGR aperture, but the instructions do not name the block, call it PLL 5,
  or reference the GFX table through it.
- The saved ADT labels `sgx` perf-state data, but does not name `0x20e005000`
  or connect that address to its table. Its PMGR perf domains list SOC and
  CPU, not GFX. The iOS 15 PMGR/AppleT7000 static findings do not establish
  a read/write path linking PMGR page 5 to the GFX perf slots. Therefore
  “PLL 5” and “the GFX perf table is derived from PLL 5” are unsupported.

## Conclusion and limits

The GFX ADT performance table is derived by iBoot from the dedicated
`0x20e01c000` slot array, which LLB populates from fuse/config data. The
`0x20e005000` operations are a nearby, distinct LLB PMGR setup whose purpose
and functional connection to GFX remain unknown. The slot encoding includes
frequency-related PLL divider fields, but this does not identify page 5 as
that PLL or prove the table's values are sourced from page 5. The offline
ApplePMGR review is bounded to the local extracted components; it does not
exclude use by another driver, firmware, or hardware logic.
