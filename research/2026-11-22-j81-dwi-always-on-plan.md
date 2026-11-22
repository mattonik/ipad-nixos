# Point 2 plan: dwi always-on from boot (2026-11-22)

Build: `kernel/dwi-always-on-observer` = observer kernel (0123 + research/probes/j81-linux-gfx-request.patch) + patch 0125 (`&ps_dwi { apple,always-on; }`). Kernel Image is byte-identical to the one in the id bundle (sha256 cb8429736cd20818...), so build-id notes sha a2dda27 and the pinned modules/wrappers are unchanged. DTB has `apple,always-on`. Bundle: private `j81-dwialwayson-bundle-20261122` (only m1n1-linux.bin differs from the id bundle; sha prefix 40664e8e). Runner: private `j81-linux-dwialwayson-experiment` (no late dwi store; stops unless dwi reads 0xff at start and after TVM).

Prediction: dwi reads 0xff from first snapshot; same recipe and identity words as the late-store runs (core 0x00070500, id 0x011b0803, hi 0), PMIC row 0x0128 -> 64 00 64 00 held 10 s.
Open: whether dwi is already 0xff at the first snapshot with always-on; if it is 0x200 the runner stops before any write (nothing changed). Dashboard is not stopped here; squares do not matter unless it hangs.
