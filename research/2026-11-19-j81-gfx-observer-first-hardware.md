# J81 first Linux GFX setter capture and the next hardware comparison

The November 19 runner report records a complete GFX power-domain cycle on a fresh RAM-root observer boot. The next useful measurement is whether that same setter sequence and a completed GPC request can coexist with page-5 bit 30 clear **on one identified Linux boot**. The first run ended at the power-domain cycle.

| Call at PMGR 0x20e020320 | Old word | Requested word | Successful poll | Auto write requested | rc |
| --- | --- | --- | --- | --- | --- |
| Active | 00000300 | 0000000f | 000003ff | 100000ff | 0 |
| Off | 000003ff | 000000f0 | 00000300 | none | 0 |
| Active | 00000300 | 0000000f | 000003ff | 100000ff | 0 |

The baseline was 0x00000300. The runner reports the same PID for all three calls, a successful one-shot cycle and two subsequent USB ping replies. The consumer executes runtime get, put, get and leaves the last reference held. The observer saves the poll word before issuing the optional auto-enable write. Its `rc=0` reports write success on the two active calls. It provides no immediate readback of the auto-enable bit. The subsequent off call starts from 0x000003ff. These data establish active/off/active at the GFX controller. This run gives no GPC result, page-5 sample or GPU core ID. [Observer source](probes/j81-linux-gfx-request.patch) · [Cycle consumer](../kernel/gpu-pmgr-cycle/gpu-pmgr-cycle.c)

The mailbox Markdown is the evidence reviewed here (SHA-256 `02f7b085be9b20a4501d9c5380a3181553b39bab73b90562e9e4af9eabde377c`). The two raw files named in it were unavailable at the cited paths in the shared snapshot. The report omits the boot UUID and binary hashes. The runner should return the original two logs and the matching preflight or boot manifest to the private mailbox. Keep the November 11 Linux GPC/page-5 result and the November 14 successful iPadOS core read as separate comparisons. [Earlier Linux and iPadOS phases](2026-11-19-j81-misc-acg-and-page5.md)

## Preserve the first boot if it is still available

Copy the raw console transcript and dmesg from the runner's working archive. Record their SHA-256 values. If the original boot UUID can be independently matched, the cycle remains active with usage 1, and no bridge or GPC operation has intervened, collect **one post-cycle sample** with the already verified PMGR word reader. Record the boot UUID before and after, its uptime and the reader hash. A changed or unknown boot gets its own evidence row. Preserve the original trace in either case. This read-only addition can proceed independently of preparing the paired probe.

## Prepare the paired boot

Use the first test's observer payload. Start a fresh boot for the complete experiment. The existing campaign starts by running the one-shot cycle itself. The old campaign, bridge wrapper and kpoll wrapper pin kernel notes beginning `82ff70e8`, and the default kpoll build pins the old kernel development tree. The first report does not establish a match. Build against the observer kernel development output and compare the derived notes digest and module identity with the first run's manifest. Use the existing guarded bridge setup and paired kpoll sequence with observer-specific artifact hashes. The baseline campaign should remain reproducible. The private packet includes builder commands and the expected evidence for each phase. [Campaign](../boot/j81_gpc_page5_kpoll_campaign.py) · [Paired measurement](2026-11-10-j81-gpc-page5-kpoll-test.md)

| Phase, in one boot | Collect |
| --- | --- |
| After the successful get/put/get, before bridge setup | All three raw setter rows, runtime status and usage, PMGR snapshot A. |
| After the existing bridge plan completes, immediately before GPC | Bridge transcript, PMGR snapshot B and initial GPC state from the guarded runner. |
| On GPC completion | Raw state, poll count, both page-5 values and validity flags, and both timing bounds from the in-kernel paired result. |
| After the paired batch returns | PMGR snapshot C, boot UUID, watchdog disarm and USB health. Keep this slower read separate from the paired reads. |

For snapshots A/B/C use region-0 offsets `20320 32000 1008 4008 1c200 2300c 5004`, in hex. They cover the GFX controller, MiscACG, both clock words, perf, GFX VID and page-5 status. They are sequential reads. For this comparison keep the established GPC and bridge operations identical across phases. Leave clock settings, MiscACG, DWI and the core-ID read out of the intervention.

- **GPC reaches 1, both valid samples clear.** This reproduces the page-5 gap in the presence of an observed GFX transition. Compare B against pre-GPC readbacks on a working iPadOS boot. Working=1 and Linux=0 for MiscACG would identify a candidate for a later isolated test. A stock staged write alone cannot answer that question.
- **Either valid sample has bit 30 set.** Report the pair in order, the timing bounds, whether B was already high and which candidate words changed A→B→C. One high sample makes a standalone repeat of the same recipe more informative than adding a core read. A high sample alone cannot identify a working core.
- **GPC poll fails or the batch is incomplete.** Preserve the last checkpoint, raw GPC result if available, observer and bridge logs. A failed poll produces no paired page-5 sample. An invalid or absent sample stays unknown. A differing setter sequence or failed bridge step moves the comparison back to that earlier boundary.

If both clock words already retain the stock high pair 01 while the paired page-5 reads stay clear, retention is insufficient for this Linux sequence. A working iPadOS capture with both words still 10 before GPC would exclude the need to retain 01 until GPC in that boot. Raw offsets, boot identity and precise phases matter for both comparisons. [Clock-word analysis](2026-11-19-j81-page1-page4-clock-control.md)
