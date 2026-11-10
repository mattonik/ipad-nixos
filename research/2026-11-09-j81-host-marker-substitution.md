# J81 iOS boot marker: host-only string-substitution experiment

2026-11-09. The ordinary 19H394 iOS log archive contains the existing AGX
startup message. A minimal marker experiment can reuse that existing logging
call instead of adding a new one: replace the static format string
`AGXk: Starting GPU driver. Available features: %s\n` with
`AGXk: J81MARK1 GPU driver. Available features: %s\n`. Both strings,
including their terminator, have the same length; `%s` and the newline are
preserved. This changes message text, not code, the call's arguments or GPU
registers. It still mutates kernel memory before boot and is not proven safe.

## Host-only prototype

In a temporary copy of the palera1n PongoOS reference checkout, an added KPF
component uses `xnu_pf_get_kext_header` for `com.apple.AGXG4G` and locates
`__TEXT,__cstring`. The unmodified 19H394 image has one exact format-string
match within that section. The prototype substitutes the marker **only under
`KPF_TEST`**, in the host harness's private mapping. The device build path
contains no substitution. The component's fallback to the kernel string
range is for host discovery only; do not treat it as approved device behavior.

| Host input | String matches | Substitution |
| --- | ---: | --- |
| Original decoded 19H394 image | 1 | Applied in private mapping; replacement and format verified |
| Copy with one original-string byte changed | 0 | Declined |
| Copy containing a duplicate in that section | 2 | Declined |

All three harness runs exited 0, because a declined custom marker is not a
stock KPF failure. The original decoded image SHA-256 was unchanged. The test
checks matching and in-memory substitution, not iOS execution, result
retrieval, KPF module compatibility or a device-safe failure policy. The
stock host KPF also modifies its private mapping. The duplicate test's extra
string was inserted into an unrelated region of the section in a disposable
copy; it is only a guard test, not a bootable image.

## Important readout caveat

The iPad's captured `.logarchive` includes the **original** GPU startup format
string in its `dsc/` decoded-string data. It is therefore possible that log
rendering resolves a format using archived or on-disk metadata instead of the
modified preboot memory string. We have not traced or tested that resolution.
An unmodified displayed message after a patched boot would not by itself prove
the patch failed. A device experiment needs an independent KPF-side receipt
and a separate positive control; if static string lookup masks the substitution,
a different marker/readout design is needed. Do not infer failure from a
missing marker without that control.

Before any iPad attempt, verify the exact loaded image and runtime KPF module,
strictly scope the matcher to the expected kext section and build, specify
safe no-match behavior, and independently review the mutation and recovery
path. This is not yet a bootable module or an instruction trampoline, and
collects no GPU values. The iPad was not rebooted for this experiment.

Private host source: `artifacts/live/private/j81-boot-marker/j81_marker_probe.c`,
SHA-256 `eaecd32f9ca9c6447428621ee02cdeb1d0a9c8a0b03b4f82b0e522b049f90979`.
Host binary SHA-256
`62d0c1d7ca5e0353d6c94a6b5af620d33be145de8ef6cbe3eff34d5be772789e`.
The modified temporary reference checkout is not a device artifact.
