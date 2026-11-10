# J81 iOS page-5 writer: store-site design

Offline analysis of the exact 19H394 kernel image and the existing
[five-point probe](probes/j81-page5control/README.md). No code was patched,
no hardware was accessed, and this is not a validated or runnable probe.

## Candidate store site

The candidate ordinary PMGR 32-bit write method `+0x988` at `bd04f0` first
validates and resolves the region/instance. Immediately before the actual
store at `0xfffffff006bd0538`, the inspected instructions give:

| Register | Meaning at this store |
| --- | --- |
| `x23` | PMGR object |
| `w22` | region selector |
| `w19` | byte offset |
| `w20` | instance |
| `w21` | requested 32-bit value |
| `x8` | resolved mapping base |

The instruction is `str w21, [x8, w19, uxtw]` (`0xb8334915`). The six
consecutive 19H394 instruction words at `bd0524`–`bd0538` are
`aa1703e0 aa1603e1 aa1403e2 97ffdc2d f9400c08 b8334915`; this exact
24-byte sequence occurs once in the private full kernel image. The fourth
word is a PC-relative call and must be validated in place, not blindly moved.
A store-site trampoline could branch at the final word, match `x23` against
the internally saved PMGR object, `w22=0`, `w19=0x5004`, and `w20=0`, then
execute the displaced store exactly once and resume at `bd053c`. It must
preserve all affected registers, NZCV, stack alignment, memory ordering and
fault behavior. Do not publish the pointer. The static candidate vtable and
argument layouts are documented in the [mapping audit](2026-11-10-j81-page5-writer-mapping-audit.md).

This site observes the **actual store instruction**, a stronger boundary than
the earlier bridge call-site trace. A before-store record only shows intent;
a post-store record shows that execution resumed after the instruction, but
still does not prove a device accepted the write or that the value persisted.
It sees only calls reaching this exact implementation and instance. The
runtime PMGR object and its mapping are not independently proven. Other
ordinary PMGR objects, aliases, direct stores, bridge mappings, other kexts,
firmware and hardware can all escape this hook.

## Window and concurrency pitfalls

The existing `C` and `M` samples are actual PMGR reads in separate injected
wrappers, not instantaneous logger lines. Opening a phase flag only *after*
`C` returns leaves a blind interval between the MMIO load and publication;
closing it *before* the `M` load leaves another. A safer coarse observation
window would open **before** invoking the `C` reader and close **after** the
`M` reader returns, so the target interval is enclosed. Store-hit records
near either edge must be tagged ambiguous rather than asserted between the
actual reads. Existing hooks permit missing C or M when guards fail; both
sample-valid flags, explicit open/close markers, and no overflow are necessary
for interpreting a capture, but cannot establish a negative: a writer can be
delayed before reservation until after the snapshot. A stalled hook may lose
every buffered record.

Concurrent CPUs can enter a trampoline before a boundary and execute its
store after it. Release/acquire flags and a bounded reservation buffer improve
publication but do not turn software phase snapshots into a global physical
ordering guarantee. Track in-flight entry/exit or conservatively mark boundary
races inconclusive; do not spin waiting for other CPUs in an interrupt or
unknown lock context. Because the hook is global and may run on IRQ paths, it
must avoid printing, allocation, sleeping, SIMD and unbounded waits. Preserve
the 4096-byte existing buffer's fields; the last observed fixed field is at
`3696`, but any reuse of remaining space requires a full static layout audit.

An always-on, bounded total counter for the candidate store site provides a
positive control only if its count is nonzero on that boot; no call to the
specific filtered address is not proof that the hook is active. Counts and
filter records must not replace existing sample checks or exceed the buffer.
Capturing callers, if needed, should use normalized offsets only and be kept
private until reviewed for identifying information.

## Decision and next work

This is a more discriminating design than filtering the `+0x998` bridge
writer with ordinary-region arguments. Before building it, validate the exact
19H394 site, choose a no-loss phase/buffer protocol, review actual call and
exception contexts, and write native host tests for target matching, displaced
store exactly once, invalid or duplicate signatures, boundary races, overflow
and incomplete publication. The exact UUID, KPF branch reachability, saved
object lifetime and all-or-nothing patch guards remain necessary. If a matching
completed store occurs in the coarse window, follow its caller and the written
value. If none is recorded, the outcome is inconclusive; do not infer that the
bit must be a hardware status or replay a write on Linux.

An experimental [store tracer](probes/j81-page5writer/README.md) has now been built and host-tested; cross-CPU pre-reservation races remain a limitation and it has not run on hardware.
