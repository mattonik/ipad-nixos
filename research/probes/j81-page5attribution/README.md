# J81 page-5 writer attribution

This experimental probe extends the
[previous writer tracer](../j81-page5writer/README.md) with a hook on the
19H394 ordinary PMGR reader and a second hook on the bridge writer. It
captures the reader's effective address privately and compares ordinary and
bridge store effective addresses against it. It retains the earlier five
page-5 observations and records matching stores, phase and value without
printing kernel addresses. See the
[design and coverage limits](../../2026-11-11-j81-page5-store-attribution-design.md).

The target address is accepted only for the saved PMGR object and
region/offset/instance used by the page-5 probe. `Y=` reports target
availability, bridge-site activity, in-flight snapshots at the window
boundaries and export, accounting failure, and whether the target was
available before the C read. `Z=` reports phase, ordinary-site activity,
reserved event count and overflow. `W=` reports a published record: its
first two fields combine phase with site tags `0x100` (ordinary) or `0x200`
(bridge); the third field is the value. Records tagged `0x400` are synthetic
metadata, not hardware writes. `W=UNREADY` means incomplete publication.
Each real displaced load or store is executed once. An ordinary-path
synthetic event at identity exercises address comparison, reservation and
publication without executing the store. A separate bridge-path synthetic
event exercises its matching, reservation and publication without executing
the bridge store. Both controls share a one-shot claim.

No-match **does not establish absence of a writer**: a CPU can be delayed
before the accounting instructions, virtual aliases or other store sites
can bypass these hooks, and firmware or hardware may change the word. The
captured virtual address and physical cross-reference remain inferred.
Positive site activity does not prove target coverage. Incomplete records,
overflow, missing controls, nonzero in-flight boundary snapshots, or an
absent target before C make a negative result especially inconclusive.

The local module is
`artifacts/live/private/j81-ios-page5attribution-probe/page5-attribution`,
SHA-256 `eb4cd3011f031617f030ac83517e18457375ee106fbf35e5836901384c38127a`.
It was built in the [pinned Pongo checkout](../j81-thread/README.md), with
`j81_page5attribution_capture` registered and
`KPF_CFLAGS=-DJ81_PAGE5ATTRIBUTION_DEVICE_BUILD`. The 19H394 KPF harness
accepted the target and rejected each of 14 individually missing and 14
duplicate signatures and a wrong UUID. Native ARM64 tests exercise the
effective-address match, both real stores, a nonmatching store, overflow,
target changes, phase capture, synthetic publication for both paths without
an MMIO write, repeated identity callbacks, incomplete records, nonzero
in-flight snapshots at both window boundaries and export, and 20 concurrent-
reservation runs. The saved host assembly replaces privileged operations
and kernel calls; these are not hardware tests.

An independent static review checked the three hook instructions, register
and flag preservation, stack alignment, buffer bounds, both synthetic paths,
and the boundary tests. It did not validate interrupt timing, mapping
lifetime, hardware ordering or actual kernel stack headroom. Verify the
checksum before use. Global kernel instrumentation and undocumented reads
may hang or reboot the iPad, and logs can be lost. The module has not run on
hardware.
