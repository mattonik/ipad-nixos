# Research request 28 result: synthesis: why J81's thread 0 never gets MTS line 0

Sources:
- the full run log (runs 54–80) and the results of requests 21–27;
- Orchard's public A8/A8X/A9 docs;
- upstream `pvr_rogue_cr_defs.h` and `pvr_fw_meta.c`;
- the decoded META firmware (private, provisional);
- the 19H394 kext.

Tags: **capture**, **source**, **fwdis**, **orchard**, **code**, **inferred**. There is no Apple binary content beyond addresses, offsets, field names and small constants.

## Short answer

**A new lead, sitting in the run log since run 77: RGX EVENT_STATUS (`0x130`) = `0x200` after alive. Upstream names bit 9 MMU_PAGE_FAULT.**
- The firmware routes that bit to its own DM4 interrupt task (`0xb78 = 0x200`, all interrupt contexts on thread 0).
- Its interrupt handler clears events (EVENT_CLEAR `0x138`), yet the bit stays set, so the handler never ran.
- Our fault check (`f3bif`) reads only bank 0 (`0x12b0`). Bank 1, the TEXAS bank and BIF_MMU_STATUS (including its STALLED bit) have never been read.
- Orchard's working A8 maps a plain zero page at GPU VA 0. We don't; request 18 noted it and ranked it low only because bank 0 was clean.

**Top hypothesis:** an MMU fault on the firmware's first access after alive stalls thread 0, or the garten, and from then on nothing is serviced (t1, rank 1). That would explain every symptom at once:
- no wake from any kick;
- the slave port never answering;
- no event and no interrupt to the host;
- the timer masked.

It also explains why every host input matching Apple's changed nothing. The test is a set of RGX reads: **X1** (t4).

**Second:** the garten fence config (`0xb50`) holds fence address `0xc0000000`, but its upper half was never programmed. Nobody writes it on J81, while upstream's host does at META wrapper init. A fence through an unprogrammed context could be the faulting access (rank 2).

Ranks 4–7 are the weaker readings, the hardware-only one included. The evidence does **not** yet point at something untestable from the host. If X1 and X2 both come back negative, it will (t4, last row).

## Q1: ranked hypotheses (t1)

Seven hypotheses, each with its evidence for and against, what it predicts, and the cheapest test. The question's (a) is rank 6, (b) rank 4, (c) rank 5, (d) rank 4, (e) ranks 1–3 and (f) rank 7.

## Q2: A8, A8X and A9 (t2)

**Same:**
- the LDR format and the same 27 configuration writes;
- the object table and the `0x30`-byte ring control (A8 and A8X);
- the firmware family: A8X uses the A9's core-memory path;
- the classic BIF MMU.

**Different on the A8X:**
- 66 bridge stores;
- `dwi` must stay on;
- the 64-bit SLC value;
- one A8X-only builder writing RGX `0x8238`.

**Orchard's A8X note** is a static kext comparison. It says the driver "has not been run on an A8X". So there is no Orchard evidence yet of a working J81 first command. The A8 consumed its first command "from the first module stage", with our host sequence plus the zero page at VA 0.

## Q3: Orchard after alive (t3)

Line by line, ours matches Orchard's working sequence except:
- the zero page at GPU VA 0 (not mapped on ours);
- the A9-only self-park arm, which comes after the first command anyway.

## Q4: next boots (t4)

1. **X1 (read-only fault census):** read EVENT_STATUS, the bank 0/1/TEXAS fault MMU and REQ status registers, BIF_MMU_STATUS, and `0xb50`/`0xb54`. Read them at h11, right after alive, 1 s later and after the kick. t4 gives the decode. A fault with an address confirms rank 1 and names the page to map.
2. **X2:** map a zero page at GPU VA 0, as Orchard's A8 does.
3. **X3:** map the faulting address that X1 reports.
4. **X4:** clear EVENT_STATUS bit 9 with an EVENT_CLEAR write (diagnostic).
5. **X5:** upstream's garten config, only if X1 implicates it.

If everything comes back negative, the remaining cause (rank 4) isn't host-visible. Progress would then need an iOS-side register snapshot or Orchard-level A8X work, not more host experiments.

## Not resolved

- When EVENT_STATUS bit 9 was first set: before META's release or after alive. X1 answers it.
- The requester and address of the fault.

## Files

- `t1-hypotheses.tsv`: Q1, the seven ranked hypotheses.
- `t2-a8-a8x-a9.tsv`: Q2, the A8, A8X and A9 differences.
- `t3-after-alive.tsv`: Q3, Orchard's after-alive steps against ours.
- `t4-next-boots.tsv`: Q4, the ranked boots with exact registers and decodes.
- `SHA256SUMS`.
