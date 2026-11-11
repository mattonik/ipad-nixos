# J81 GPC timing probe: offline prerequisites

This directory contains an offline signature checker, not a device probe.
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

Next: implement the start and finish trampolines, exact-build and branch-range
guards, bounded per-invocation storage and export, then host-test preservation,
reentrancy, skip paths, missing markers and failed signatures before building a
KPF module. No new device MMIO is proposed. A future kernel hook can still
hang or reboot the device, and logs can be lost before the identity export.
