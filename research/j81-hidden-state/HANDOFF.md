# Research agent and runner handoff

## Start on another computer

Fetch the public work and use a separate checkout to preserve local runner changes. The share packet contains the report, all four research appendices/instructions, narrow timeline, test and helper, and the expected output. If the share uses another name, change ARCHIVE only. The tests run offline and require Python 3. Use macOS for reading an Apple logarchive.

    git clone --branch research/j81-next-gpu https://github.com/mattonik/ipad-nixos.git ipad-nixos-hidden-state
    ARCHIVE=/Volumes/martin-home/Projects/Archive/ipad-nixos
    MAIL="$ARCHIVE/builder-mailbox"
    PACKET="$MAIL/from-builder/2026-11-21-j81-hidden-state-result"
    cd "$PACKET"
    shasum -a 256 -c SHA256SUMS
    STOCK="$MAIL/to-builder/2026-11-19-j81-miscacg-3dbfe00"
    LIVE="$ARCHIVE/local-setup-20261118/ipadlinux/ipad-nixos/artifacts/live"
    PYTHONDONTWRITEBYTECODE=1 python3 check_j81_hidden_state.py "$STOCK/kernel" "$STOCK/j81dt" "$LIVE/gpu/dwi-gpu-compare-20261111-01"

Compare stdout to OFFLINE.txt. To transfer privately, copy the result directory intact. Pass the three local input paths explicitly if the private inputs live elsewhere. Keep raw kernel images, unified logs and machine-specific capture data on the share. The Git report lives at research/j81-hidden-state/RESULT.md. Record the Git revision and packet checksum manifest with the next result.

## Independently reproduce the iPadOS order

1. Inspect success-rail-order.tsv and match all eight records to UUID DCE69446-4DFB-405B-BDAD-79790E1714EB. The UUID in parentheses on plain kernel.log lines can identify the binary, so use structured bootUUID for joining across services. All times below are Europe/Bratislava time. An example narrow query on a Mac in that timezone is:

       /usr/bin/log show --archive "$LIVE/private/ios-logarchive-j81-pmgr-bisect-03/boot.logarchive" --start '2026-11-14 20:57:11' --end '2026-11-14 20:57:13' --style ndjson --info --debug --predicate 'eventMessage CONTAINS "J81_BOOT" OR eventMessage CONTAINS "buck mask" OR eventMessage CONTAINS "AppleD2207PMU::start" OR eventMessage CONTAINS "Added AppleARMPMUCharger"'

2. Order by machTimestamp. Confirm CORE=00070500, then the DWI message, then the PMIC message. This establishes message order. For instruction order inspect the exact 19H394 kernel (SHA-256 c3507666766775dc854d5bcf6c375e6651ac8b2d1adb13d06331c60deb6a0008). With llvm-objdump available, use:

       llvm-objdump -d --start-address=0xfffffff006c9a270 --stop-address=0xfffffff006c9a5cc "$STOCK/kernel"
       llvm-objdump -d --start-address=0xfffffff006ce71f0 --stop-address=0xfffffff006ce77e0 "$STOCK/kernel"
       llvm-objdump -d --start-address=0xfffffff006c8a164 --stop-address=0xfffffff006c8a238 "$STOCK/kernel"

3. Find any *earlier* DWI-specific event attributable to the same start invocation, ideally the clock-gate-54 request, map completion or first MMIO write. Preserve CPU/thread, UUID, exact marker and attribution. A missing log entry does not timestamp a write. If an earlier start marker has an ambiguous thread or service, report an open interval. The PMIC superclass call before its banner deserves separate treatment from the later external writes.

## First runner comparison

1. Search existing raw data for a single no-core Linux boot that had page 5 high and sampled both DWI PS and D2207 row 0x0128 before and after GPC. Check the Nov 21 no-core and bridge-readback runs first. Do not merge their PMGR samples with the Nov 11 PMIC bytes. If absent, list the missing fields. Recover the new boot UUIDs and module/build hashes from the runner's private manifests.
2. If a fresh measurement is available within the runner's normal scope, use the already returning single-activation no-core control. Preserve its GFX power, bridge, GPC and watchdog sequence. Sample previously characterized PMGR registers: DWI PS 0x20e020120, GFX PS 0x20e020320, GFX VID 0x20e02300c, page 5 at 0x20e005004 and perf 0x20e01c200. Obtain before/after external PMU samples through the established owner of the I2C0 PMIC at 0x3c. Record the raw eight-byte response for row 0x0128, especially bytes 0 and 2. Take bus diagnostics outside the IRQ-off batch, record timestamps and phase, and keep the existing in-batch GPC/page-5 observations. If the bus owner cannot supply a sample, preserve the missing field. Sampling can itself resume the I2C domain; distinguish I2C0 from DWI.
3. Return boot UUID, build and module digests, measurement width, PMIC access method, CPU, raw values, GPC raw/poll count, both page-5 samples if available, watchdog outcome, and health after the run. A new core access or PMIC write is unnecessary for this comparison.
4. If GFX VID reaches 0x164 and external bytes remain 00/40 with page 5 high, investigate transport state and retention. If the bytes reach 64/64 with page 5 high, rank the missing-digital-code explanation lower and compare core-side clock, physical mapping and isolation. For either outcome, prioritize an equivalent existing iPadOS diagnostic. Actual voltage needs characterized telemetry or a calibrated board measurement. No regulator command or higher voltage is supported by these results.
5. Return RESULT.md, raw excerpts, a per-boot phase table and SHA256SUMS in a fresh from-builder/2026-11-21-j81-page5-high-pmu-result directory, suffixing if occupied. For further software research add a separate ordered-service table showing driver, instruction VA, physical/service target, observed time bounds and uncertainty. Commit the public findings and tests to the research branch, push, then record the revision in the private packet.
