# J81 independent pre-identity path: research round

Offline review on 2026-11-13 of the 19H394 kernel, previous iPadOS captures,
and Linux test4. No new device access. Objective: identify an observed iPadOS
pre-identity operation missing from Linux that can guide an experiment.

## Result

No additional hardware-changing operation has been established on the
ordinary GFX pre-identity path beyond the observed PMGR state request, the
selector 9/10 bridge writes, and GPC setup/poll already attempted on Linux.
That is a bounded finding: software checkpoints do not prove 66 hardware
writes were accepted, and independent threads or firmware can still act.
The `+0x848` device-set candidate is weakened by the actual 19H394 GFX row
and its zero parent IDs; see [the record audit](2026-11-13-j81-pmgr-runtime-record-audit.md).

The iPadOS and Linux GFX perf-control samples after GPC are **both**
`0x80110100`; treating that value alone as a Linux-only pending transition
would contradict the healthy iPadOS capture. The physical meaning of its
fields remains unproven. Likewise, early DWI retention did not reproduce
page-5 bit 30 on Linux ([result](2026-11-13-j81-dwi-hold-gpc-result.md)).
Neither observation excludes another prerequisite.

## Best unresolved software path: message 10

A source-backed *candidate*, not a measured pre-identity event: the iPadOS
PMGR/Nub can reconstruct device-set bitmaps, then notify a receiver with
message 10. GFX is listed as set-0 bit 4 in the captured device-set data.
The candidate tuner can react to the bitmap with a conditional display-idle
and MCC policy; Linux test4 did not implement that Apple software policy.
No evidence yet establishes that this notification occurs or completes before
the first identity read, that its receiver is the candidate tuner at runtime,
or that it controls GPU accessibility.

The registration path `be3b0c` supplies callback `bdc648`. The recovered
callback reconstructs bitmaps and reaches the tail branch at
`0xfffffff006be3c88`: its arguments at that boundary include message 10, a
receiver, and a bitmap pointer; the branch target is receiver vtable `+0x420`.
The candidate tuner table points that slot to `cd8ab0`, which accepts message
10 and forwards to policy `cd827c`; the actual runtime vptr is unproven. This
is distinct from the per-set message-11 path.

Previous tuner probes hooked `cd827c` entry/return, and both the identity
export and later firmware-success export recorded zero events **and zero
positive-control hits**. They did not instrument the Nub-side dispatch.
Thus they do not establish either absence or presence of the message-10
path. The later export is not a guaranteed positive event and occurs after
identity.

### Discriminating observation to design, not yet a ready test

A bounded, nonblocking record at the Nub-side tail dispatch could capture
actual target address, message, bitmap, thread and ordering relative to the
existing provider and identity markers. Seeing the target equal the candidate
tuner handler with GFX bit set before identity would establish a concrete
software path to investigate; it would not by itself prove policy completion
or causal relevance. The tail branch has no local return; separately recorded
handler completion would be needed to support that claim.

There is **no known guaranteed positive dispatch event in the observation
window**. A synthetic record can verify buffer publication but cannot prove
an original runtime path ran. A zero dispatch count without a genuine matched
positive event and timing coverage remains inconclusive. The hook would alter
execution in a potentially locked context: before building, prove displaced
instruction/ABI preservation, bounded atomic recording, exact build identity,
thread/phase coverage, and safe export without logging or MMIO in the hook.
No PMGR, MCC or page-5 write follows from this hypothesis.

## Alternative: narrower page-5 timing

The current iPadOS `page5-control` probe records `C=0` before the GPC request
store and `M=0x40000000` only after the successful poll. An additional sample
after the request store but before the first poll could split that interval.
The candidate displaced instruction is the first poll load; a new hook must
execute that original load exactly once and not interfere with the existing
poll-branch hook. Its address/signature must be rechecked against the exact
19H394 input before implementation. The extra method call and MMIO read
delay polling and can change the observed transition or stall the device.
This observation narrows timing but does not identify the writer or explain
the Linux stall; prioritize it only if the result changes a concrete decision.

## Other bounded results

- The optional PMGR timing-record path is not a demonstrated setup write.
  Its `hw-dpe-reg` property and runtime limits are described in
  [the correction](2026-11-12-j81-hw-dpe-provider-trace.md); an alternate
  record pointer's physical meaning remains unresolved.
- iOS selector 7/11/6 calls appeared on other threads, while the GFX thread
  supplied selector 9/10 positive controls. This weakens a direct GFX-call
  interpretation, not all asynchronous or shared-domain explanations.
- Source-derived Linux and iOS initial mappings both indicate Device-nGnRnE
  under the inspected conditions; actual live PTEs/aliases remain unverified.

Sources: `ios15pmgr-tuner-callback.c`, `ios15pmgr-tuner-link.c`, prior probe
captures and private IORegistry under `artifacts/live/private/`; see
[positive-control audit](2026-11-11-j81-tuner-positive-control-audit.md),
[tuner-later result](2026-11-11-j81-ios-tunerlate-result.md),
[writer thread result](2026-11-10-j81-writer-thread-result.md), and
[page-5 capture results](2026-11-10-j81-page5-capture-results.md).
Do not publish Apple binaries or private device logs.
