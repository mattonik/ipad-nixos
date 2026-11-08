# J81 GPU research status

**Status: bring-up in progress; no GPU acceleration is available.** The target
is the iPad Air 2 (J81, A8X/T7001), whose GPU is identified by this project as
Imagination GXA6850 (Rogue/G4G generation).

## What has been observed

- A guarded PMGR power cycle completed, and the PMGR state subsequently read
  as `0x3ff` (state 15).
- A staged sequence of 66 bridge-table store operations reached its software
  checkpoints. Two bridge words were read back:
  `0x201f00018 = 0x80010004` and `0x201f0001c = 0x00010001`. The first address
  overlaps one table target; the second is outside the table's 66 targets.
- GPC initialization reported state 1. The first direct RGX core-ID read did
  not complete. Its cause is unknown; the read does not establish whether the
  GPU is ready or whether the address is correct.
- A separately guarded, watchdog-supervised MCC read completed on a later
  Linux RAM boot: `0x200000830 = 0x00000000`. This raw value matches none of
  the conditional iOS 8.1 low-five-bit/bit-8 write patterns for selectors 0,
  3, or 4;
  it does not establish MCC initialization, hardware mode, or prior iOS
  callback history. See the [MCC read result](2026-11-08-j81-mcc-read-result.md).
- GPU firmware execution, job submission, and rendering have not been
  demonstrated.

These are observations from specific J81 test boots, not a general device
support claim. Checkpoints after stores show software progress, not register
readback. Thus 65 table targets remain unverified by readback.

## Evidence and reproduction

The tracked [test4 capture analysis](2026-11-07-j81-test4-raw-readback-boundary.md)
explains the distinction between checkpoints and target readback. The
[core-hang analysis](2026-11-06-j81-gpu-core-hang-analysis.md) records the
unknown cause and the stop boundary. The capture helpers are in
[`boot/`](../boot/) and the small host-side test suite can be run with
`python3 tools/check_offline.py`.

Raw live-device captures are not included in this repository, so the numeric
observations above cannot be independently reproduced from a clean checkout
alone. No private Apple firmware, extracted firmware payload, serial number,
or device-specific credential is published here. Hardware experiments can
hang the device or terminate USB networking; do not treat this page as a
procedure to repeat the stalled RGX read.

## What related work establishes

- [Public ecosystem update](2026-11-07-public-gpu-ecosystem-update.md):
  Orchard's experimental J81/J82 device data, Project Cascadia's older A5 SGX
  implementation, and Mesa's public PowerVR status. None provides a working
  A8X GXA6850 driver.
- [Cascadia methods comparison](2026-11-07-cascadia-gpu-methods-for-j81.md):
  readiness tracing and Apple/Linux comparison methods that may inform
  investigation; SGX addresses, firmware, and command formats do not transfer
  to A8X.
- [A11 GPU-WIP comparison](2026-11-08-a11-gpu-wip-comparison.md): static
  A11/AGX research and its limits; A11 addresses and firmware do not apply to
  J81.

## Remaining boundary

The iOS 15 G4G probe was traced up to the identity read. Its only pre-ID
clock/power calls are one provider clock enable and one power enable, the same
as iOS 8.1 ([pre-ID clock/power trace](2026-11-08-j81-ios15-g4g-pre-id-clock-power.md)).
The next offline target is the iOS 15 PMGR clock callback behind that
enable. The PMGR busy-edge codes `0x2700c001/2` turned out to be kdebug
trace points with no hardware effect
([trace-code note](2026-11-08-j81-pmgr-2700c00x-are-trace-codes.md)).
On iOS 15 the GFX clock gate goes to ApplePMGR's generic state path and its
state helper. On J81 the AppleT7000 bridge-selector handler does not bind
([clock gate to PMGR state](2026-11-08-j81-ios15-clock-gate-to-pmgr-state.md)).
GFX has no parent power domains, no related-device step, and iOS 15 writes its bridge selectors 9
and 10 right after PMGR state 15 is reached, the same order test4 used
([dependencies and bridge apply](2026-11-08-j81-ios15-gfx-dependencies-and-bridge-apply.md)).


The next work is to understand the A8X-specific power, reset, wake, and
ownership sequence before any further core access. Similarities to A5 SGX or
A10/A11 AGX are research leads only. There is no verified A8X initialization
recipe or rendering path yet.
