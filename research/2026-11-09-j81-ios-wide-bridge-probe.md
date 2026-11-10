# J81 iOS: wider bridge capture and cached-state decision

2026-11-09. Offline work and host tests only; this wider module has not run
on the iPad. It follows the [empty first capture](2026-11-09-j81-ios-gfx-bridge-capture-result.md).

## The provider decision

The decoded 19H394-equivalent ApplePMGR code at
`0xfffffff006bd7bb4`–`...7bd8` computes a per-instance device-state byte at
PMGR object `+0x19554 + instance*0x260 + device_id`, loads it into `w24`,
and compares it with requested state in `w22`. An equal comparison branches
around the state-change path; otherwise it stores the new state and builds
the transition/dependency work. Earlier instructions and record-flag checks
can return before this comparison. In the expected enable case the requested
state is 15, but no actual state from the empty hardware capture is known.

## Wider proposal

The temporary KPF module installs three guarded hooks together:

1. The PMGR bridge-writer hook records requests for selectors 9 or 10 and
   state argument 15 **from early XNU driver execution**, before the G4G
   clock request starts. It cannot observe earlier iBoot, PongoOS or BootROM
   writes, and it does not trace every PMGR register or other selectors.
2. During the first G4G clock request, a hook at the cached-state comparison
   records GFX device ID `0x7c`'s cached and requested states. It then
   performs the original compare so its flags and subsequent branch retain
   their semantics. The original cached byte load is unchanged.
3. On return from that provider, the clock hook stops recording and drains
   the buffer with the same existing GPU log format used in earlier tests.
   It does not call the logger inside the PMGR writer or decision hooks.

Each emitted message begins `B0 D1:xxxxxxxx>yyyyyyyy` if the comparison was
observed, showing cached state then requested state in hexadecimal. `D0`
means no matching comparison was recorded and must not be interpreted as
state zero. Subsequent tokens such as `09:00000100=00009000;` record the
selector, offset and value passed to the existing writer dispatch. `B1`
indicates overflow; `?` means a record was reserved but not ready at drain
time. The 96-entry limit makes overflow explicit. The probe buffers all
matching early selector/state requests in a global window, so concurrent or
unrelated users of those selectors may be included. Reservation order is not
proof of hardware completion order; these are requests, not MMIO readback.

The probe uses a static allocation established by PongoOS and uses atomic
reservation/ready flags. Its buffering hooks add ordinary memory accesses,
not new GPU or PMGR MMIO accesses. The drain checks IRQ state before calling
the logger; no event if IRQs are masked is inconclusive. It adds logging and
uses roughly 1 KiB of clock-wrapper stack plus the logger's own stack.
A successful host test does not prove the allocation's mapping, lock context,
stack headroom or timing behavior in this boot. A crash may lose the log.

## Host tests and artifact

The host KPF harness accepted the expected kernel and declined separately
missing or duplicated clock, writer and decision signatures and a wrong
kernel UUID. The original file was unchanged. A native arm64 harness with
fake provider/writer/logger exercised one pre-request record, the observed
GFX decision, original compare flags, 66 further records and selected state
preservation. Other variants exercised concurrent record reservations,
96-entry overflow and IRQ-masked skip. The user-mode harness substitutes a
fake DAIF result, buffer and logger and a return for the on-device branch;
it is not a running iOS test. A warning in the initial device build was
corrected and the final build completed without compiler warnings.

Private module:
`artifacts/live/private/j81-ios-wide-probe/checkra1n-kpf-pongo-j81-wide`
SHA-256 `395d32ff92b017434909eb020e6919c28ff5c227770dfc0cb50a55ffed239f20`.
The source, assembly and host harnesses are in the same private directory.
The module is built for a temporary rootless palera1n boot of the known
19H394 kernel; it is not yet tested on hardware. It also includes the stock
KPF changes and can require a DFU recovery if it stalls. No new iPad access
or DFU cycle was performed in this offline round.

Hardware follow-up: [the wide capture result](2026-11-09-j81-ios-wide-bridge-result.md)
observed cached state 0, requested state 15, and no matching bridge records.
