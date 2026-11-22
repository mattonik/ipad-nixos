# j81-gpu step 3a: META slave-port reads, result (2026-11-22, run 1)

Plan: `2026-11-22-j81-gpu-meta-read-plan.md`. Module sha256 4c2e221d.... Logs (private): `artifacts/live/private/j81-gpu-meta-20261122-run1`. Identity again as before (core 0x00070500, id 0x011b0803). All 12 META reads returned, no hang, MSLVCTRL1 stayed 0x07000040 (ready+idle) throughout.

| META address | name | value | reading |
|---|---|---|---|
| 0x04831000 | META_CORE_ID | 0x141e0203 | version byte (bits 23:16) = 0x1e = MTP219 in the upstream header's table: the firmware core is a META MTP219 |
| 0x04800000 | T0ENABLE | 0x0201c032 | bit 0 = 0: thread 0 NOT running |
| 0x04800010 | T0STATUS | 0x00020000 | PRIV bit set (as in upstream TXSTATUS_PRIV) |
| 0x04801000 / 0x04801010 | T1ENABLE / T1STATUS | 0x0201c132 / 0 | thread 1 not running |
| 0x048000b0 | TXCLKCTRL | 0xaa202222 | close to upstream ALL_AUTO 0xaa222222, one field differs |
| 0x048000e8 | T0PRIVEXT | 0 | |
| 0x04830030 | SYSC_JTAG_THREAD | 0x00000004 | PRIV_EN bit set |
| 0x04830018 / 0x04830020 | MMCU D/I cache ctrl | 0 / 0 | caches off |
| 0x04850000 / 0x04850004 | MMCU_SEG0_BASE / LIMIT | 0x08000f02 / 0x17fff000 | segment 0 map as left by whoever ran before (possibly hardware reset values); not decoded |

Meaning: the GPU's firmware processor is a META MTP219, idle (no thread running), reachable and readable from Linux through the slave port. That is the entry point for loading firmware: the slave port also writes META memory. Names/fields are from the upstream PowerVR headers; Apple's integration is not verified. One device, one run.
Packet 5 (post-ID bring-up) is still open and covers the firmware image, memory ownership, GPU MMU and the release sequence.
