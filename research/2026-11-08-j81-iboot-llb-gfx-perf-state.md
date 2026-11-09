# J81 iBoot and LLB 12B410: what the boot chain does for the GPU

Date: 2026-11-08. Offline. I decrypted `iBoot.j81.RELEASE.im4p` and
`LLB.j81.RELEASE.im4p` from the local iPad5,3 8.1 (12B410) IPSW with the
public keys at `api.ipsw.me/v4/keys/ipsw/iPad5,3/12B410`, then disassembled
them with `objdump -b binary -m aarch64` (iBoot at `0x87a0e0000`, LLB at
`0x180000000`). The decrypted images stay on the Mac, outside Git. I also
used the saved J81 ADT `artifacts/adt/20260908T082112Z-j81.adt` (private).
The decrypted images and ADT are not included, so public readers cannot
independently reproduce the binary and ADT observations from this repository.
No device access.

## iBoot (iBoot-2261.3.32)

- **It never touches the GPU blocks directly.** A constant scan finds no
  address in `0x201000000`–`0x201ffffff` (RGX, GPC, bridges). Its PMGR use
  is clock and PLL setup (`0x20e000000`, `0x20e010000`), power-state
  registers (`0x20e020000`) and chip-ID/fuse registers (`0x20e02a000`).
- **The kernel inherits the clock state.** The boot path (`0x...fd224`)
  calls a quiesce routine (`0x...f9a70`) that dispatches on boot type. Only
  types 5 and 7 (DIAGS and MONITOR, by the usual iBoot enum) take the path
  (`0x...fc7a4` → `fc4c4`) that resets the clock muxes to `0x80100000`,
  powers off devices outside a keep-mask and clears `0x20e01c200`. The
  Darwin boot type does not, so iOS starts with the clock, PLL and GFX
  perf-state setup the earlier stages left.
- **It reports the GFX perf states, it doesn't set them.**
  `pmgr_gfx_update_device_tree` (`0x...fcf80`) reads 16 GFX perf-state
  registers at `0x20e01c000 + n*0x10`. Each register holds PLL fields
  (feedback `[20:12]`, pre-divider `[8:4]`, post-divider `[3:0]`, × 24 MHz)
  and a voltage index in `[31:24]`. It writes the results into the `sgx`
  node's `perf-states` property.

## LLB

LLB is what programs the GPU clock:

- `0x...12fbc`–`12ff0` writes the 16 GFX perf states through
  `0x...13adc`. States 0–8 come from a 20-byte-per-entry table built from
  chip-ID fuse voltages (`chipid_get_gpu_voltage`, `chipid_get_gpu_ram_voltage`).
  The code appeared to repeat one entry for states 9–15, but the live read
  shows them as zero ([live read](2026-11-08-j81-gfx-perf-state-live-read.md)).
- `0x...12ff4`–`1301c` operates on PMGR page `0x20e005000`: wait for bit
  25, clear bit 0 at `+4`, set bit 24 at `+8`. The block is not identified
  as PLL 5 by the LLB instructions, the saved ADT, or the iOS PMGR analysis;
  its function and relationship to GFX remain unresolved. These writes are
  separate from the GFX perf-state table at `0x20e01c000`.
- `0x...13020`–`13034` sets bit 31 of `0x20e01c200`, which enables GFX
  perf-state control.

## What the saved ADT shows

The `sgx` node in the 2026-09-08 capture has `perf-state-count = 16`,
`gpu-num-perf-states = 4` and filled-in `perf-states`, as
(frequency, voltage mV) pairs:

| State | MHz | mV |
|---|---|---|
| 0 | 0 | 600 |
| 1 | 365 | 912 |
| 2 | 450 | 950 |
| 3 | 500 | 950 |
| 4 | 550 | 996 |
| 5–8 | 182.5, 225, 250, 275 | 912–996 |

iBoot computes these from the live `0x20e01c000` registers, so the saved ADT
is evidence that those table values were present when iBoot populated that
tree. The `original-base-os-version` property is consistent with iBoot having
produced or contributed to the saved tree, but it does not show that iBoot or
LLB ran during the later Linux boot. The documented Linux run starts from DFU:
palera1n performs checkm8 and loads PongoOS, then the host uploads m1n1 and
sends PongoOS `bootm` (`boot/run_m1n1_debug.sh`, `boot/load_m1n1.py`). No LLB
or iBoot execution appears in that path. Therefore do not use this ADT alone
to claim those stages ran in the Linux boot, or to rule out a boot-stage
difference between iOS and Linux. The Linux-session read is covered by the
[handoff-state boundary note](2026-11-08-j81-llb-linux-perf-state-boundary.md).

The state-0 table word is all zero and has its valid bit clear. Treat it as
an invalid entry, not a valid 0 Hz state; neither the selected state nor the
PLL output follows from this ADT row.

The PMGR `perf-domains` property lists only `SOC` and `CPU`. ApplePMGR's
perf-state machinery therefore does not manage GFX on J81. The `sgx`
node's two `reg` entries map no PMGR registers. Which agent picks a nonzero
GFX state on iOS (the AGX kext through another provider call, the GPU
firmware, or hardware on power-up) is still unknown. The AGX kext reads
`perf-states`, `perf-state-count` and `perf-states-sram` and builds a
power-transfer table (`AGF_MAX_NUM_PMGR_PERF_STATES`). That code was not
traced here.

## Why this matters for the hang

Test4 powered GFX (PMGR `0x3ff`) and ran GPC init, but nothing in Linux
selects a GFX perf state. The selected state after power-up is unknown; this
table alone does not explain the stalled RGX register access.

Two points argue the other way:

- Apple reads the RGX ID before GPU firmware starts, so on iOS either a
  nonzero state is already selected by then, or the register interface does
  not depend on this clock.
- The contents of `0x20e01c200` (apart from bit 31) are not decoded.

## Proposed next step (needs Martin's go-ahead)

A single read-only PMGR check on a fresh Linux boot: read
`0x20e01c200` and the 16 words at `0x20e01c000`–`0x20e01c0f0` (stride
`0x10`), before and after the GFX power-up used in test4. This only reads
PMGR registers in the block that iBoot and LLB already read and write. It
is the same PMGR register file as the `0x20e020320` power-state reads that
completed in test4. It does not touch RGX, GPC, the bridges or the MCC, so it
stays within the stop rules in
`2026-11-08-j81-next-mcc-experiment-decision.md`. If the control register
shows state 0, the follow-up is offline: find the agent that selects the GFX
perf state on iOS before the ID read.
