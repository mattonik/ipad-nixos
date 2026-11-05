# J81 next segment stopped at GPC read

The next selector-9 segment was attempted in the already-running boot after
the earlier two segments. The watchdog reached the PMGR checkpoint and read
`0x000003ff`, then the GPC state read at `0x201e01000` did not return. No
bridge entry from this segment was written. The host connection disappeared;
the user reported that the iPad rebooted.

This demonstrates the cumulative-state hazard: a previously successful bridge
sequence does not make another same-boot MMIO access safe. The boot must be
treated as ended and the segment must not be retried in it.

Private capture:
`artifacts/live/private/gpu-observations/2026-11-05-bridge-segment-9-next4b.log`

Capture SHA-256:
`bdebaf4b85574cdb6ec054c5d1b2b302828441f3216205bd11c2ca07c7502e98`
