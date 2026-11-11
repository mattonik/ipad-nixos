# J81: GFX perf-state control after GPC state 1 (2026-11-10)

One read-only sample on the Linux boot that ran the
[in-kernel GPC/page-5 test](2026-11-10-j81-gpc-page5-kpoll-test.md)
(boot `5c3f6218`, GPC left at state 1, GFX PS `0x3ff`, uptime about
12,700 s, roughly 3.5 h after the `0x11` request). Labels: **E** measured or
read in source, **I** inference, **U** unknown.

## Measurement

Preflight `perf-peek` GO. The same static tool as the 2026-11-09 runs
(`gpu-pmgr-perf-peek`, sha256 `d2ef11e1...`, `/dev/mem` read-only, 34 words in
the perf block plus the GFX PS word). No writes, no GPU core access, no page-5
access. The device stayed up.

| Word | Before any GPC request (2026-11-09) | After GPC state 1 (this run) |
|---|---|---|
| `0x20e01c200` (GFX perf-state control) | `0x80000000` | **`0x80110100`** |
| `0x20e01c000 + n*0x10` (table) | LLB values | unchanged |
| `0x20e01c004 + n*0x10` | `0x70/0x70/0x70/0x80` twice | unchanged |
| `0x20e01c300` | `0x40000001` | unchanged |
| `0x20e020320` (GFX PS) | `0x3ff` | `0x3ff` |

This is the first observation that the GPC state request reaches the PMGR
GFX perf-state block on Linux (E). The 2026-11-09 conclusion "no
selected-state record in this block" was true only because no state had been
requested yet.

## Reading of `0x80110100`

- bit 31: enable, set by LLB (E, LLB disassembly).
- bits 11:8 = `1`: matches the requested state 1 (low nibble of the `0x11`
  GPC request) (I).
- bits 3:0 = `0`: a current-state field still at 0 (I).
- bits 23:16 = `0x11`: non-zero. On Apple SoC perf-state control words of
  this generation a non-zero field here means a change is still pending (I,
  by analogy; not confirmed for this register).

If that reading holds, the GFX perf-state machine accepted the request for
state 1 and has been stuck mid-transition for hours. That would explain
both open observations at once: page-5 `+4` bit 30 never sets on Linux, and
the GPU core is not clocked when it is read.

## Why page 5 fits

The LLB sequence around page 5 (poll bit 25 of `+0`, clear bit 0 of `+4`,
set bit 24 of `+8`, then set bit 31 of `0x20e01c200`) is the shape of
handing a PLL to a perf-state table (E for the writes,
[LLB dataflow note](2026-11-09-j81-llb-page5-clock-dataflow.md); I for the
meaning). PMGR pages 0 to 5 then are the PLLs, page 5 the GFX PLL, and bit 30
of `+4` a hardware "running" status rather than a software-written bit (I).
The parallel iPadOS work found no same-thread call between the `0x11` store
and the poll that could write it
([writer lead](2026-11-10-j81-page5-change-ios-writer-lead.md)), which is
what a hardware status bit predicts.

## What could block the transition

The ADT `sgx` perf-states say state 0 is 0 Hz at 600 mV and state 1 is
365 MHz at 912 mV (E, private ADT). A state change therefore needs a GPU
rail voltage change before the PLL may run. Candidates, none tested:

1. **DWI is clock-gated on Linux.** The PMGR sends rail voltage changes to
   the PMU over DWI (I). Linux genpd shows `dwi` (PS `0x20e020120`) off on
   this boot (E); iPadOS uses the same block for the backlight (E, ADT
   `function-backlight_update`). A voltage request that cannot leave the SoC
   would leave the transition pending.
2. m1n1 `cpufreq_init` writes `PMGR+0x23000 = 1` (voltage control), which
   iOS does not do at boot (E,
   [pre-Linux write audit](2026-11-09-j81-pongo-m1n1-pre-linux-writes.md)).
3. Something else the state machine waits on (U).

## Proposed next test (needs a go-ahead, it is a write)

On a boot where GPC state 1 is pending (this one qualifies), switch the
`dwi` power state on (`0x20e020120`, the same kind of PS write Linux already
does for other blocks), then re-read `0x20e01c200` with the same tool. If
the pending field clears and the low nibble becomes 1, read page-5 `+4`
once through the already-reviewed in-kernel path on a fresh boot. Risks: the
GPU rail steps to its state-1 voltage as on iPadOS, and the device may hang
and need DFU. Still no GPU core read and no page-5 write.

