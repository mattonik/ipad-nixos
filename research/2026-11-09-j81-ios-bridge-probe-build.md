# J81 iOS GFX bridge request capture: temporary build

2026-11-09. Host tests and device-module build only; no device result yet.
This follows the successful [working-iOS identity capture](2026-11-09-j81-ios1585-gpu-identity-capture.md).

## Method

For the first G4G clock request, the probe marks a bounded capture window,
executes the original provider call, then drains its buffer through the same
existing GPU log format used successfully by the identity probe. Separately,
a hook on the existing PMGR bridge-writer dispatch records selector, offset
and value before dispatch for selector 9 or 10 with requested state 15 while
the window is active. Recording uses a 96-entry `alloc_static` buffer,
atomic reservation and per-entry ready flags. It does not add a bridge, PMGR
or GPU MMIO read or write; the original writer calls remain in place.

After the provider returns, at most eight records are formatted per message;
66 records require nine log messages. `B0` means no buffer overflow was
observed, `B1` means overflow occurred, and `?` denotes a reserved record not
ready at drain time. The format is `B0 09:OFFSET=VALUE;...` with 8-digit
hexadecimal offset and value. If IRQs are disabled when the provider returns,
the probe skips logging. A missing event can also mean a declined patch,
logger loss, or an unreached path and is not proof of zero writes.

The scope is a global window rather than a thread- or device-bound trace:
concurrent unrelated selector 9/10 state-15 requests could be included.
Reservation order does not prove hardware completion order, and recording a
request before dispatch is not readback or proof of persistence. Formatting
and logging add time between the provider return and later GPC setup.
The clock wrapper saves and restores general-purpose and SIMD registers,
condition flags and floating-point state; it uses just over 1 KiB of stack
plus the logging call. The PMGR hook does not invoke the logger while in the
writer. IRQ-enabled status does not prove every lock or stack condition is
safe, and the temporary patched iOS boot can stall.

## Guards and tests

The patcher requires the known 19H394 kernel UUID and XNU version, one exact
AGX clock signature and one exact ApplePMGR writer signature, unchanged bytes,
and in-range branches. It only enables both hooks together. The stock KPF
still applies its usual patches in a temporary rootless palera1n boot.

The host KPF accepted the original image and declined either missing site,
either duplicated site, and a modified UUID. The original file hash remained
unchanged. A native arm64 harness with fake provider, writer and logger
checked 66 simulated entries, selector/state filtering, nine output batches,
original calls, return value and selected SIMD state; a two-thread test
checked all 66 records survived concurrent reservations. Additional variants
checked the 96-record overflow indicator and IRQ-masked logging skip. The
harness substitutes user-mode handling for privileged DAIF access and uses a
fake logger and buffer; it is not the on-device module. It does not prove
kernel stack headroom, live logging safety, or exact scheduling and timing.

Private module `artifacts/live/private/j81-ios-bridge-probe/checkra1n-kpf-pongo-j81-bridge`
has SHA-256
`dc7dbcb245dc474310ebb2a8f8b200989a5d747bf686c33cc448b1ce3312e59a`.
The same private directory contains source and native test variants. The
capture module has not been tested on the iPad at the time of this note.

Hardware follow-up: [the first capture](2026-11-09-j81-ios-gfx-bridge-capture-result.md)
returned a `B0` empty record window and iOS continued to firmware boot.
