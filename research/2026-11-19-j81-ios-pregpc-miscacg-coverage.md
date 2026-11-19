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
| probe-v4 (R9 in P0, but entry-site hook) | no data | never run; would sample at ApplePMGR entry, before enableACG |
A requested store (the static enableACG store) or the post-enable read from another boot cannot stand in for the pre-GPC field, as the instructions say.

## 2b. Search done
All kernel.log files under artifacts/live/private/*/ and */result/ searched for "J81_BOOT" and for R9-bearing records: only the Nov 14 rows
(plus re-captures of them) exist. Raw files: ios-logarchive-j81-pmgr-bisect-03/{kernel.log,capture.tar} digests in evidence/archive-bisect-03.sha256.

## 3. CORRECTION (same day): probe-v4 is NOT a read-only variant of the working sequence
The first version of this section called probe-v4 (784ab3b1...) the prepared pre-GPC observation. That was wrong. Decoding the hook-site
constant in the module (`mov x8,#-0x6514; movk #0x6bb,lsl#16; movk #0xfff0,lsl#32`) gives:
- run-3 module 0a20ead8... (v2 == v3, the build that produced boot DCE69446): hook at 0xfffffff006bb9aec, the success return at the END of ApplePMGR::start().
- v4 (784ab3b1...): hook constant -0x6e08 -> 0xfffffff006bb91f8, the ENTRY-lineage site (retained entry-control sources j81-entry-*-control use 0xfffffff006bb91f8).
So v4 would sample R9 at ApplePMGR entry, before enableACG(true): that is the already-known entry value 0, not a pre-GPC value. At that site the retained
GPC controls with the third write (+0x1000 <- 0x11) stalled after kernel handoff. v4 was therefore NOT run, and it must not be used for this question.
What it does show: the v4 P0 block confirms the field-to-address mapping (S=+0x20320, F=+0x5004, P=+0x1c200, V0=+0x23000, V1=+0x2300c, R9=+0x32000).

### What a valid observation needs
An end-of-start build (hook 0xfffffff006bb9aec, run-3 behavior) whose P0 additionally reads PMGR +0x32000 before the GFX power-on, bridge stores and GPC writes.
The run-3 source is not retained in any tree found on this machine (only the binary), so this needs a rebuild from the entry-lineage sources with the hook site, signature guard
and w0=1 resume of run 3, then the kpf-test acceptance on the exact 19H394 kernel. Not built yet.

## Interpretation rule, restated (from the instructions)
If R9 reads 1 before GPC and page 5 rises -> phase-matched candidate difference for separate review.
If R9 reads 0 there and page 5 rises -> a retained 1 is unnecessary for that response; a transient earlier effect remains possible.
Linux control (already returned): A/B/C MiscACG all 0, GPC raw 1 at poll 11, page-5 0 and 0.

