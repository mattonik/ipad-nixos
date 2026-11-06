# J81 GPU-core hang: offline boundary analysis

The fresh hardware results now separate three paths:

* PMGR acquisition succeeds (`0x000003ff`).
* Fender/GPC initialization succeeds: the bounded writes reach state `1`.
* The bridge read at `0x201f00018` succeeds under the watchdog.
* The first direct RGX read at `0x201000020` hangs and drops USB networking.

The Orchard G5P transport patch explains why the last step is not yet a valid
standalone probe. Its `g5p_fender_wake_once()` sequence performs a bounded
incoming PMGR cycle before Fender access, then uses the Apple wake path and
only later calls `g5p_read_id()`. The patch also documents that maps need the
core ID “read through the woken wrapper”; the GPC state value alone is not a
proof that the RGX slave port is usable. The recovered transport additionally
has a reset-generation gate and an explicit core-request/GPC-0 edge before a
later GPC-1 release.

Our successful `gpu-gpc-init` reproduced the three Fender writes and poll but
did not reproduce that full reset-generation/wrapper ownership contract. The
GPU-core hang is therefore best classified as **missing wake/reset sequencing**,
not evidence that `0x201000000` is the wrong address.

Decision: do not retry `0x201000020`, read `0x201000018`, upload firmware, or
render. The next candidate must be a separately gated, one-shot Fender
reset/wake state machine that records the PMGR off/on generation and the
core-request/GPC-0/GPC-1 edges before any RGX read. No such candidate is being
run automatically.

Offline validation remains clean: 82 passed, 7 input-dependent skips.
