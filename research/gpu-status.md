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
The iOS 15 PMGR callback is now traced through the generic per-device state
compare and state-transition helper; the dependency builder also maintains
per-device counts. The PMGR busy-edge codes `0x2700c001/2` turned out to be
kdebug trace points with no hardware effect
([trace-code note](2026-11-08-j81-pmgr-2700c00x-are-trace-codes.md)).
On iOS 15 the GFX clock gate goes to ApplePMGR's generic state path and its
state helper. The separate AppleT7000 special-action handler does not bind on
J81, but this does not exclude other bridge paths
([clock gate to PMGR state](2026-11-08-j81-ios15-clock-gate-to-pmgr-state.md)).
GFX's captured dependency record has no parent IDs or related-device object;
selectors 9 and 10 are written after state 15 on the traced transition, the
same order test4 used
([dependencies and bridge apply](2026-11-08-j81-ios15-gfx-dependencies-and-bridge-apply.md)).
The effective Linux FDT on the inspected boot has no bridge-settings,
bridge-reg-index, or state-config properties, so it cannot answer what those
properties held in Apple's ADT or whether iOS PMGR populated `bcc56c` records
for GFX ([Linux FDT property check](2026-11-08-j81-linux-fdt-pmgr-properties.md)).
The later [`bcc56c` analysis](2026-11-08-j81-ios15-bcc56c-timing-accounting.md)
resolved its optional selector-1 action to PMGR counter reads. The alternate
pointer's mapping and whether a GFX record invokes the action remain unknown.
GFX is in an iOS 15 SoC-tuner set linked to MCC and display policy; its
runtime activation and effect on GPU reachability have not been established
([SoC-tuner note](2026-11-08-j81-ios15-soc-tuner-device-sets.md)).

Test4's planned bridge stores match the conditional format-0 Apple writer,
and its GPC operations match the inspected pre-ID sequence. Its software
checkpoints are not readback of all entries. Apple waits 10 µs after the GPC
poll; the identity-read transcript does not timestamp the actual test4
interval. Linux and XNU mapping attributes have not been compared directly
([test4 comparison](2026-11-08-j81-test4-vs-apple-pre-id-sequence.md)).

Both 8.1 and 15.8.8 LLB images contain GFX perf-control writes. A helper
hid the 15.8.8 writes from the original address scan; they can produce values
matching the later Linux capture. That is static evidence, not proof of the
last writer or of which instructions ran in the Linux boot. The selected
GPU performance state remains unknown ([bootloader analysis](2026-11-09-j81-iboot-15.8.8-first-scan.md),
[helper inventory](2026-11-09-j81-llb-indirect-pmgr-helper.md)).

The next work is to understand the A8X-specific power, reset, wake, and
ownership sequence before any further core access. Similarities to A5 SGX or
A10/A11 AGX are research leads only. There is no verified A8X initialization
recipe or rendering path yet.
