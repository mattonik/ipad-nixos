# J81 next discriminator: PongoOS versus Linux RGX read

## Decision

Do not make another PMGR, bridge, GPC, DWI, or page-5 write.  The completed
bare-PongoOS control already reached the same PMGR/bridge/GPC endpoint as the
Linux diagnostic, including GPC state 1, while page-5 `+0x5004` remained
clear.  Replaying another word would not distinguish the remaining causes.

The next useful hardware experiment is one guarded read of RGX revision
`0x201000020` from **PongoOS**, after that already proven no-core preamble.
The existing `boot/pongo_gpu_split.py` runner stops on every unexpected
precondition, performs no core access until its final step, and issues no
second core read if the revision read does not answer.  Its host-only test is
`boot/test_pongo_gpu_split.py`.

## Why this is discriminating

The Linux test reached PMGR `0x3ff`, the 66 recovered bridge stores, GPC
state 1 and control `0x40000000`, but its first `/dev/mem` revision read did
not return.  The PongoOS control has independently reached the same recovered
state sequence without Linux userspace or the Linux PMGR driver.

| PongoOS revision result | What it narrows |
| --- | --- |
| Read answers | The remaining primary difference is the Linux access path: its physical mapping, MMU/translation attributes, or Linux handoff, rather than the recovered PMGR/bridge/GPC sequence alone. |
| Read hangs | The recovered sequence is insufficient below both Linux and PongoOS; investigate missing platform/firmware state before changing Linux mapping policy. |

Neither result proves a complete driver, establishes page-5 bit 30 as a
control, or makes a second core access safe.

## Checked rejection: PMGR auto policy

This pass also checked whether Linux's explicit auto-PM write was an
unreplayed iOS difference.  It is not a sound next test.  The working iOS
PMGR poll and Linux poll have both returned `0x3ff`; the hardware readback
does not expose a useful policy difference.  More importantly, the exact
Apple state helper's policy argument depends on the device-record flags, and
the local records/older notes disagree on those flags across captures.  A
manual `0xf` versus `0x100000ff` variation would therefore be a weak replay,
not an evidence-led experiment.

## Safety boundary

The final PongoOS revision read can wedge the USB transport or PongoOS.  It
does not mount a filesystem or write the RGX core, and recovery is a forced
restart into DFU, but it is still a disruptive hardware test.  Preserve the
runner transcript, do not retry in the same boot, and do not continue to the
second identity read after any anomalous output.

Inputs: [bare PongoOS control](2026-11-16-j81-pongo-gpc-page5-result.md),
[Linux core-read boundary](2026-11-07-j81-core-revision-after-clock-test4.md),
and [core-map provenance](2026-11-07-j81-core-map-provenance.md).