Private capture: `artifacts/live/gpu/perf-peek-after-gpc1-20261110/` on the
Mac (not in Git).

## Prepared, not run (2026-11-11)

Tool `boot/pmgr-dwi-on.c` (host test `boot/test_pmgr_dwi_on.py`): maps only
the PMGR power-state page, reads `0x20e020120` after a `READ` acknowledgment,
sets the low nibble to `0xf` after a separate `WRITE` acknowledgment, polls
the actual-state nibble for up to 100 ms and prints the result. Static build
`pmgr-dwi-on-static`, sha256 `0fa25237...ab65258`. Private bundle with a
staging file on the Mac: `artifacts/live/private/j81-pmgr-dwi-on-bundle-v1/`
(the staging file was decoded locally and reproduces the same hash).

Run order, on a boot where GPC state 1 has been requested:

1. `boot/j81_preflight.sh perf-peek` must say GO.
2. Run the staged `gpu-pmgr-perf-peek2`; continue only if `ctl` reads
   `0x80110100` (the stuck state).
3. Stage `pmgr-dwi-on`, check its hash on the device, run it, answer `READ`
   and then `WRITE`.
4. Run `gpu-pmgr-perf-peek2` again and compare `ctl`.

A boot that has lost `/tmp` or was rebooted needs the kpoll `immediate`
campaign first to get back to the pending state.

## Result of the dwi test (2026-11-11, boot `2d2da8d6`)

Fresh cycle-payload boot, preflight `gpc-page5-kpoll` GO. Sequence and
values, all E:

1. kpoll `immediate`: GPC state 1 on poll 11 (294 to 296 us after the
   `0x11` store), page-5 `+4` = `0x00000000`. Same as boot `5c3f6218`.
2. Perf block about a minute later: `ctl = 0x80110100`. So the value appears
   right after the request, not slowly, and reproduces across boots.
3. `pmgr-dwi-on` (hash checked on the device): `0x20e020120` read
   `0x00000200` (target 0, actual 0), then after the write `0x000000ff`
   (target 15, actual 15) on the first poll.
4. Perf block again: **`ctl = 0x80110100`, unchanged.** GFX PS `0x3ff`,
   `0x20e01c300 = 0x40000001`. Device stayed up.

Switching the `dwi` clock gate on does not move the control word. Candidate
1 in its simple form is ruled out. It does not rule out a DWI block that is
clocked but not configured (iPadOS has a driver for it; Linux has none), and
it does not test the reading of `0x80110100` itself: the word might also be
a completed state, with the non-zero bits in 23:16 meaning something other
than "pending" (U).

## Next discriminator

The cheapest decisive datum is the same word on iPadOS. The existing iOS
probes already read PMGR region 0 through the ordinary reader, so a sample
of offset `0x1c200` at the `C` and `M` points (optionally `0x20120` and
`0x23000`) says whether a healthy GPU shows a different value. If iPadOS
also reads `0x80110100`, this register is not the lead and page 5 stays the
only known difference. If it differs (for example low nibble 1 or bits 23:16
clear), the Linux transition is confirmed stuck and the difference tells
which field to chase.

Private captures: `artifacts/live/gpu/gpc-page5-kpoll-20261111-01/` and
`artifacts/live/gpu/dwi-on-20261111-01/` on the Mac.

## iPadOS comparison (2026-11-11): the word is the same

The [perfctl probe](probes/j81-perfctl/README.md) (module sha256
`ebb30acc...`) ran on a temporary 19H394 boot. iPadOS reached the Home
screen. Latest-boot records (E):

| Point | iPadOS `0x1c200` | Linux |
| --- | --- | --- |
| early `Q`, `T`, `C` (before the `0x11` request) | `80000000` | `80000000` |
| `M` (after the GPC poll) | `80110100` | `80110100` |
| late `Q` (after GPU identity) | `80110100` | `80110100` |

`0x80110100` is therefore the normal value after a state-1 request on a
working GPU. The "transition stuck pending" reading above is wrong and the
voltage/DWI candidates built on it have no support. The perf-state control
word is not a difference between the two systems; page-5 `+4` bit 30 stays
the only known one. Private archive:
`artifacts/live/private/ios-logarchive-j81-perfctl-03/` (the `-01` and `-02`
directories are an empty and a truncated attempt).

Follow-up prepared, not run: the [perf-table probe](probes/j81-perftab/README.md)
compares five static words (state-1 table entry, `0x1c300`, voltage control,
`dwi` power state) in one boot.
