# Review of J81 DWI and PMU measurements

Offline review of PR #38 branch `9c141fd`, its saved Linux capture, and the
local Linux PMGR/genpd sources. No device accesses were made for this review.

The saved same-boot comparisons support a useful new observation: with DWI
state `0x200`, the two sampled PMU rows did not follow changes in the
corresponding PMGR words across CPU governors; after the DWI state was switched
to `0xff`, both followed the sampled words. For example, PMGR `0x23010` and
PMU `0x0100` changed from `0x16d`/`0x9c` to `0x16d`/`0x6d`. The second
observed pair also changed together. These correlations strengthen the case
that DWI participates in voltage requests. They do not independently prove
which physical rail each PMU row controls, actual voltages, that all DWI
transactions succeeded, or that a GPU request was missed. In particular, the
identity of buck 1 as the GPU rail and the meanings of its bytes remain
inferences. The earlier DWI-on-before-GPC test observed page-5 bit 30 clear;
it did not measure that PMU row.

The claim that `pd_ignore_unused` may not prevent provider synchronization has
specific source support: the local `drivers/pmdomain/core.c`
`genpd_power_off_unused()` returns early for that option, whereas the separate
`of_genpd_sync_state()` clears `stay_on` and calls `genpd_power_off()` without
checking it. This is consistent with the observed boot accounting, but does
not prove which particular callback switched DWI off on the captured boot.
The local Apple PMGR driver recognizes `apple,always-on`; a proposed device
tree change still needs its own build and validation.

## Test choice and tool review

A fresh-boot DWI-on-before-request run **with pre- and post-request PMGR and
candidate PMU buck observations** is the most direct test of the new GPU
voltage hypothesis. Compare the same rows at the same boundaries, keep the
previous Linux test as a control, and use the existing guarded GPC/page-5
capture. A changed candidate byte is evidence about that register, not proof
of its rail identity or an actual voltage. An unchanged byte does not by
itself establish that the PMU rejected a GPU request: the row, request path,
measurement timing and byte semantics remain uncertain. Individual PMU reads
can have side effects; the prior full dump cleared observed event bytes, and
only specifically justified rows should be sampled.

The proposed 20-domain restore could be a separate high-risk experiment,
but it would vary many inputs and its positive result would not isolate DWI.
It is also not equivalent to an ordinary genpd transition: the reviewed
`pmgr-ps-restore` reads a word and writes `v | 0xf` via `/dev/mem`, without
acquiring the genpd/regmap lock or updating Linux's power-domain bookkeeping.
The local Apple PMGR driver's power-on path clears AUTO_ENABLE and historical
flags before writing the target, polls, and then sets AUTO_ENABLE. Thus the
raw tool's write is not the same sequence as that Linux driver, and Linux can
later change a manually restored domain. The host test passed and the staged
binary matched its recorded hash, but those checks do not establish safe
semantics, dependency ordering or ownership for the other 19 domains. Its
previous device dry run refused writes and did not validate those transitions.
Do not interpret host acknowledgments or a returned `actual=15` as proof that
an individual domain or its consumers are safe.

The single iPadOS GPC timing sample and Linux sample are close only if the
unverified 24 MHz iPadOS conversion is applicable, and their hook boundaries
and polling behavior differ. They do not establish equal hardware latency or
prove that page-5 bit 30 is a PLL-running status. The existing captures
support investigating that as a hypothesis, not a confirmed register name.

Private inputs: `artifacts/live/gpu/pmgr-words-20261111-boot288e-after-bridge10/`
and PR #38's `research/2026-11-11-j81-dwi-voltage-transport.md`. Full device
logs and PMU dumps are not included in this note.
