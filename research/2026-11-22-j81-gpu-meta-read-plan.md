# j81-gpu step 3a: META slave-port reads (plan, 2026-11-22)

After `...-step1-result.md` (META_SP_MSLVCTRL1 = 0x07000040: ready and idle). Module `kernel/j81-gpu` rebuilt (sha256 4c2e221d...), same supervisor and runner; new `--meta` list.

Method (upstream pvr_meta_cr_read32): wait MSLVCTRL1 READY|GBLPORT_IDLE (bounded 1 ms), write MSLVCTRL0 = addr | RD_EN (an address select, the first GPU register WRITE of the survey), fence read, wait ready again, read MSLVDATAX. Waits are bounded; a timeout returns an error, not a hang. Only 12 allow-listed addresses, each its own stage:
0x04831000 META_CORE_ID, 0x04800000 T0ENABLE, 0x04800010 T0STATUS, 0x04801000 T1ENABLE, 0x04801010 T1STATUS, 0x048000b0 TXCLKCTRL, 0x048000e8 T0PRIVEXT, 0x04830030 SYSC_JTAG_THREAD, 0x04830018 MMCU_DCACHE_CTRL, 0x04830020 MMCU_ICACHE_CTRL, 0x04850000/04 MMCU_SEG0_BASE/LIMIT.

Questions it answers: which META core (CORE_ID version fields), whether thread 0 is running (ENABLE bit 0) and its status, the state of the clock gating and caches, and the segment MMU left by the previous owner (iBoot/iPadOS state, so firmware may even still be in memory).
Prediction: unknown. If the META core is not clocked the first read may time out (bounded, reported). A hang would mean the slave-port access itself is unsafe in this state; watchdog reset, fresh DFU.
Dashboard stopped as before.
