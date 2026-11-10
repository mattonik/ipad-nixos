# J81 iOS writer calls separated by thread

On 2026-11-10 the user booted the [thread-attribution probe](2026-11-10-j81-writer-thread-attribution.md)
on iPadOS 15.8.5 19H394. iPadOS booted, and the private startup archive
was retrieved. The same boot identified G4G A1 and reported GPU firmware
startup success.

The header recorded `B0`, client and aggregate 0 to 15, one GFX entry,
existing target 0 versus requested 15, bridge mode 0 and `W=0x5d` (93
writer calls). There were 93 parsed records, all tagged provider-window
`P1`, instance 0, with no unready markers:

| Selector | Count | Provider-thread match |
| --- | ---: | --- |
| 7 | 10 | `T0`: different thread value |
| 11 | 3 | `T0`: different thread value |
| 6 | 14 | `T0`: different thread value |
| 9 | 33 | `T1`: same thread value |
| 10 | 33 | `T1`: same thread value |

`T1` for selectors 9 and 10 is a positive control that a nonzero provider
thread context was captured. The captured ADT associates 7 with display,
11 with USB, and 6 with ISP; their different-thread result supports the
interpretation that their calls were concurrent device work, not direct
synchronous calls by the GFX provider thread. The result does **not** rule
out an asynchronously scheduled GPU dependency, an interrupt in a matching
thread context, other writers or earlier boot setup. It records request
arguments before the writer call, not completed or persistent stores.

The 66 GFX-thread records reproduce the earlier capture's two bridge tables;
Linux test4 had the same 66 planned writes and reached its after-store
checkpoints. No new missing GPU power-on write sequence is identified by
these 27 extra calls. Continue with evidence outside this global bridge
writer: earlier boot state, remaining provider actions, or a targeted
readback/comparison that distinguishes hardware state without repeating an
unsupported core read.

The private archive and filtered log are under
`artifacts/live/private/ios-logarchive-j81-thread-01/`; full device logs may
contain personal information and must not be published.
