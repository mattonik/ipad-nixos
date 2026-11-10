# J81 iPadOS 15.8.5 boot-time observation hook: design review

2026-11-09. This is a proposed design, not an implemented hook or a tested
boot procedure. The user reports iPadOS 15.8.5 build 19H394. Addresses below
are unslid virtual addresses in the archive's decoded kernelcache, not
absolute runtime addresses. The [build comparison](2026-11-09-j81-ios1585-kernelcache-comparison.md)
shows that the previously examined GPU and PMGR code slices are identical
in the 19H394 and 19H422 archive images; live kernel and data identity remain
unverified.

## What it could answer

An instrumented working iOS boot could tell us whether the G4G probe reaches
its clock, power, GPC and RGX-read stages and what values those *existing*
reads return. A second PMGR hook could record the actual bridge write requests
for selectors 9 and 10. Comparing them with Linux checkpoints would identify
specific differences or increase confidence in the existing comparison.
Neither a matching trace nor a successful identity read proves the GPU clock
frequency or explains all earlier boot state. A write-request record does not
prove that a device completed a write or retained its contents.

## Boot and instrumentation path

1. From DFU, load a known-compatible PongoOS and a **temporary** KPF module.
   PongoOS's patchfinder runs before XNU. The documented palera1n
   [`--override-kpf`](https://github.com/palera1n/palera1n/blob/main/docs/palera1n.1)
   option is a possible way to select a custom module, but compatibility of
   our binary, module, and this device's iOS boot path is not yet proven.
2. KPF verifies the expected image, finds exactly one copy of each selected
   instruction pattern in its intended image/section, and checks the
   original instruction bytes and surrounding control flow. On failure it
   must **decline to install this custom instrumentation**; the behavior of
   the larger stock boot chain on such a failure must also be decided and
   tested. A signature match is not an integrity check of the full running
   kernel or a guarantee that another component will not later patch it.
3. The patcher reserves suitable *executable* storage for trampolines and
   separately establishes an explicitly owned, writable, initialized record
   buffer whose lifetime extends until it can be read. The existing KPF
   component framework has `shc_size`/`shc_emit`, and its dyld component
   emits shellcode and checks AArch64 branch reach. That is a useful pattern,
   not proof that this image has enough safe space or a writable buffer.
   Never assume executable kernel text is writable at runtime.
4. At a selected site, a branch enters a short trampoline, which records the
   required values, executes the displaced instruction(s) with equivalent
   semantics, and resumes the original control flow. It must preserve all
   registers and flags live at that exact site, stack alignment, LR, and any
   affected architectural state. PC-relative instructions and branch targets
   require correct relocation; a single-instruction patch is not automatically
   safe. AArch64 `B`/`BL` immediate reach is roughly ±128 MiB and must be
   checked against actual slid locations. No extra GPU MMIO reads or writes
   are required for the proposed first observations.
5. A separately verified post-boot readout retrieves the buffer to the Mac.
   Without a working transport, the hook has no useful result. Ordinary RAM
   may be lost on a panic or reboot.

## Candidate records and precise boundaries

| Point | Candidate site | Data available / meaning |
| --- | --- | --- |
| Clock request | `0xfffffff006683918`, with a separate point after `...3930` if needed | Path entered; at the return boundary `w0` is the existing provider return value. Entry alone does not prove the call returned. |
| Power request | after the existing `blr` at `...394c` | Existing `w0` return and caller's output slot at `sp+0x30`, after validating their lifetime and types. Neither is a physical power measurement. |
| GPC state request | around `...3994`–`...39a4` | Record the existing command `0x11`; after the existing poll, capture the last value already loaded by the driver. The poll's branch and the 10 µs delay must retain their behavior. |
| Identity results | after existing loads at `0xfffffff00669bb58` and `...bb5c` | The first load places RGX `+0x20` in `w9`; the second places `+0x18` in `w8`. A record after both shows both returned; a separate record immediately after the first distinguishes a first-read stall from a second-read stall. |

These sites need individual instruction/liveness analysis. The existing three
16-byte match-only signatures cover target discovery; they do **not** cover
all these distinct before/after record sites. A hook after both identity
loads alone cannot tell which load stalled. iOS's values on this working
path would be baseline observations, not a safe suggestion to read them
again while Linux is in a different power state.

For bridge writes, a later, separate experiment could intercept the existing
indirect call at `0xfffffff006bd3e58`, where the caller has selector in
`x1`, offset in `w2`, value in `w3`, and state argument in `x4`. Log only
selectors 9 and 10 and include a sequence number and context identifying the
GFX request; selector alone may match other callers. A before-call record
means a request was about to be dispatched, not that the write completed.
A return record adds evidence of return, not readback. This site is in a
loop and could run under synchronization; avoid calling a potentially blocking
logger or adding register reads there. The exact concurrent context and
filter remain to be established.

A minimal bounded record format could contain `sequence`, `event`, `flags`,
and two or three fixed-width values. Reserve fixed per-CPU slots or use a
proved nonblocking reservation protocol; publish each completed record only
after its fields are written. Include overflow/partial-record indicators.
Do not assume ordering across CPUs from a bare increment or lose evidence of
overflow. CPU ID, timing and buffer placement themselves must be validated.

## Retrieval is the gating problem

- **Existing kernel logging:** a small, carefully placed kernel log marker
  could be the first feasibility test if the kernel logging symbol, calling
  convention and context are verified. Host `idevicesyslog` can relay kernel
  messages ([tool documentation](https://github.com/libimobiledevice/libimobiledevice/blob/master/docs/idevicesyslog.1)),
  but it is unknown whether this device's early messages survive until the
  service connects. Printing 66 entries in a PMGR critical path is not a
  suitable assumed-safe recorder.
- **Owned kernel buffer and privileged readout:** avoids logging in the hot
  path, but requires a concrete buffer mapping and a narrowly scoped,
  authenticated retrieval mechanism or verified existing privileged access.
  We have not identified or tested one. A rootless/jailbreak or SSH path
  cannot be presumed available just because PongoOS booted.
- **Panic/reboot retrieval:** no persistent buffer, panic-log guarantee,
  serial route, or later Pongo readback has been established. Loss of records
  after a failed boot is a real limitation, not a negative test result.

A defensible first milestone is therefore **one synthetic, non-GPU boot
marker with a proved readout on the target build**, followed by a single
post-identity observation only after trampoline correctness is tested.
The full bridge trace comes later if the simple marker and retrieval work.

## Validation before device use

- Verify the exact loaded image/build and KPF compatibility; preserve a known
  normal iPadOS boot and the existing DFU/Pongo/Linux recovery path. The user
  reports the build, but actual kernel bytes and recovery from an instrumented
  iOS attempt have not been checked.
- Offline: enforce unique signatures and original bytes, confirm executable
  and writable storage, branch reach, all relocation and return addresses,
  register/flags preservation, record bounds and overflow behavior. Exercise
  missing, duplicate and changed signatures and known-negative cases; the
  current tests cover only a subset of these.
- On device: first test only an independently retrievable synthetic marker,
  then a small GPU record, and compare the trace with the expected order.
  A missing marker is inconclusive until transport and boot completion are
  independently confirmed. Keep raw data and build identifiers together.

No boot image, hook code, readout interface, or hardware experiment was made
in this review. Static site identification does not prove operational safety.
