# Orchard GPU PR #74: relevance to J81 (2026-11-05)

Orchard currently has an open draft, [PR #74](https://github.com/OrchardLinux/orchard/pull/74),
adding experimental A9/G5P rendering for J71t with the original Apple META
firmware. Its useful precedent is the workflow, not the driver:

* extract the firmware locally from the user's iOS kernelcache;
* require an exact section size and SHA-256, rejecting other revisions;
* install the original LDR at runtime and keep firmware out of Git;
* qualify the complete host/firmware path before claiming rendering.

The PR's hardware result is on A9/G5P (S8003/J71t), not A8X/G4G (T7001/J81),
and the patch set is not evidence that G4G can use the G5P transport, register
setup, memory layout, or userspace ABI. Its description explicitly says the
Orchard export itself still needs a build and device qualification.

For J81, the analogous safe deliverable is therefore the existing private,
hash-checked `AGXFirmwareKextG4G` extraction plus the execution-disabled
host-plan/simulator. The remaining blocker is still the host allocation and
thread-start contract: the real image's Apple slot 1 begins at `0x20000000`
and thread 1 points at that exact base, while Linux's generic META driver
exposes only one `FW_DATA` allocation. No firmware upload is justified by this
PR.
