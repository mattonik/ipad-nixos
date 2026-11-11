# J81: choosing the next discriminator

Offline decision, no hardware access. The problem is a Linux GPU identity
transaction that did not produce a completion checkpoint after the GFX
power/GPC sequence; the reason remains unknown.

The strongest positive comparison already obtained is narrower than full
equivalence: on separate boots iOS and Linux observed GFX PMGR `0x3ff` and
GPC state `1`; iOS requested the same 66 GFX-thread bridge writes that Linux
issued. Linux has actual readback for only one of those 66 table targets.
The iOS hook records requested stores, not physical acceptance. The extra
27 iOS bridge requests came from different thread contexts and cannot be
attributed to the synchronous GFX provider path. None of this establishes
that the GPU clock, reset, fabric, address mapping or memory attributes match.

The page-5 bit is a repeatable observation at comparable but not identical
boundaries, not yet a demonstrated prerequisite. The global ordinary-writer
tracer captured no matching store, but has a pre-reservation race and covers
only one implementation, object and argument mapping. A negative result does
not exclude a software writer or hardware change. The DWI backlight lead has
no established GFX-rail connection and a DWI-on-before-request Linux test
did not change the bit. Neither is a basis for a guessed write.

## Proposed offline work: provider-to-tuner connection

The iOS 15 static SoC-tuner investigation identifies GFX as one input to a
device set and a possible display/MCC policy response, but it does not show
that the GPU's provider request triggers that policy before the first identity
read. First trace the 19H394 PMGR device-set accounting and callback call
edges, including asynchronous work and guards, from the captured GFX clock
request. Identify whether the event is synchronous, queued, independent or
not reachable on that path. The prelinked executable range is byte-identical
to the earlier analyzed kernel, but runtime binding and data still need proof.

A preliminary search of the already decoded current-boot writer, perf-control
and perf-table logs found no `MCC config`, `New display state`, `soc-tun`,
`MemCacheState`, or `framebuffer cach` message. Logging may be disabled,
filtered or absent from the archive; the missing messages do not prove that
the tuner did not run.

If a specific edge and safe observation point are found, a candidate iOS
instrument could record existing call arguments and completion/return markers
in a bounded buffer, then emit them at the already established later logging
point. It must not add an MCC or GPU register read. A synchronous observed
callback before identity would prioritize its proven effects for comparison;
an absent callback would only narrow the branch if a positive control,
thread/window coverage and buffer publication establish it was observable.
Queued work would require a distinct completion marker and cannot be ordered
from the enqueue alone. Hooking still changes timing and can crash the boot;
this is a decision criterion, not an implemented or reviewed probe.

In parallel, offline-check which bridge target has documented readable,
stable semantics and can distinguish failed persistence from correct setup.
Do not read back all 65 unknown registers or equate reading a command register
with a harmless operation. A fresh core read, an MCC write, or a page-5 bit
write would not by itself explain the failure.

Evidence: [iOS thread attribution](2026-11-10-j81-writer-thread-result.md),
[Linux checkpoint/readback audit](2026-11-07-j81-test4-raw-readback-boundary.md),
[iOS 15 SoC tuner analysis](2026-11-08-j81-ios15-soc-tuner-device-sets.md),
[writer result](2026-11-11-j81-ios-page5writer-result.md), and
[kernel code parity](2026-11-11-j81-19h394-code-parity.md). Full logs remain
private.
