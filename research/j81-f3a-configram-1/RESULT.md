# Research request 25 result: Apple's full Fender ConfigRAM list on J81 (19H394)

Sources: the 19H394 AGXG4G kext, the decoded META firmware (private, provisional), our layout tool in `context/tools`, and the run notes.

Tags: **code**, **fwdis**, **capture**, **inferred**. There is no Apple binary content beyond addresses, offsets, field names and small constants.

## Short answer

- **Our 31-word ConfigRAM list is Apple's, word for word** (t1):
  - nine entries: three SOFT_RESET asserts, META_BOOT, BIF_CAT_BASE0, the SLC pair and the SOFT_RESET release;
  - the terminator;
  - all built by the hardware-start function (fw vtable `+0xe0`, `0x6690bbc`) and two accelerator helpers.

  No other code writes ConfigRAM.
- **Request 24 was wrong: there are no "12 computed entries"** (t3). Those were vtable-slot `+0x1e8` calls on registry and dictionary objects, not ConfigRAM writes.
- **No entry touches the MTS, the slave port or META's interrupt path.** The only META entry is META_BOOT = 1. The firmware doesn't read any of these registers back. So the trigger problem isn't in ConfigRAM, and there's nothing to append.
- **One host step in the same builder sits outside ConfigRAM:** `enableGPCHostInterrupts(3)` writes Fender `+0x10` (TIMER_POWER_INT_ENABLE) = 0. Please check that our sequence matches. It's unlikely to matter for the MTS (inferred).

## Q1: the complete list (t1) and the encoding (t2)

- **32-bit entry:** `0x00FF0000 | reg`, then the value.
- **64-bit entry:** `reg + 4`, the high half, `0x00FF0000 | reg`, the low half.
- **Cursor and terminator:** the cursor starts at Fender `+0x10000` and steps 4 bytes per word. The terminator `0xFFFF0000` is written at the cursor.
- **Mode:** the writers go to ConfigRAM only when the global flag `0x7a4d882` bit 1 is set; otherwise they go straight to RGX.

## Q2/Q3: the computed entries

There are none. The only run-time value is BIF_CAT_BASE0, our page catalogue. Everything else is a constant for J81.

## Q4: does the firmware depend on them?

No. Of these registers the firmware only writes the SLC flush (`0x3818`); it never reads SOFT_RESET, META_BOOT, BIF_CAT_BASE0 or the SLC pair back.

## Q5: next boots (t4)

There are no ConfigRAM additions. The list region has room for 16,384 words (`+0x10000` up to the override at `+0x20000`); we use 31.

The remaining host differences from iOS:
1. **F1:** Fender `+0x10 = 0`, only if we don't already write it.
2. **N3:** CONTROL `+0x20 = 1`, iOS's idle-power-off word.
3. **S2:** the `0xac8` bit 2 liveness check around the kick.

## Files

- `t1-configram-list.tsv`: Q1, Apple's list in order, compared with ours, plus the builder's non-ConfigRAM steps.
- `t2-encoding.tsv`: Q1, the entry encoding, cursor, terminator, writer modes and room.
- `t3-findings.tsv`: Q2–Q4, the correction and the conclusions.
- `t4-next-boots.tsv`: Q5, the ranked boots.
- `SHA256SUMS`.
