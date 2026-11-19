# iPadOS pre-GPC MiscACG, phase-matched result (answers to-builder/2026-11-19-j81-ios-pregpc-retention step 3/4)

Run 2026-11-19 ~20:49 +0100, iPadOS 15.8.5 (19H394), temporary rootless palera1n boot, boot UUID 846527FB-1D2B-4834-AEB8-49480323BBFD.

## Result: iPadOS reads MiscACG = 1 immediately before the GPC request, and page 5 rises
| machTimestamp | local time | record (process /kernel, AGXk logger) |
| --- | --- | --- |
| 13847368728 | 20:49:29.111514 | J81_BOOT P0 S=00000300 F=00000000 P=80000000 V0=00000001 V1=00000001 |
| 13847385690 | 20:49:29.112220 | J81_BOOT GPC TICKS=00003909 |
| 13847386233 | 20:49:29.112243 | J81_BOOT P1 F=40000000/40000000/40000000 P=80110100 V0=00000001 V1=00000164 G=30303000 |
| 13847386869 | 20:49:29.112269 | J81_BOOT BEFORE CORE READ |
| 13847387204 | 20:49:29.112283 | J81_BOOT CORE=00070500 |

IMPORTANT field relabel: in this probe the P0 field printed as `V1=` is NOT the usual +0x2300c. It is PMGR region 0 +0x32000 (MiscACG),
read in the P0 block before GFX power-on, the 66 bridge stores and the GPC writes. The P1 `V1=` (0x164) is the normal +0x2300c.
- Page 5 +4: F=0 before GPC, 0x40000000 (bit 30 set) in all three samples after GPC. GPC completion: poll ended after 0x3909 ticks (about 606 us at 24 MHz; Nov 14 run: 0x3929).
- Core ID 0x00070500 (same as Nov 14). No separate GPC raw word is logged (G=30303000 is a log-buffer field, unchanged from Nov 14).

## Interpretation (per the instruction's rule)
iPadOS: MiscACG = 1 before GPC AND page 5 rises. Linux observer control (from-builder/2026-11-19-j81-observer-finished-ed70e35-result): MiscACG 0 in snapshots A/B/C,
GPC raw 1 at poll 11, page-5 0 and 0. This is a phase-matched candidate difference for separate review. It is a correlation, not proof of causation,
and says nothing about whether a Linux MiscACG write is safe.

## The probe
j81-ios-pregpc-miscacg-probe/checkra1n-kpf-pongo-j81-pregpc-miscacg, sha256 3f409df104a56f7c7ad9fd3b8b75fcbaed66e6e094678daac28e0a0ade5e8671
= run-3 module 0a20ead8... (hook at the end of ApplePMGR::start(), 0xfffffff006bb9aec, same guards and GPC sequence) with ONE instruction word changed at file offset 0x416c:
`add x0, x24, #0xc` (91003300) -> `add x0, x20, #0x32, lsl #12` (9140ca80). Only 3 bytes differ. No store added; read of +0x32000 only. (The earlier probe-v4 was rejected: entry-site hook.)
evidence/patched-p0-block.dis shows the patched block; evidence/probe-module.sha256.

