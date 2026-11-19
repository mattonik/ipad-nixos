# What the J81 page-1 and page-4 clock writes establish

ApplePMGR replaces bits 31 and 30 of two clock configuration words with binary `01`. This leaves the published-rate calculation unchanged for both pages. Page-5 bit 30 still reads clear after the normal startup path on the iPadOS boot that later reads the GPU core successfully. The pair remains a possible prerequisite for the later GPC response. Its electrical function is unresolved.

## Trace from the writer to the observed requests

On J81AP 19H394, PMGR region 0 starts at physical 0x20e000000. The T7001 method at 0xfffffff006c8872c reads +0x1008, computes `(old & 0x3fffffff) | 0x40000000`, and requests a write to the same offset. It then does the same at +0x4008 before calling its parent at 0xfffffff006c8879c. The two BFXIL instructions at method +0x24 and +0x48 copy the old low 30 bits into a register initialized to 0x40000000. Each update is unconditional on this path. Neither tests its own readback or accesses page 5. The [stock audit](../tools/audit_j81_pmgr_start.py) checks both instruction sequences.

| PMGR address | Linux after GPC1 | Predicted request from that old word | iPadOS captured request |
| --- | --- | --- | --- |
| Page 1 +8, 0x20e001008 | 0x80480348 | 0x40480348 | 0x40480348 |
| Page 4 +8, 0x20e004008 | 0x88480348 | 0x48480348 | 0x48480348 |

The iPadOS writer staged both arguments before the store in a global observation window. It did not record the old word, caller, real instance or subsequent readback. There is also a second way to reach this method. The action-key comparison at 0xfffffff006bbb438 uses `gIOPlatformActiveActionKey`. That branch calls the same vtable slot +0x5c8 at 0xfffffff006bbb7ac. XNU places this action early in wake. Both rows can therefore fingerprint the method without dating them to cold startup or the November 14 boot. [Ordinary-store capture](2026-11-17-j81-ios-g4g-ordinary-pmgr-store-capture.md) · [Apple platform action definitions](https://github.com/apple-oss-distributions/xnu/blob/xnu-8019.41.5/iokit/IOKit/IOPlatformExpert.h#L179-L186)

The named stock method `ApplePMGR::setPLLOffMode` at 0xfffffff006bcf364 also programs a high pair. Its register offset is `(index << 14) | 4` for the accepted register map. Neither of these +8 offsets nor page-5 +4 can be produced by that expression. The symbol supplies no name for our two fields.

## What the clock software consumes

The decoded J81 19H422 LLB loops over six pages and fills slots 1–6. When page-local +0 bit 31 is set, the multiplier comes from +0[20:12] and the predivider from +0[8:4]. With +8 bit 27 set the numerator is 48 MHz times the multiplier. With bit 27 clear it is 24 MHz times the multiplier divided by one plus +0[3:0]. Both paths divide by the predivider. When +0 bit 31 is clear, +4 bit 0 selects 24 MHz or zero. The loop consumes neither +8[31:30] nor +4 bit 30. Its page-5 setup earlier in this routine targets page-5 +0 bit 25, +4 bit 0 and +8 bit 24. [LLB disassembly and table layout](2026-11-09-j81-llb-page5-clock-dataflow.md)

| Page | Linux input words +0 / +4 / +8 | Calculated before and after | Independent arm-io clock slot |
| --- | --- | ---: | ---: |
| 1 | 80085040 / 40000000 / 80480348 | 798 MHz | slot 2 = 798 MHz |
| 4 | 80032010 / 40000000 / 88480348 | 2,400 MHz | slot 5 = 2,400 MHz |
| 5 | 00001010 / 00000000 / 81480348 | 0 Hz | slot 6 = 0 Hz |

Across all six pages the result is 24, 798, 24, 100, 2400 and 0 MHz. Every result matches the September 8 populated J81 arm-io table. The November 11 Linux capture, September ADT and 19H422 LLB are independent inputs. This verifies the software calculation across captures. A physical frequency, lock signal or gating state would require separate evidence. The 19H394 kernel writer and 19H422 LLB are different builds.

In the LLB's 53 static selector records (rows 8–60, 12 source/divisor pairs per row), slot 2 is an available input in six entries, slot 5 in 196, and slot 6 in zero. All 202 entries selecting slots 2 or 5 have nonzero divisors. For example, row 8 pair 1 uses slot 2 with divisor 1. Row 55 pair 0 uses slot 5 with divisor 3. These are available choices in the software table. The running selectors and the hardware clock path to the GPU remain unknown.

There is an independent stock use of PLL4 frequency metadata. The 19H394 initializer stores a frequency at object +0x35040 (instruction 0xfffffff006c886d0) and branches to an assertion naming `_pll4Frequency` if it is zero. The ISP reference clock getter at 0xfffffff006c88894 loads that cached value and divides it by two divisors. This gives the stock value a named consumer. The getter itself reads none of the three MMIO words under investigation.

## Does this explain page-5 bit 30?

The Linux capture already has bit 30 set at both **page 1 +4 and page 4 +4**, with their respective +8 high pairs still `10`. Page 5 in this same sample has +4 bit 30 clear. The bare Pongo control also has the old pair values. A page-local rule requiring `01` for +4 bit 30 therefore fails on pages 1 and 4. Page 5's status is a separate word at **0x20e005004**.

On the successful November 14 iPadOS recipe, the static startup writes precede the end-of-start marker. Page-5 +4 is zero there. After requesting GPC, the poll completes and page-5 +4 reads 0x40000000 before the core returns 0x00070500. This timing argues against a persistent immediate mirror of the startup requests. A retained configuration or a transient hardware effect that enables a later transition remains possible. That boot lacks pre-GPC readbacks for the two +8 words. A separate working identity boot read page-5 +8 as 0x81480348, the same word as Linux. [Successful timed recipe](2026-11-14-j81-ios-boot-bisect-probe1-results.md) · [Separate page-5 captures](2026-11-10-j81-page5-capture-results.md) · [Bare Pongo control](2026-11-16-j81-pongo-gpc-page5-result.md)

## Reproduce and decide

The [clock audit](../tools/audit_j81_clock_pages.py) takes the complete 42-word Linux sample and the populated ADT text. The [host test](../tools/test_audit_j81_clock_pages.py) varies both high pairs over all 16 combinations on each of pages 1, 4 and 5. Changing bit 27 instead produces 1,596 MHz and 1,200 MHz on pages 1 and 4 respectively. Native execution of the extracted LLB arithmetic on fixture memory independently reproduced the high-pair result.

Look next for the retained state immediately before GPC in a boot with a known page-5 outcome. If a failing boot retains both `01`, setting the pair alone is insufficient in that boot. If a working boot retains both `10`, retaining `01` until GPC is unnecessary in that boot. Neither comparison excludes an earlier transient effect. Working `01` against failing `10` supports a candidate prerequisite but cannot distinguish the two pages or MiscACG. [Builder instructions](j81-gpu-builder-handoff.md#compare-the-page-1-and-page-4-clock-words)
