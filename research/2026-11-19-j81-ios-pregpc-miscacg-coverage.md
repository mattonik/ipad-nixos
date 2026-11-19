# Answer to to-builder/2026-11-19-j81-ios-pregpc-retention

Date 2026-11-19. Offline work only: no iPad access, nothing run. Linux one-shot result left unchanged
(from-builder/2026-11-19-j81-observer-finished-ed70e35-result).

## Verdict: coverage gap. The retained iPadOS archives do NOT contain a pre-GPC MiscACG (+0x32000) value.

### 1. The November 14 boot DCE69446-4DFB-405B-BDAD-79790E1714EB (ios-logarchive-j81-pmgr-bisect-03)
Boot UUID confirmed from the unified-log records themselves (evidence/bisect-03-j81-boot-records.ndjson, `log show --style ndjson`,
process /kernel, logger "AGXk: Starting GPU driver. Available features: %s"). The boot has exactly five J81_BOOT records:

| machTimestamp | local time | record |
| --- | --- | --- |
| 994228592 | 20:57:12.167310 | J81_BOOT P0 S=00000300 F=00000000 P=80000000 V0=00000001 V1=00000000 |
| 994245647 | 20:57:12.168020 | J81_BOOT GPC TICKS=00003929 |
| 994246296 | 20:57:12.168048 | J81_BOOT P1 F=40000000/40000000/40000000 P=80110100 V0=00000001 V1=00000164 G=30303000 |
| 994246926 | 20:57:12.168074 | J81_BOOT BEFORE CORE READ |
| 994247261 | 20:57:12.168088 | J81_BOOT CORE=00070500 |

Address mapping of P0/P1 fields, confirmed from the probe code, not only from notes. The build that produced this boot is module
0a20ead8... (probe-v2 == probe-v3, sha256 in evidence/probe-builds.sha256) and the sampling code is the sibling build v4
(784ab3b1...), whose P0 block (evidence/v4-p0-sampling-block.dis) reads, in this order, before logging:
S = PMGR+0x20320 (GFX PS), F = +0x5004 (page-5 +4), P = +0x1c200, V0 = +0x23000, V1 = +0x2300c, then (v4 only) R9 = +0x32000.
In v3 (the run that produced DCE69446) the disassembly contains no 0x32000 access at all and no " R9=" format string; P0 has no sixth field.
So the successful boot sampled GFX PS, page 5, perf, VM0, VM1 before the GPC request and never MiscACG.
- Page 5 +4 = 0 before GPC, 0x40000000 (bit 30) in all three samples after GPC (poll ended after 0x3929 ticks), core ID 0x00070500.
- Core ID: no separate core-ID record besides CORE=00070500. GPC completion is only GPC TICKS (no raw GPC word logged, `G=30303000` is a log-buffer field).
- The earlier boot F83AD018-BD6F-4C39-BF27-507D7502B2E8 (20:13) only has P0 and STOP C=7 (GPC poll limit): no page-5 rise, no MiscACG.

### 2. Every other retained iPadOS source, and why none fills the field
| Source | MiscACG value | Why it cannot fill "pre-GPC in a boot where page 5 rises" |
| --- | --- | --- |
| j81-ios-entry-*/entry controls (Nov 15, boot-scoped, prints `r9=`) | 0 | at ApplePMGR entry, BEFORE enableACG(true); no successful GPC |
| j81-ios-miscacg-read-probe (Nov 19), boots B5C9CF9C-F412-416E-BC8E-0DFCA7F459B6 and 6B5D51C5-D33A-4FE2-947C-E26532C14C5F | 1, 1 | immediately after enableACG(true) returned; probe has no GPC/page-5 path (gpu-offline/j81-miscacg-log-review-20261119T161450/miscacg.ndjson) |
| ios-logarchive-j81-pmgr-bisect-0{1,2,3} and every later archive that merely re-contains the same Nov 14 rows (store-sample, store-slice, window-probe ...) | no field | same five records as above |
| probe-v4 (has R9 in P0) | no data | never run: no " R9=" record exists in any retained kernel.log |
A requested store (the static enableACG store) or the post-enable read from another boot cannot stand in for the pre-GPC field, as the instructions say.

## 2b. Search done
All kernel.log files under artifacts/live/private/*/ and */result/ searched for "J81_BOOT" and for R9-bearing records: only the Nov 14 rows
(plus re-captures of them) exist. Raw files: ios-logarchive-j81-pmgr-bisect-03/{kernel.log,capture.tar} digests in evidence/archive-bisect-03.sha256.

## 3. Prepared read-only pre-GPC observation (NOT built or run)
Candidate: probe-v4 = j81-ios-pmgr-bisect-probe-v4/checkra1n-kpf-pongo-j81-pmgr-bisect, sha256
784ab3b183344f30be66d395d6a169b78b89a51e5249b8f24812e2bb2dfc6a8d. Against the run-3 module it adds exactly one read-only
sequence in the P0 block: `add x0, x20, #0x32, lsl #12; bl <mmio read>; str w0, [sp,#0x43c]` and the printed field ` R9=`, i.e.
P0 would read `J81_BOOT P0 S=.. F=.. P=.. V0=.. V1=.. R9=<MiscACG>`. P0 is logged before the GFX power-on, the 66 bridge
stores and the GPC writes, so it is a pre-GPC value in the same boot as the existing GPC / page-5 / core-ID sequence. The GPC and page-5
ordering is unchanged and there is no MiscACG write. Store/barrier instruction diff against v3 shows no added store (only the one
sp-relative spill of the read value).
Not yet established (honest limits): the v4 source is not retained here (only the binary), so equivalence of the rest of v4 to v3 rests on
the disassembly diff; v4's hook-site / kernel-UUID guard and the 19H394 kpf-test acceptance should be re-run on the builder before a hardware
boot. The entry-lineage shell sources in /private/tmp/j81-entry-*-control show the same ` R9=`/+0x32000 convention (R9 = MiscACG).
Run condition for a later hardware step (Martin's DFU/palera1n step): temporary rootless iPadOS boot with this module, then whole-device
unified-log collection and a `log show --style ndjson` filter for "J81_BOOT"; keep bootUUID/machTimestamp with every row.

## Interpretation rule, restated (from the instructions)
If R9 reads 1 before GPC and page 5 rises -> phase-matched candidate difference for separate review.
If R9 reads 0 there and page 5 rises -> a retained 1 is unnecessary for that response; a transient earlier effect remains possible.
Linux control (already returned): A/B/C MiscACG all 0, GPC raw 1 at poll 11, page-5 0 and 0.

