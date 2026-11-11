# J81 iOS tuner probe: later startup snapshot

This experimental 19H394 probe extends the [hardware-run tuner probe](../j81-tuner/README.md).
It keeps its `P`, `G`, `I`, and early `U` records and adds a second `V` record
at the existing GPU firmware-success logger call. `V` has the same four hex
fields as `U`: window flags, bounded atomic-update failure, global entry-seen,
and global exit-seen. The GFX window still closes at identity; the global
seen flags continue recording until the later snapshot. They are not reset.

The original firmware log call executes first, with its existing stack and
arguments. The trampoline then saves CPU state, logs `V` when interrupts are
not masked, restores state, restores the original call-site return address,
and resumes after the displaced call. The new logging can perturb timing; the
original logger can also observe a different return address while it executes.
No additional GPU, MCC, or PMGR MMIO is performed.

A nonzero seen field in `V` following zero in `U` would show that the
corresponding tuner hook ran sometime after the earlier snapshot and before
the later one. It does not identify the caller, prove causation or establish
that the handler ran before the GPU identity read. Flag publication races,
missing markers, masked interrupts and later activity remain limitations.
Two zero snapshots do not prove the policy never ran. The later point occurs
around 114 ms after identity in one previous boot, before the Home screen;
it cannot observe a later user-triggered brightness change.

## Build and checks

Component `j81_tunerlate_capture`, flag `KPF_CFLAGS=-DJ81_TUNERLATE_DEVICE_BUILD`.
The host KPF harness accepted the exact 19H394 image (12 unique signatures,
854 shellcode words), rejected each individually missing and duplicated
signature and a wrong UUID, and checks branch reachability. The native ARM64
host test verifies the original logger's two stack arguments and return value,
the `U`/`V` outputs, tuner thread categories and host/device hook-body parity:

```sh
python3 research/probes/j81-tuner-late/test_tuner.py
```

Device module `artifacts/live/private/j81-ios-tunerlate-probe/tuner-late4`,
SHA-256 `7843b689fa48a3f9f19023ea7751166caee08457513ceffca18de56579c019ab`.
The module is private and is not included in Git. Full logs contain private
information and remain local. The probe has not been independently reviewed
or run on hardware. Mocked tests do not establish kernel stack headroom,
real interrupt/concurrency behavior or the impact of the changed call path;
it may hang or reboot iPadOS and lose the capture.
