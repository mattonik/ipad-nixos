# J81 Linux GPC-to-page-5 timed observation

Prepared offline; the first hardware attempt failed before sampling. See the follow-up below. The motivating Linux capture read
page 5 about 51 seconds after its GPC poll based on host and filesystem wall
clock evidence. This probe narrows that interval using the existing pinned
one-shot page-5 kernel module on a fresh cycle-payload RAM boot.

The campaign verifies the existing cycle/bridge bundle, creates a new log
directory, checks the J81 RAM-boot preflight, records its boot ID, and runs
the existing supervised PMGR cycle and 66 bridge stores. It stages pinned
copies of the new static binary, wrapper, supervisor and previously tested
page-5 module. The wrapper checks the same boot ID, J81 identity, exact kernel
and cycle-module notes, runtime PM lease, RAM root, module/binary hashes, and
one-shot state. Under the watchdog it loads the existing page-5 module with
fixed offset 4 and starts the binary.

The host separately acknowledges the PMGR and initial GPC state reads. After
the host acknowledges **one combined GPC-and-page5 batch**, the binary writes
the three known GPC setup values, polls until bit 4 clears and state equals 1,
then reads the pre-opened page-5 sysfs attribute once without waiting for
another host acknowledgment. It emits checkpoints before the writes, poll,
and page-5 syscall; the watchdog remains armed if any step stalls or the host
fails to acknowledge a completed stage. The sysfs module maps and reads page
5 inside that syscall, so the sample is not a direct CPU load immediately
after the poll. `poll-to-sysfs-return-ns` is a measured upper bound from a
monotonic timestamp taken after the poll to the sysfs read's return; it also
includes checkpoint output and sysfs/map overhead. It does not measure the
exact MMIO-to-MMIO interval. There is no delayed follow-up sample, GPU-core
read, or page-5 write in this campaign.

Current local bundle: `artifacts/live/private/j81-gpc-page5-timed-bundle-v2/`.
The fixed module is the previously used `ca16576e…06099e4c`; the campaign
pins full hashes and the exact boot ID. The ARM64 probe and supervisor were
built statically using the project's Nix cross toolchain and were verified as
AArch64 static ELF. The new flake output is `gpu-gpc-page5-timed-static`.

Host checks mock MMIO and sysfs: three GPC writes in order, poll success,
busy-limit and bad-state failure, one page-5 read and invalid response;
supervisor real child pipes with a fake watchdog, host-ACK/feed and stall
handling; strict host capture ordering including missing-poll and lost-host
cases; and campaign sequencing, boot-ID passing and checksum rejection. An
ARM64 builder executed the binary only with an invalid argument, which it
rejected before any device access. Shell syntax, Nix parse and checksum
verification also passed. The corrected version later ran on hardware as described below; these host tests alone do not prove hardware timing or safety.

After a **fresh** correct cycle-payload boot and prior to any GPC test, run
from the repository root with a new capture directory, for example:

```sh
python3 boot/j81_gpc_page5_campaign.py artifacts/live/gpu/gpc-page5-timed-NEW
```

The existing Pongo/DFU boot procedure and physical confirmation remain
necessary. The test performs GPC writes and an undocumented page-5 read, so
it can hang or reset the device. No missing result may be interpreted as zero;
stop and do not retry on the same boot. A positive or negative single sample
still does not prove the meaning of bit 30 or why the GPU core stalls.

## First hardware attempt and corrected bundle

On 2026-11-10, boot `44bea979-dc90-47b6-8d67-78edf6976ebe` passed the
campaign preflight, supervised PMGR cycle and bridge stages. The timed stage
recorded PMGR `0x3ff`, initial GPC state `0`, host authorization for the
combined sequence, `checkpoint=before-gpc-writes`, and
`checkpoint=before-gpc-poll`, followed by `stage=finished rc=1`. It did not
emit `checkpoint=before-page5-read`, a page-5 value, or watchdog disarm.
The host stopped on the failure. USB networking later stopped responding;
this does not independently identify the device's reset outcome.

The first version used 1,000 back-to-back GPC polls and failed to log the last
poll value or a clock failure. A poll limit reached too quickly is a plausible
cause, not an established diagnosis; failure of the immediate monotonic-clock
call is another possible path. No page-5 sample was obtained, and this result
must not be interpreted as `0`. Raw capture:
`artifacts/live/gpu/gpc-page5-timed-20261110-01/`.

Version 2 uses the existing timed-GPC probe's 10 µs sleep between busy polls,
still capped at 1,000, and logs the raw final poll and count on failure. Its
source test exercises busy delays, eventual completion, timeout and invalid
state. Host capture still fails closed on a failure checkpoint. The updated
bundle is `artifacts/live/private/j81-gpc-page5-timed-bundle-v2/`, with binary
SHA-256 `7ed55c603bf6c20298e18621e1defbb199cca2cef541819c8a092009a05ea6b5`;
the campaign now pins that version. Its hardware result is recorded below.
The previous bundle and capture are preserved for diagnosis. A new run needs a
fresh DFU and cycle-payload boot; never retry on the failed boot.

## Corrected hardware result

On 2026-11-10 fresh RAM boot `78b52d0a-678c-4c08-9922-e48ff20ed5ac`
passed the preflight, supervised PMGR cycle and 66 bridge steps, and ran
the version-2 timed probe. The timed capture recorded:

```text
stage=after-pmgr-read raw=0x000003ff target=15 actual=15 auto=0 reset=0
stage=after-gpc-state raw=0x00000000
checkpoint=before-gpc-writes
checkpoint=before-gpc-poll
checkpoint=before-page5-read
checkpoint=gpc-poll-ok raw=0x00000001 polls=5
checkpoint=poll-to-sysfs-return-ns value=34500
stage=after-gpc-page5 address=0x20e005004 value=0x00000000
stage=finished rc=0
stage=watchdog-disarmed
```

The time is 34.5 µs from a monotonic timestamp **taken after** the successful
poll to completion of the sysfs read, including checkpoint output and the
kernel module's mapping/read/unmapping. The code does not timestamp the
polling load itself, so 34.5 µs is not a strict upper bound on the entire
poll-to-read interval; scheduling or delay before that first timestamp is
unmeasured. It is a much closer sample than the earlier approximately
51-second-later capture, not proof the bit was never briefly set.

The iPad remained reachable immediately after watchdog disarm. This single
Linux sample `0` differs from the separate iPadOS post-GPC poll sample
`0x40000000`. The samples remain different OS boots with different execution
and MMIO paths. This does not prove equal physical mapping, exclude an earlier
transient, identify the bit or establish causation for the core-read stall.
No GPU-core access or page-5 write was performed by the timed probe. Capture:
`artifacts/live/gpu/gpc-page5-timed-20261110-02/`.
