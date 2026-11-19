# Linux gated core-ID read after the MiscACG write: result (2026-11-19, one boot, iPad Air 2 J81, observer kernel a2dda271...)

Boot 49df36fd-3c32-4e35-bbbb-51a4af673ee0, fresh observer RAM boot, repo preflight GO. Plan/code: ../2026-11-19-j81-linux-core-id-prepared/.

## Result: the core-ID read at 0x201000020 HUNG; every gate before it passed. The watchdog reset the iPad.
Campaign part (unchanged, summary.txt): MiscACG A/B 0 -> stored 1 (old=0, new=1) -> B2 1; GPC raw 1 after 11 polls; page-5 samples 0x40000000 and 0x40000000; perf 0x80110100, 0x2300c = 0x164.
Core-ID step (core-id.log, supervised, all READs acknowledged and fed):
| stage | address | raw |
| --- | --- | --- |
| pmgr-read (GFX PS) | 0x20e020320 | 0x000003ff |
| miscacg-read | 0x20e032000 | 0x00000001 |
| page5-read | 0x20e005004 | 0x40000000 (bit 30 set) |
| gpc-state | 0x201e01000 | 0x00000001 |
| gpc-control | 0x201e00000 | 0x40000000 |
| gpu-revision | 0x201000020 | `stage=before-gpu-revision` printed and READ acknowledged; NO `stage=after-...`, no further output |
After the last checkpoint the device went silent; the supervisor's 20 s hardware watchdog expired and the iPad rebooted (core-id-result.txt: "no result ... may have been reset by the watchdog"). The earlier results were already on disk.

## Interpretation
MiscACG = 1 before GPC is sufficient for page-5 bit 30 on Linux (3 of 3 write boots) but not for the core window: its first read still hangs where iPadOS returns 0x00070500.
Either another iPadOS startup step is still missing, or the read depends on timing (iPadOS reads it milliseconds after GPC completion; here seconds later). Not established; not repeated.
