# J81 iOS 15.8.5 matrix capture result

> Correction: the writer filter described below tested instance index 15,
> not requested state 15. See the later [dispatcher capture](2026-11-10-j81-ios-dispatch-capture-result.md).

On 2026-11-10 the user booted the temporary rootless matrix module documented
in [the morning plan](2026-11-09-j81-overnight-research-and-morning-batches.md).
The iPad returned to iPadOS and its private startup log archive was captured.
The relevant messages from the same startup are:

```text
AGXk: Starting GPU driver. Available features: release
AGXk: Starting GPU driver. Available features: B0 D1:00000000>0000000f A1:00000000>0000000f N1:00000001
AGXk: Probing - Detected G4G A1 [...]
AGXk: ... GPU firmware booted successfully (AGXFirmwareKextG4G)
```

`D1` records the client software cache as 0 with request 15. `A1` records
the prior aggregate software state as 0 with an effective request of 15;
`N1` records one dependency-list entry. The aggregate values are printed
old then requested (the earlier preparation note had this order reversed;
it is now corrected). The selector 9/10, state 15 writer-request buffer
reported no records and no overflow (`B0`). These are software observations,
not hardware power-state measurements.

For this boot, this rules out the proposed explanation that the aggregate
was already at 15 and so no transition was constructed. It does not prove
that the transition dispatcher actually executed or determine which device
the sole list entry represented. The zero writer result is limited to the
instrumented path, selectors, state argument and capture window; the writer
hook still has no positive on-device control. A matching dispatch elsewhere,
another writer or an instrumentation failure remains possible. GPU firmware
startup was reported, but that is not an independently verified workload.

Next inspect and instrument, with a positive control, the existing dependency
entry and dispatcher path: device ID and requested state, prior PMGR target,
bridge mode and the branch which selects or skips the writer. Prepare a
bounded probe after checking the relevant branch and call signatures; avoid
assuming that the sole dependency-list item is GFX or that no bridge write
occurred. No further hardware test was performed in this boot.

The full archive and filtered log are private under
`artifacts/live/private/ios-logarchive-j81-matrix-01/`; the full archive may
contain personal system data and must not be published.
