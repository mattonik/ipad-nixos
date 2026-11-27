# Research request 29 result: the bank-1 BIF fault on a mapped page (J81, 19H394)

Sources:
- upstream `pvr_rogue_cr_defs.h` / `pvr_rogue_meta.h` / `pvr_fw_startstop.c`;
- the decoded META firmware (private, provisional);
- the 19H394 kext;
- the boot list;
- runs 81/82.

Tags: **source**, **fwdis**, **code**, **capture**, **inferred**. There is no Apple binary content beyond addresses, offsets, field names and small constants.

## Short answer

- **The fault (t1):** a single instruction-fetch READ by META thread 0 at GPU VA `0xe1c000df80`, a 64-byte code line in seg0, in context 0. It is latched from META's release (h11) onward, before alive.
  - TAG_ID 3 / TAG_SB 1 decodes as META thread 0's ICache. That comes from IMG's DDK debug table, quoted from memory, so it's unverified.
  - The MMU isn't stalled (BIF_MMU_STATUS = 0), and the firmware runs on to alive afterwards.
  - The likeliest cause is a fetch at release that raced the MMU taking the catalogue, or hit stale MMU state from before the power cycle (t3, rank 1).
- **META uses CAT_BASE0** (t2). The boot-list segment word `0x7e1` decodes, through upstream's classic-BIF macro, to page catalogue 0 and BIF DM 7, and META isn't one of CAT_BASE_INDEX's requesters.
  - `0x1200` is the right offset: 64-bit, ADDR in bits 39:12, as upstream and Orchard's A8 have it.
  - That it reads 0 is most likely a filtered host view, like `0x3808` reading 0 after a write of 1, and `0xbc8`/`0xb08` ignoring host writes (inferred).
  - The heap works, so the catalogue is in effect.
- **The fault probably doesn't explain the stall, but it adds a fact** (t4). The pending event never became an MTS interrupt-context task for DM4 (`0xb98 = 0`, `0xbb0 = 0`), although the firmware enabled it (`0xb78 = 0x200`). So *neither* interrupt nor background work reaches META. The delivery side of the MTS, or its link to META, is what fails.
- **E1 (t5) is a single low-risk write: clear the event with EVENT_CLEAR `0x138 = 0x200`,** the firmware's own value, then kick with the slave-port detector. If that changes nothing, the remaining cause is outside what the host can see. The next step would then be an iOS-side snapshot of `0xb10`, `0xb98`, `0xbb0` and `0x130` after alive.

## Q1: requester and context (t1, t2)

- META thread-0 ICache (TAG_ID 3, SB 1), in bank 1, context 0 (CAT_BASE0), BIF DM 7.
- Apple's host sets no other context for META. The firmware loads other catalogues only for user slots.

## Q2: CAT_BASE0 reads 0 (t2)

- The offset and encoding are right.
- The likely reason is a host-filtered read.
- No host-driven walk register exists to check it: BIF_MMU_ENTRY is the MMU's pending-entry status.

## Q3: causes of a read fault on a mapped page (t3)

Six causes ranked. A race or stale-cache fetch at release fits best. Protect rules, the 40-bit address and walker coherency fit poorly. A PT-entry check for page `0xd` (E2) rules out a per-page format error.

## Q4: does it explain the stall? (t4)

- **Probably not by itself:** no MMU stall, alive follows, and no interrupt task is pending in the MTS.
- **What the firmware does with the event:** its handler clears events (EVENT_CLEAR `0x138`). It never reads the bank registers; it invalidates MMU caches (BIF_CTRL_INVAL `0x12a0`).
- **A host clear is low risk.** It's informative unless the register is filtered for the host.

## Q5: next boots (t5)

1. **E1:** clear the event, then kick with the slave-port detector.
2. **E2:** check the PT entry for page `0xd` in the blob.
3. **E3:** add BIF_CTRL_INVAL `0x12a0 = 0xf` before the release, as a test of cause 1.

## Not resolved

- The exact IMG tag table for this core.
- Whether host reads of `0x1200`, `0x3808` and others are filtered or truly 0.
- The MTS-to-META delivery link itself.

## Files

- `t1-fault-decode.tsv`: Q1, the field-by-field decode of the fault and the related status registers.
- `t2-catalogue.tsv`: Q1/Q2, CAT_BASE0, the read-back and META's context.
- `t3-causes.tsv`: Q3, the ranked causes of a read fault on a mapped page.
- `t4-stall.tsv`: Q4, whether the fault explains the stall, and the clear.
- `t5-next-boots.tsv`: Q5, the ranked boots and the plain statement.
- `SHA256SUMS`.
