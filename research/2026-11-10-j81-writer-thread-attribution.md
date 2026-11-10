# J81 writer attribution: offline findings and probe

> Hardware result: the 27 additional calls were on different threads from
> the GFX provider, while selectors 9 and 10 matched it; see the
> [capture result](2026-11-10-j81-writer-thread-result.md).

2026-11-10. Prepared after the [93-call capture](2026-11-10-j81-ios-allwriters-result.md).
No additional hardware test was performed in this round.

## What can already be inferred

The captured Pongo PMGR `devices` records assign bridge selector 7 to DISP0
(device 28), 11 to USB (device 6), and 6 to ISP (device 24). The GFX record
contains selectors 9 and 10 and no parent IDs. Together these facts make
concurrent display, USB or ISP setup plausible sources of the extra 27 calls;
they do not prove the runtime caller or exclude another path issuing the
same selector. Shared hardware dependencies are also not excluded.

The saved Linux display inventory contains simple framebuffer / DRM fbdev,
not the Apple `disp0` clock consumer. Its generic PS86 node does not show
the live PMGR word or recreate Apple's display policy. A historical raw
sample is not from test4. See [Linux display observation boundaries](2026-11-07-j81-disp0-linux-gate-observation.md).
The test4 logs have no explicit checkpoints for the three extra selector
ranges, but another Linux or bootloader component could configure them.
The current boot is iPadOS, so no new Linux readback was performed.

## Follow-up probe

The new module retains the 128-entry all-selector probe and labels each
record `PpTt:ssssssss/iiiiiiii:oooooooo=vvvvvvvv;`. `P` has the same
before-provider/window meaning as before. `T1` means the existing XNU
`TPIDR_EL1` value matched the nonzero value sampled by the GFX provider
wrapper; `T0` means it did not match, or no nonzero provider context was
available. Apple XNU's [ARM64 startup code](https://github.com/apple-oss-distributions/xnu/blob/main/osfmk/arm64/start.s)
identifies `TPIDR_EL1` as the thread register. This is a comparison only:
no thread pointer is emitted to the log. It is not a call-stack trace.

If selectors 7/11/6 are `P1T0`, that supports concurrent other-thread work;
it cannot rule out an asynchronously scheduled dependency. If `P1T1`,
they share the provider's thread context but could still arise from an
interrupt or nested unrelated call. Follow the actual call path before
attributing causation. Phase sampling and buffer-reservation races, global
scope, log loss, `B1` overflow, and the pre-dispatch rather than completed
write boundary still apply. `P0` thread labels are not useful because the
provider context may not yet be captured. Do not replay the other tables
solely on this evidence.

Module: `artifacts/live/private/j81-ios-thread-probe/checkra1n-kpf-pongo-j81-thread`

SHA-256: `82c6fd2587c0861bb9d87ce8bc6546622795136da960d81f9ef9271702fa4cb3`.
The exact 19H394 kernel passed the host KPF harness. Each missing or
duplicated one of six patch signatures and a wrong UUID was declined.
Native ARM64 simulations tested equal, different and zero thread identities,
pre-window capture, all-selector records, batching and 128-entry overflow.
These simulate privileged register reads and do not prove device timing,
logging reliability or safety. The binary, source, registration and host
test inputs are kept together in the private artifact directory.

When ready for another fresh DFU, run:

```sh
cd /path/to/ipad-nixos
printf '%s  %s\n' 82c6fd2587c0861bb9d87ce8bc6546622795136da960d81f9ef9271702fa4cb3 artifacts/live/private/j81-ios-thread-probe/checkra1n-kpf-pongo-j81-thread | shasum -a 256 -c - && sudo boot/vendor/palera1n-macos-arm64 --rootless --override-kpf artifacts/live/private/j81-ios-thread-probe/checkra1n-kpf-pongo-j81-thread --debug-logging
```

If palera1n remains at “Booting PongoOS” while the logo is visible, stop it
and rerun as before. After iPadOS boots, unlock and collect logs privately.
The probe can stall or reboot the device and may need a DFU recovery. Full
device archives can contain private information.
