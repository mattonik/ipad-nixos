# R1/R2 read-only run, result (2026-11-22, run 1)

Plan: `2026-11-22-j81-gpu-r1-readonly-plan.md`. Module sha256 8975300174402a1f.... Logs (private): `artifacts/live/private/j81-gpu-r1-20261122-run1`. Identity as before (core 0x00070500, id 0x011b0803). All 18 META-port reads and all 14 RGX reads returned; no hang.

| register | value | note (research predictions are claims) |
|---|---|---|
| META_BOOT 0xbf8/0xbfc | 0 / 0 | as predicted: master-boot mode not set, which explains why META never ran |
| BIF_CAT_BASE0 0x1200/0x1204 | 0 / 0 | as predicted: no page catalogue programmed |
| BIF_CTRL 0x12a8 | 0x000000c0 | |
| BIF 0x1288, 0x1290, fault status 0x12b0, 0x1340 | 0, 0, 0, 0 | no fault, no pending IRQ bits |
| META_SP_MSLVIRQSTATUS 0xac8 | 0 | |
| SLC_CTRL_MISC 0x3800/0x3804 | 0x00320001 / 0x00035500 | stock writes 0x0003550000300001: high word equal, low word differs by bit 17 |
| SLC 0x3808 | 0 | stock writes 1 |
| SLC_IDLE 0x3898 | 0x000000ff | idle bits all set (stock waits for 0xff before power-down) |
| MMCU seg0 BASE/LIMIT/OUTA0/OUTA1 | 0x08000f02 / 0x17fff000 / 0x88000000 / 0 | hardware defaults |
| seg1 | 0x20000f02 / 0x1ffff000 / 0xa0000000 / 0 | |
| seg2 | 0x40000f02 / 0x1ffff000 / 0xc0000000 / 0x000007e1 | OUTA1 low byte 0xe1 with 7 in bits 15:8 = GPU VA 0xe1_c0000000 with DM 7: the default boot mapping the research expected (upstream claim) |
| seg3 | 0x60000f02 / 0x1ffff000 / 0xe0000000 / 0 | |
| coremem 0x80000080/84 | 0xfdfdefff / 0x18a15406 | unloaded memory contents |

Reading: the GPU is exactly in the reset state stock expects before firmware start: META not in master-boot mode, no page catalogue, default segment map (seg2 already points at the firmware heap VA 0xe1c0000000), SLC nearly at stock value, SLC idle. The segment default OUTA1/dm encoding agrees with the (va >> 32) | (dm << 8) form from the research. One device, one run.
Next: W0 (page tables, firmware buffer and boot list built in memory only) and W1 (first GPU write: rewrite META_BOOT 0, read back, tests whether direct writes land or the Fender mailbox is needed).
