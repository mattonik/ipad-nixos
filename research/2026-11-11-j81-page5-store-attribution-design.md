# J81 page-5 transition: bounded store-attribution design

Offline design only; no probe was built and no device access performed in
this round. The prior iOS 19H394 capture saw page-5 `+4` bit 30 clear at C
before the GPC `0x11` store and set at M after its successful poll. Between
those points, the original same-thread G4G path has no ordinary call. A
[previous writer probe](2026-11-11-j81-ios-page5writer-result.md) saw no
matching ordinary-PMGR store, but its pre-reservation race and limited
object/argument filter make that negative inconclusive. The new same-boot
`+0`/`+4` observation does not distinguish a CPU store from firmware or
hardware either.

## Candidate sites and identity

Use the existing five-point observer and add narrowly guarded instrumentation
at these 19H394 candidate instructions. Instruction bytes and addresses are
from the prior ApplePMGR disassembly; the listed instruction sequences were
also searched in the local 19H394 image and each occurred exactly once.
Uniqueness is necessary, not proof of runtime binding or safe relocation.

| Site | Displaced instruction | Address to compare |
| --- | --- | --- |
| Ordinary reader `0xfffffff006bd04c4` | `ldr w0,[x8,w19,uxtw]` | `x8 + zero_extend(w19)` |
| Ordinary writer `0xfffffff006bd0538` | `str w21,[x8,w19,uxtw]` | `x8 + zero_extend(w19)` |
| Bridge writer `0xfffffff006bd3d4c` | `str w3,[x8,w2,uxtw]` | `x8 + zero_extend(w2)` |

The reader's 24-byte signature beginning at `bd04b0` includes its
PC-relative call at `bd04bc`; validate that instruction in place rather than
relocate it. The two 24-byte writer signatures begin at `bd0524` and
`bd3d38`; the former likewise contains a PC-relative call. Patch only the
final load/store after validating the complete matching context. The reader
retains object in `x22`, region in `w21`, offset in `w19`, instance in `w20`.
At the ordinary writer the corresponding values are `x23`, `w22`, `w19`,
`w20`, with value `w21`; the bridge writer's mapping family is different,
so compare its effective address, not its numeric region/offset arguments.
See the [mapping audit](2026-11-10-j81-page5-writer-mapping-audit.md).

Capture the effective virtual address at the earlier confirmed reader call
for the same saved PMGR object, ordinary region 0, offset `0x5004`, instance
0. Require a successful load, a valid saved address and the normal C and M
samples. Compare each store's resolved effective virtual address internally
to that saved address. Do not export virtual addresses. Exact VA matching
does not catch a different virtual alias of the same physical register, a
different active page mapping, another store implementation or width, DMA,
firmware or autonomous hardware. The live mapping's physical identity and
the object's lifetime remain inferred.

## Bounded events and races

Instrument the two sites independently. Preserve registers, flags, stack,
the original instruction exactly once, exception behavior and return path.
Before a writer executes the displaced store, mark its entry with a bounded
atomic in-flight operation and capture the phase, target-match result and
value; after it returns from the store, publish completion with release
ordering and then retire the in-flight mark. Open the coarse observation
window before invoking C's reader and close it after M's reader returns.
Acquire snapshots, per-site entry/completion counts, in-flight values at
both boundaries and export, bounded reservation failures and buffer overflow
must be reported. A failed reservation must set a sticky failure indication
without an unbounded retry; it cannot silently disappear. Do not wait for
other CPUs, log, allocate or sleep from the global hooks.

An invocation can be interrupted after branching to the trampoline but
before its first counter update: it is not yet counted. The original store
has not yet retired on that path, but it may run after a boundary or never
resume. Do not use an entry count as proof of when the hardware accepted a
write. An in-flight mark at either boundary, incomplete record at export,
contention failure, counter wrap, missing reader target, missing C/M sample,
or buffer overflow makes a no-match result inconclusive. A counter snapshot
alone is insufficient if the original store and bookkeeping can be reordered;
review the actual ARM64 memory ordering and device mapping before claiming
coverage. Added barriers can perturb timing and must be justified rather than
assumed neutral. Concurrent aliases and asynchronous bus behavior remain
outside the result even if every software record is complete.

Positive controls are required for *each* writer site: an always-on seen
counter proves that site was reached, and a tagged synthetic **metadata-only**
event passed through the same matching/publication/export code checks the
target and buffer machinery without an extra register write. Such a control
does not prove a real write to the target occurred, that every CPU was covered,
or that the hardware accepted a store. Preserve the existing identity and
firmware-startup markers. Never label a mere matching in-window record as the
cause of the bit transition without independently tracing its caller and
ordering. For the ordinary writer, its caller's LR is saved on the function
stack; at the bridge leaf the live LR identifies its caller. Verify ABI and
pointer handling before collecting normalized callsite identifiers.

## Decision and host checks

* A matching store completing inside the coarse window is a concrete CPU
  writer and value to investigate, not proof of device acceptance or causal
  ordering. Trace its caller and compare the surrounding provider work.
* A clean no-match with both site controls and all coverage checks rules out
  only the exact instrumented sites and VA under the covered software
  window. It does **not** prove that hardware sets bit 30.
* A missing target/site control, ambiguous edge, incomplete publication or
  unavailable startup archive is inconclusive. Do not turn it into a fresh
  blind write or claim the GPU is ready.

Before any hardware run: validate the exact UUID and each unique signature,
relocation and branch ranges, and fail the entire installation if any hook
cannot be installed. Host simulations should verify the reader's displaced
load exactly once; each writer's store exactly once; correct target and
non-target behavior; both values/phase boundaries; pre-increment interruption,
in-flight boundary and late publication; nested/reentrant and concurrent
writers; contention, wrap, buffer overflow and missing context; and the two
positive controls. Tests must also check register/NZCV preservation and that
missing or duplicate signatures and the wrong UUID prevent installation.
Host simulation cannot validate interrupt context, MMIO effects, mapping
lifetime or target hardware ordering. Extra kernel hooks can stall or reboot
iPadOS and logs may be lost.
