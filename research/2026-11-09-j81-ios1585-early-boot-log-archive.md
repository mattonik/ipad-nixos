# J81 iPadOS 15.8.5: early GPU messages in device log archive

2026-11-09. Read-only capture from the connected iPad, whose device service
reported `iPad5,3`, 15.8.5, 19H394. No reboot, patch, hook, or GPU MMIO was
performed. `idevicesyslog archive` retrieved an approximately 142 MiB tar
using a requested start time 24 hours earlier; the request is a filter, not a
proof of complete coverage. The archive was unpacked into a private
mode-0700 directory and decoded on the Mac with `log show`, restricted to
process `kernel` for analysis. The unfiltered archive can include personal
system information and must remain private.

## Results

The decoded kernel log starts with an iBoot-version message at 19:47:39 local
time and contains several successive iBoot/startup sequences on November 9.
For the first such sequence, the AGXG4G messages include:

- 19:47:41.892: GPU driver starting.
- 19:47:42.006: GPU probe detects `G4G A1`, 1 MGPU, 8 cores, 2 fragments,
  and one each of GTP, FRG and CDM slots; the driver selects the G4G A0
  accelerator with score 10000.
- 19:47:42.006: accelerator starts on `J81AP`.
- 19:47:42.116: GPU firmware reports `META FW started`, and AGX reports
  firmware boot success with `AGXFirmwareKextG4G`.

The same probe detection appears in four startup sequences in this archive.
This is real evidence of a working iOS GPU identification and firmware start
on the connected device, distinct from Linux's non-returning first identity
access. These are driver-reported messages, not raw identity values or a
trace of the PMGR or MMIO operations. Firmware boot success alone does not
establish that any particular rendering workload was tested.

The archive was acquired after these events, so early driver messages survived
for later host retrieval on this ordinary iOS boot. This makes the archive a
credible candidate for a marker readout. It does not prove that an injected
`IOLog` will be accepted, retained or recoverable after a patched boot, nor
that logs survive a panic. We do not know whether a time-filtered archive is
complete, and do not infer missing events from the absence of a message.

## Next step

Prepare a minimal host-tested synthetic marker at a proven safe context,
then use a temporary boot-only patch to test whether that marker survives to
an archive. The already recovered unmodified AGX startup message can serve as
a positive retrieval control. Confirm exact loaded image and hook ABI/context,
including the IOLog interrupt restriction discussed in the
[relay baseline](2026-11-09-j81-ios1585-log-relay-baseline.md), before any
instrumented boot. No logging call is justified inside the PMGR critical path.

Private artifacts under `artifacts/live/private/ios-logarchive-19h394/`:
`capture.tar`, extracted `boot.logarchive`, filtered `kernel.log`, and
`log-show.stderr`. They are not included in Git.
