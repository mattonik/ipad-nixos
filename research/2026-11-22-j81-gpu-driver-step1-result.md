# j81-gpu driver steps 1 and 2: first hardware run, result (2026-11-22, run 1)

Plan: `2026-11-22-j81-gpu-driver-step1-plan.md`. Module sha256 c902b732..., always-on observer bundle, dashboard stopped. Logs (private): `artifacts/live/private/j81-gpu-run-20261122-run1`.

**Step 1 passed, entirely in-kernel**: precheck, pmgr stores (PLL1, PLL4, MCC x5, MiscACG, TVM), activate (gfx_ps 0x3ff), batch: state=identified, core=0x00070500, id=0x011b0803, hi=0, GPC raw 1 after 28 polls, page 5 0x40000000, core_read_ns 542. Prediction confirmed. No userspace tools needed.

**Step 2: all 15 allow-listed reads returned, no hang** (values from the first RGX page):

| offset | name | value |
|---|---|---|
| 0x0000 / 0x0004 | CLK_CTRL lo / hi | 0x2a2aaaaa / 0xa02aaa00 |
| 0x0008 / 0x000c | CLK_STATUS lo / hi | 0x00600000 / 0 |
| 0x0028, 0x0030, 0x0040 | DESIGNER_REV_FIELD1/2, CHANGESET_NUMBER | 0, 0, 0 |
| 0x0100 / 0x0104 | SOFT_RESET lo / hi | 0 / 0 |
| 0x0130 | EVENT_STATUS | 0 |
| 0x0160 | TIMER | 0x0000b9c0 |
| 0x03c8 | SIDEKICK_IDLE | 0x0000007e |
| 0x08f8 | MARS_IDLE | 0 |
| 0x0a10 | META_SP_MSLVCTRL0 | 0 |
| 0x0a18 | META_SP_MSLVCTRL1 | 0x07000040 |

Reading (register names from the upstream PowerVR headers; not verified for Apple's variant):
- SOFT_RESET = 0: no block is held in reset, including the firmware core.
- META_SP_MSLVCTRL1 = 0x07000040: bits 24 (READY), 25 (COREMEM_IDLE) and 26 (GBLPORT_IDLE) are set, so the META slave port answers and is idle. This suggests the firmware processor is reachable by host reads/writes through the slave port.
- CLK_CTRL fields are all in the same non-zero pattern (0x2a/0xaa); meaning of the fields not decoded here.
- TIMER non-zero (counter value; not checked whether it advances).
One device, one run.

Next (read-only): read META registers through the slave port (MSLVCTRL0 address select + MSLVDATAT), starting with the META core ID, then TXENABLE/status; each its own stage.
