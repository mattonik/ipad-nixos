# J81 GPC timing probe: offline prerequisites

This directory contains the probe source, host checks and an offline signature checker.
On the local decoded iPadOS 15.8.5 19H394 kernel it locates the unique six-word
GPC sequence containing the proposed request-store and post-poll hook sites.
It also finds a 64-byte signature beginning at `mach_absolute_time`; its first
48 bytes alone occur twice in the image, so a short byte-pattern match is not
sufficient to select that function. The extra 16 bytes cover the start of the
following code and must be validated on the exact image. The checker does not
verify a Mach-O UUID, virtual address, branch reachability or hook safety.

The named `mach_absolute_time` implementation on this image reads a per-CPU
offset via `TPIDR_EL1`, executes `isb; mrs CNTVCT_EL0`, rereads the offset,
retries if it changed, and returns their sum. A bare `CNTVCT_EL0` delta omits
this adjustment. The saved Pongo ADT contains a 24 MHz timebase-frequency;
this is not a measurement of the current iPadOS timer configuration. The
kernel routine uses `x0`, `x8`–`x11` and condition flags; a trampoline making
this call must preserve the interrupted state, including LR, and validate
stack and execution context. A same-thread start/finish marker still needs
reentrancy protection and explicit skipped-path handling. The routine's retry
loop and injected calls affect timing; its presence is not proof that calls
are safe from the candidate sites.

Run offline checks from the repository root:

```sh
python3 research/probes/j81-gpc-timing/test_verify_sites.py
python3 research/probes/j81-gpc-timing/verify_sites.py /path/to/decoded-kernel
```


## Built candidate

The experimental KPF module is now built at
`artifacts/live/private/j81-ios-gpc-timing-probe/gpc-timing`, SHA-256
`bb36d637c7659215e747ed734c78587dc55a0a4154d708bcc8bc26297549c9c5`.
It is intended only for the exact iPadOS 15.8.5 19H394 kernel checked by the
component. It extends the previously run poll-comparison probe, retaining
its provider, PMGR and identity capture, but replaces the per-iteration GPC
poll hook with request-store and post-poll trampolines. It adds two calls to
the original `mach_absolute_time` and no new MMIO. Other inherited provider
hooks still affect execution and log output.

At the existing identity log, `P1=... T1=xxxxxxxx I=...` means the provider
PMGR sample was captured, a valid timing interval was recorded and the
original identity read completed. `T1` is a 32-bit hexadecimal delta of the
values returned by `mach_absolute_time`, not nanoseconds; `T0` is missing,
invalid, reentered, mismatched-thread or overflow, not a zero latency. The
first timestamp precedes the displaced GPC request store; the second follows
the original poll's successful exit. The interval includes injected code,
possible interrupts and any scheduling, and is not a measurement of the
exact physical transition. Do not infer a 24 MHz conversion without confirming
the running iPadOS timebase. `T1` does not report a GPC register value or
page-5 bit. The trampoline uses one guarded global record; repeated same-thread
entries invalidate it. Missing export remains inconclusive.

The host KPF harness accepted the exact kernel and rejected individually
missing and duplicated versions of the nine instruction signatures, a wrong
UUID, and a modified timer function. The ARM64 native hook simulation checks
the original request store, result and skip paths, wrong thread, nested start,
reentry during the timer, and NZCV restoration. Signature tests check missing,
duplicate and unaligned matches. Host tests simulate thread/timer state: they
do not establish live kernel execution context, stack headroom, real interrupt
or scheduler behavior, timer safety at this call site, capture availability
after a crash, or precise timing. No device run has yet been performed.

Use the established temporary rootless Pongo boot flow with this module;
verify its SHA-256 immediately before boot. Retrieve the startup archive after
iPadOS reconnects and is unlocked. Full logs stay private. The experimental
hook could hang or reboot iPadOS; recovery by reset is not guaranteed.
