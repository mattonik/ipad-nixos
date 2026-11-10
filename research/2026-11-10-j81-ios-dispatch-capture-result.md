# J81 iOS dispatcher capture and writer-filter correction

On 2026-11-10 the user booted the temporary rootless dispatcher module from
[the probe plan](2026-11-10-j81-ios-dispatch-probe.md). The iPad booted and
its private log archive was retrieved. The startup included:

```text
AGXk: Starting GPU driver. Available features: B0 D1:00000000>0000000f A1:00000000>0000000f N1:00000001 L000f007c X1:00000000>0000000f M00000000 W0000005d
AGXk: Probing - Detected G4G A1 [...]
AGXk: ... GPU firmware booted successfully (AGXFirmwareKextG4G)
```

The client and aggregate software states went from 0 to a request of 15;
one transition-list entry encoded GFX device ID `0x7c` and request `0xf`.
At the dispatcher comparator, the existing hardware PMGR **target nibble**
was 0 and the request was 15, selecting the increasing branch; the PMGR
object's bridge mode was 0. `W=0x5d` means the instrumented virtual writer
dispatch was reached 93 times during the GFX provider call. The count is a
global window and may include concurrent unrelated calls; it does not prove
that the 93 stores completed. GPU firmware startup was reported in the same
boot. No extra PMGR or GPU MMIO was performed by the instrumentation.

## Important correction: filter used an instance as a state

The older bridge, wide, matrix and dispatcher probes filtered the writer
call with `w4 == 15`, describing `w4` as the requested power state. That
interpretation was wrong. In the static instruction trace, the table writer
at `bd3dc8` copies its third argument `x2` into `x19`; it uses `x19` as an
instance index when selecting a bridge table (`bd3e18`), then passes `x19`
in `x4` to the virtual writer at `bd3e58`. The higher-level caller
`bd90a8` also carries this third argument through to the table writer.
Thus `w4` is the instance/index argument, not a state. The filter does not
test for a state-15 transition and can exclude the very writes of interest.

This affects the previous negative captures: **no conclusion that the
selector 9/10 tables were not dispatched follows from their absence**.
The new 93-call count is positive evidence that this hook executes, but it
does not reveal those calls' selector, instance or data. This is consistent
with a faulty filter; it does not by itself prove which selector or instance
was used or which writes completed. Correct next capture: record all calls
with selectors 9/10 without a state filter, including the actual `w4`
instance, offsets and values, while retaining buffer overflow detection.
Compare those records with the previously extracted iOS table and Linux's
attempt; do not guess a new hardware sequence from this result.

The full archive and filtered log are private under
`artifacts/live/private/ios-logarchive-j81-dispatch-01/`, since they may
contain personal data. No new capture beyond the dispatcher test was run.
