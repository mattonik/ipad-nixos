# J81 iPadOS 15.8.5 log relay baseline

2026-11-09. A read-only device-service check reports ProductType `iPad5,3`,
ProductVersion `15.8.5`, BuildVersion `19H394`, confirming the model and
build previously reported by the user. This is a service-reported identity,
not a hash of the running kernelcache.

Installed Homebrew `libimobiledevice` 1.4.0_2 on the Mac. An eight-second
`idevicesyslog --no-colors -k` session produced 24 kernel-log lines (3,719
bytes) and no stderr. This proves that a live kernel-log relay worked at that
time. The bounded raw log is private at
`artifacts/live/private/gpu-offline/ios1585-ordinary-kernel-relay.log`.
It does not prove that messages emitted early in boot are retained until the
relay connects, that a custom marker reaches it, or that a patched iOS boot
will work. No instrumentation or GPU register access was performed.

The 19H394 archive kernel's symbol table names `_IOLog` at unslid
`0xfffffff0076d66d4`, `_printf` at `0xfffffff007182994`, and `_kprintf` at
`0xfffffff00778a568`. Symbol presence is not proof that a call is safe at a
candidate hook site. In the public
[XNU 8020.140.41 IOLog source](https://github.com/apple-oss-distributions/xnu/blob/xnu-8020.140.41/iokit/Kernel/IOLib.cpp),
`IOLog` routes through `os_log_with_args` and asserts about interrupts being
disabled (subject to specific exceptional conditions). This is a related
public XNU version, not the exact running kernel source; it is evidence that
context must be checked, not proof of identical behavior in 19H394. In
particular, the PMGR bridge writer can run while interrupts are disabled and
spin locks are held, so do not call `IOLog` from that path. Logging can also
change timing and cannot be assumed safe in the GPU path without proving its
execution context.

Next: establish whether an existing early-boot kernel message can be obtained
through the relay or a log archive, then design an isolated marker hook in a
verified non-critical context. Test the trampoline, preservation and branch
relocation on the host before attempting a temporary iOS boot. A successful
live relay alone is not sufficient to run a boot patch.

Follow-up: the [early-boot archive capture](2026-11-09-j81-ios1585-early-boot-log-archive.md)
retrieved ordinary iOS GPU probe and firmware-start messages after boot.
