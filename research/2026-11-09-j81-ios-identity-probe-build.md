# J81 iOS 15.8.5: GPU identity capture build

2026-11-09. Host build only; this identity probe has **not** been run on the
iPad. The earlier [J1 marker](2026-11-09-j81-ios1585-boot-marker-result.md)
proved that a different, much smaller inline patch and its log argument could
survive a temporary rootless iOS boot. It did not prove this new trampoline.

## Intended observation

The existing G4G identity function reads 32-bit RGX `+0x20` into `w9`, then
`+0x18` into `w8`. The candidate patches the following instruction at
`0xfffffff00669bb60`, *after both reads*, with a branch to a trampoline. It
formats the already loaded words as `I20=xxxxxxxx I18=xxxxxxxx`, then calls
the driver's existing log thunk with the same `%s` format string whose
argument was successfully retrieved in the J1 test. The trampoline executes
the displaced `and w10,w9,#0xff0000` and returns to `...bb64`. It does not
perform an additional GPU or PMGR MMIO read or write.

The record would show values read in a working iOS probe; it would not explain
why Linux's read stalled or reveal PMGR bridge writes. Because the hook is
after both loads, no event is produced if either existing read does not
return. The synthetic record reuses an existing startup-log format; its
`I20=` / `I18=` argument distinguishes it from the real startup message.

## Preservation and safety boundaries

The trampoline reserves `0x340` bytes of stack, saves x0–x30, q0–q31, NZCV,
FPCR and FPSR, and restores them before the displaced instruction and branch
back. It checks the ARM IRQ mask and skips the added log call when IRQs are
disabled. The public related XNU 8020.140.41 sources check this same IRQ bit
in [ml_get_interrupts_enabled](https://github.com/apple-oss-distributions/xnu/blob/xnu-8020.140.41/osfmk/arm64/machine_routines.c)
and flag IOLog with interrupts disabled in
[IOLib.cpp](https://github.com/apple-oss-distributions/xnu/blob/xnu-8020.140.41/iokit/Kernel/IOLib.cpp).
Those sources are not the exact installed kernel. Interrupts enabled alone
does not prove the log call is safe with all locks, stack constraints or
probe lifecycle state. An IRQ-masked run deliberately emits no identity
record; absence is inconclusive.

The kernel patchfinder checks the same kernel UUID and XNU version as the
successful marker, exactly one five-instruction match in the AGXG4G text,
unchanged bytes at patch time, and both ARM64 branch displacements. It uses
the reference KPF's shellcode-area allocator and applies the runtime patch
only when built with `J81_IDENTITY_DEVICE_BUILD`. The matcher checks the
identity site but does not verify every outside code or data dependency.
A failure skips the custom identity hook, while stock KPF behavior remains.

## Host validation

- The exact 19H394 image produced one match and applied the patch to the
  host harness's private mapping. Missing and duplicate signatures and a
  modified UUID each produced `applied=0`; the source image hash was unchanged.
- A native arm64 harness, using a fake logger, checked formatting against
  `I20=12345678 I18=9abcdef0`, restored x8/x9, selected SIMD registers and
  NZCV, and executed the displaced instruction with its expected result.
  A second variant simulated IRQ masked and verified that it skipped logging
  while preserving those same observed values. The harness substitutes a
  user-mode test for the privileged DAIF read, resolves the logger differently
  and returns in place of the patched branch; it is not the device binary.
- The reference PongoOS KPF built an ARM64 Mach-O device module with explicit
  `J81_IDENTITY_DEVICE_BUILD`. It has not been independently loaded or
  executed and has not been reviewed for every possible ABI/locking edge.

Private files under `artifacts/live/private/j81-ios-identity-probe/`:

- `checkra1n-kpf-pongo-j81-identity`, SHA-256
  `f8f53f4163c6c778865e9f9fe840710ae4095721fbe2c89c24dde10cee337c9e`.
- `j81_identity_capture.c`, SHA-256
  `5ff7c5924d323d7ae032bfe092e6911413cf126a8c30d7b233d6281fa3f1d4cc`.
- `j81_identity_shell.S`, SHA-256
  `b331bdf99e7658baa488b277064c00a22c91e70b0ac49af17b7b6c7d90798e0f`.
- Native host-test and IRQ-skip variants; these intentionally differ from the
  privileged on-device shellcode at the DAIF, logger-resolution and return sites.

Next: independently review the trampoline, indirect logger's lock context,
stack use, patchfinder cache handoff and boot/readout procedure before using
this module on hardware. The existing normal iOS log and J1 marker are useful
controls, but a missing identity event remains inconclusive.
