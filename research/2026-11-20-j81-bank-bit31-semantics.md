# J81 five-word PMGR replay and the GPU-ID stall

**Hardware result.** Fresh Linux boot 36e22c25 completed all five readbacks, then MiscACG bit 0 and GFX power came up, GPC reached state 1 after 11 polls, and both page-5 reads returned 0x40000000. The last marker was before-gpu-revision. No GPU-ID was recorded before the runner reported a watchdog reset. This rules out simply missing these five bit-31 writes as a sufficient explanation for the Linux stall under this sequence. It leaves open whether they are prerequisites. The last marker bounds the failure but cannot identify the instruction where progress stopped.

| PMGR offset from 0x20e000000 | Immediate readback | Later S3, before MiscACG/GFX |
|---|---|---|
| 0x22000 | 80000000 | 80000000 |
| 0x22090 | 89070300 | 89070300 |
| 0x220a0 | 89040300 | 89040300 |
| 0x220b0 | 89060300 | 89060300 |
| 0x22130 | 89040300 | c9040300 |

The stopped first run reproduced the last word's bit-30 transition without attempting GPU-ID. Its cause is unknown. That bit and the bit in the separate page-5 register are distinct observations. Source packets on the share under builder-mailbox/from-builder are 2026-11-20-j81-linux-mcc-write-result and 2026-11-20-j81-linux-mcc-write-run1-stopped.

**Stock code.** J81 iOS 8.1 (12B410) already sets exactly those five bits on its normal startup branch. Archived T7000.raw file offsets 0x538c..0x540f read/OR/write bit 31 in the order +22000, +220a0, +22130, +220b0, +22090. T7000 selects +22140 in the third position. See gpu-offline/t7000-map.c lines 94–121 and t7000-flags.c lines 81–92, 177–180, 305–306, 338–341 for the chip-ID selector and pmgr_disable guard. 19H394 VA 0xfffffff006c8a0c4 applies the bit to 19 entries with 0x10 stride and skips six positions. Its observed startup call site at VA suffix 6bccf34 passes true. The loop preserves bits 30:0 and can also clear bit 31 on a false argument. Applied to the archived Linux dump it changes exactly the same five words.

The code establishes a board-selected per-entry control bit. Its hardware client and electrical function remain unidentified. The adjacent named enableACG method is slot +0x690. The bank loop is +0x688. The separate method at suffix 6c8a01c resolves function-mcc_ctrl (J81 ADT phandle 0x20, /arm-io/mcc, selector Mem$) and a fast-CPU frequency threshold for the callback path at 6c8a2f4. The bank loop uses neither. The later 15.8.8 LLB initializes payloads while preserving upper bits at four of the offsets (dec_15llb_page5.c lines 261–299). Neither source assigns a GPU clock or cache name to bit 31. Linux separately describes the GFX power-state register at +20320 in the [A8X PMGR device tree submission](https://lists.infradead.org/pipermail/linux-arm-kernel/2024-December/988514.html).

**Offline reproduction.** On Apple Silicon macOS run python3 tools/test_j81_bank_enable.py T7000.raw kernel linux-pmgr-0x22000-0x223fc-words.txt. The test authenticates both binary images and executes the archived instructions against host RAM. It checks the complete 256-word bank against the Linux capture and two synthetic patterns, for both old board branches and both directions of the 19H394 loop. RAM models neither hardware feedback nor timing.

**Next observation.** On three separate iPadOS boots the low 32 bits of CPU cluster +0x20, +0x48 and +0x1b0 respectively returned zero. These variants used the CORE field for the CPU read. None pairs that zero with a GPU-ID on the same boot. Test +0x68 low using the existing cpu68 variant at the same hook. 15.8.8 LLB instruction VAs 0x1803904dc and 0x180390644 write 0x00080000 to the low word, and 19H394 suffix 6c887cc..6c887e4 preserves it when copying the high byte. A nonzero result validates that the observer can see data somewhere in this block. A zero leaves the release, stage, mapping and access width unresolved. No clock or voltage write is needed.
