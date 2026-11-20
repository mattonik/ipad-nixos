# iPadOS +0x2d000 probe: plan (prepared 2026-11-20, not run)

Purpose: the Linux side is now measured (`2026-11-20-j81-linux-tvm-snapshot-result.md`): PMGR +0x2d000 reads 0 at B2 (before GPC) and C (after page 5 high). The working iPadOS counterpart is missing. This probe reads it at the same two phases, one boot, read-only.

Module: `artifacts/live/private/j81-ios-tvm-probe/checkra1n-kpf-pongo-j81-tvm`, sha256 9f84397c32120380a95dfdf45f1c2fb3ca0109e0773d04ea0271b5f906b1e474. Base: run-3 module 0a20ead8... (pmgr-bisect v3, hook at the end of ApplePMGR::start(), 0xfffffff006bb9aec, same guards and GPC sequence as the successful 2026-11-14 and 2026-11-19 boots). Two instruction words changed (6 bytes differ), both `add x0, x24, #0xc` (91003300, address +0x2300c) -> `add x0, x20, #0x2d, lsl #12` (9140b680, address +0x2d000):
- file offset 0x416c, the P0 `V1=` read, before GFX power-on, bridge stores and GPC (phase of Linux B2),
- file offset 0x43e4, the P1 `V1=` read, after the GPC poll and the three page-5 samples, immediately before `BEFORE CORE READ` (phase of Linux C).
No store added. The same helper (`bl 0x45c4`, 32-bit load) is used. Region 0 +0x2d000 is the stock soc-tvm control address, in the same PMGR window as the other reads.

**Field relabel for this probe only:** P0 `V1=` and P1 `V1=` are PMGR +0x2d000. +0x32000 (MiscACG) and +0x2300c are NOT read; the 0x164 value of +0x2300c is already established by earlier boots. Other fields keep their meaning (S=GFX PS, F=page 5 +4 samples, P=+0x1c200, V0=+0x23000, G=log-buffer field).

Expected output: five `J81_BOOT` rows as in the 2026-11-19 run, core ID 0x00070500 if the boot behaves as before. Prediction under the missing-enable idea: P0 V1 and/or P1 V1 nonzero (bit 0 set) on iPadOS while Linux is 0. If both read 0, the TVM control is not the discriminator and the idea is contradicted at the sampled points; resume dpe-thrtl and CPU TVM tracing.

Run (user, iPad in DFU, unlocked after the boot): `sudo palera1n --rootless --override-kpf <module> --debug-logging`, then `sudo /usr/bin/log collect --device-udid <udid> --output X.logarchive` and filter with `/usr/bin/log show --archive X --style ndjson --info --debug --predicate 'eventMessage CONTAINS "J81_BOOT"'`, as for the 2026-11-19 pre-GPC run.
