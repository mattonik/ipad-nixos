# J81 corrected iOS bridge capture: 66 requests match Linux test4

On 2026-11-10 the user booted the [corrected records probe](2026-11-10-j81-ios-corrected-bridge-probe.md)
on iPadOS 15.8.5 19H394. The iPad returned to iPadOS; its private startup
archive was collected. The same boot reported G4G A1 and successful GPU
firmware startup.

The probe printed `B0`, client and aggregate 0 to 15, one GFX transition,
target 0 to 15, bridge mode 0, and `W=0x5d` writer calls during the GFX
provider window. It recorded **66** selector 9/10 requests without buffer
overflow: 33 for selector 9, then 33 for selector 10, all instance 0.
Both start with offset/value `0x18=0x80010004`, followed by 32 pairs at
`0x40000` through `0x4007c`. All offset/value pairs are identical across
the two selectors. There were no unready record markers in the filtered log.

A local exact comparison of selector, instance, offset, value and order
found all 66 equal to `gfx-bridge-static-plan.json`, which was extracted
from the iOS 8.1 J81 device tree. Using the documented J81 selector bases,
another exact comparison matched all 66 Linux test4 **before-store**
checkpoints, in order and value; all 66 after-store checkpoints are present.
This moves the earlier format-0/table prediction to a directly observed
iOS 15.8.5 writer-request result. It does not establish iOS physical
addresses independently of the selector mapping.

The hook records arguments before the writer call; the captures are not
reads verifying that all iOS stores completed. Linux checkpoints show code
progress beyond the stores, not that all values persisted; prior test4
readback confirmed only one bridge entry. The 93-call count covers all
writer dispatches during the provider call, whereas the 66 records cover
selectors 9/10 from KPF installation through provider return; the 27-call
difference must not be assigned to specific selectors or phases without
another capture. Hooks are global and concurrent unrelated events remain
possible. The result confirms this table path was used; it does not prove
the surrounding iOS and Linux initialization or hardware state are equivalent.

## Implication and next work

The precise bridge-table values and order are no longer a strong explanation
for Linux's stalled first GPU identity read. Investigate state outside those
66 requests: additional writer calls or earlier boot setup, unverified store
persistence, the clock/power provider's other operations and mapping or
hardware state. Prior timed and host-paced core-read tests also stalled; a
repeat core access is not justified by this table match alone.

The full archive and filtered log are private under
`artifacts/live/private/ios-logarchive-j81-records-01/`. They may contain
personal device information and should not be published. The compared test4
transcript is `artifacts/live/gpu/clock-table-20261107-test4.log`.
