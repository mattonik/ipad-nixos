# DWI power state and PMIC rail snapshot on the no-core control (prepared, not run)

Why: the agent's hidden-state result ranks "downstream GFX rail delivery" first (`2026-11-21-j81-hidden-state-review.md`). Our own Nov 11 notes
(`2026-11-11-j81-dwi-voltage-transport.md`) already found that the PMIC buck registers follow the PMGR voltage manager only while the `dwi` power state (0x20e020120) is on,
and that Linux switches `dwi` (and nineteen other boot-chain domains) off about 0.7 s into the boot; the GFX state-1 request (voltage word 0x2300c = 0x164) then never reaches
the PMIC (buck 1 at 0x0128 stayed `00 .. 40` with DWI off, `64/64` after the request with DWI on). The Nov 14 strategy note lists DWI as "ruled out (both orders)", but those
tests ran before MiscACG was found (Nov 19): the core read would have hung without MiscACG regardless, so they could not discriminate. With page 5 now high on Linux, the observer's
DWI state and PMIC bytes have never been measured.

What: runner `artifacts/live/private/j81-linux-dwi-experiment/runner/boot` + the existing `j81-nocore-bundle-20261121` (module `4827876e...`, no rebuild; the campaign is the no-core control).
Added, all read-only: PMGR word 0x20120 (DWI PS) in every snapshot (17 words; S0..S5, A, C, plus a new snapshot D10 ten seconds after the batch); PMIC rows 0x0100, 0x0128, 0x0150, 0x01c8
via `i2ctransfer -f -y 0 w2@0x3c <hi> <lo> r8` before the batch, after the batch and 10 s later, outside the irq-off batch (files `pmic-before-batch.log`, `pmic-after-batch.log`, `pmic-after-10s.log`).
If `i2ctransfer` is missing from the observer userland the runner records `pmic-unavailable` and continues; the DWI PS and GFX VID words are still captured (summary lines `DWI PS 0x20120: S0 S5 A C D10`,
`GFX VID 0x2300c: ...`). Flow test passes (with PMIC and extra snapshot mocks); `--verify-only` passes. Risk: the I2C read can resume the I2C0 domain (distinguish from DWI); no PMIC write, no DWI write, no new core access.
Reading: DWI PS 0x200 (off) at A/C with VID 0x164 and buck 1 stuck at `00/40` -> the GPU rail request never reaches the PMIC on our Linux boots: next test = switch `dwi` on (`boot/pmgr-dwi-on.c`, one acknowledged PS write) before the GFX request,
then repeat the whole sequence and, last, the core read. DWI PS 0xff and bytes `64/64` -> rail delivery is not the difference (agent rank 1 weakens; go to mapping/isolation).
Launch: fresh DFU, same two boot commands with the `j81-nocore-bundle-20261121` Pongo.bin/m1n1-linux.bin, preflight GO, go-ahead; then from the runner dir
`python3 j81_observer_paired_campaign.py <new logdir> --bundle ../../../j81-nocore-bundle-20261121`.
