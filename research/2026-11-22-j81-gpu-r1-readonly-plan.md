# R1/R2 read-only run: META_BOOT, BIF, SLC and segment registers (plan, 2026-11-22)

From `2026-11-22-j81-meta-boot-research-result.md` (t5 steps R1, R2). Module `kernel/j81-gpu` rebuilt (sha256 8975300174402a1f...): RGX mapping grown from 0x1000 to 0x4000 bytes (mapping only; no access outside the allow-list), 14 more allow-listed offsets, META segment words 0-3 allowed. The wrapper now runs META reads before RGX peeks.

Order (a hang names the last announced stage):
1. META slave port: MMCU_SEG0..3 (BASE, LIMIT, OUTA0, OUTA1 = 0x04850000-0x0485003c, 16 words) and coremem 0x80000080/0x80000084.
2. RGX page 0: MSLVIRQSTATUS 0x0ac8, META_BOOT 0x0bf8/0x0bfc.
3. RGX BIF: BIF_CAT_BASE0 0x1200/0x1204, 0x1288, 0x1290, BIF_CTRL 0x12a8, fault status 0x12b0, 0x1340.
4. RGX SLC: SLC_CTRL_MISC 0x3800/0x3804, 0x3808, SLC_IDLE 0x3898.
Predictions (from the research, claims): META_BOOT 0 (explaining why META is not running), BIF_CAT_BASE0 0, segment 2 at its default, SLC_IDLE reading idle bits. Unknown: whether the registers beyond the first 0x1000 respond at this clock state; the previous reads of the first page all did. A hang means a register beyond that is unsafe: watchdog reset, fresh DFU; the identity and META results would be in the log already.
Dashboard stopped.
