# Research request 17 result: the idle loop at 0x10000358, and what is missing for the alive record (J81, 19H394)

Offline analysis of the 19H394 AGXG4G kext (host side), upstream `pvr_rogue_cr_defs.h` for MTS field names, and the run-60 halted snapshot.

Tags:
- **code**: host kext disassembly;
- **source**: upstream;
- **capture**: run logs and builder;
- **inferred**.

The firmware code is MiniM and still can't be decoded (request 16), so the firmware-side statements are inferred from the host's view of the firmware's data structures.

## Short answer

- **Thread 0 has finished init and is in the scheduler's idle loop.**
  - The halted snapshot's D1.5 = fwaddr `0xc002978c` = heap `0x2978c`, which is offset `+0x78c` in the `0x8e0` block.
  - The host names that block (CPU fw `+0x1f8`) in its debug dump as the firmware **scheduler**: KickSlot entries, LockupState, SKUEncoder fields, "inflight_commands_perlevel", a 32-entry channel table at `+0x80c`, and per-priority "enqueued_commands" at `+0x78c + 4·prio` (`0x6677b44`–`0x6677c4c`, code).
  - So thread 0 is polling the priority-0 queue count, with PC stable at `0x10000358` and no writes. That is the idle "waiting for BG kick" state whose PC the alive record should report (inferred, strong).
- **The event ring layout is not the problem.** In Apple's layout:
  - root `+0x20` = event control, root `+0x24` = event buffer;
  - control `+0x0` = read index (host), `+0x10` = write index (firmware);
  - 256 records of `0x2c` bytes; type 0 → alive.

  The builder matches all of it (t1, code). I first suspected `+0x30`/`+0x34`, but the CPU↔address pairing (`+0x40`) settles it as `+0x20`/`+0x24`.
- **On iOS the alive record needs no host action.** bootFirmware releases, requests state 1 and waits. Every doorbell waits for alive before kicking. So the firmware posts alive on its own (code).
- **The one firmware-side difference left in view is thread 1,** which never started (T1ENABLE `0x0201c132`). The host never starts it; it only passes `{pc, sp}` in config `+0x2f0`. If thread 1 posts the record, or thread 0 posts it only after thread 1 is running, that explains the gap (inferred). R1 reads thread 1's state; K1 tries one kick.

## Findings

**Q1 (code).** The host uses the idle PC only in its debug dump: "T0 PC 0x%08X (PC of waiting for BG kick = 0x%08X)" (`0x6691b40`) prints the live T0 PC next to fw `+0xb38`, which the alive handler sets from record word `+4` (`0x6694048`). There is no check or expected constant. The host has no META or MiniM disassembler; its failure dump prints raw registers only.

From the snapshot and the scheduler identification, `0x10000358` fits an idle loop. Without decoding, I can't confirm one wait instruction and one backward branch.

**Q2 (code).** Between META start and `waitForFWAlive`, Apple's host does only accel `0x8a8 (1)`, which unmasks AIC lines `0x86`/`0x87`/`0x8a` and enables events. There is no MTS write, no Fender `+0x10` enable and no state-block update. The record is written to memory before the IRQ-138 doorbell, so the AIC unmask can't gate it.

**Q3 (code).** `+0x78c` is `enqueued_commands[0]` in the firmware scheduler block. In normal operation the host's enqueue path (`0x668a570`, inside the doorbell) fills the scheduler and channel structures before the kick (inferred from the dump field names). `+0x778 = 0xffffffff` is written by the host at init (`0x6689460`); its name is not decoded.

**Q4 (code; source)** (t2). The kick sequence:
1. Check alive: if fw `+0xb35` is clear, call `waitForFWAlive` first.
2. Enqueue (`0x668a570`), then `dmb ish`.
3. Fender `+0x14` = 7.
4. State check.
5. RGX `0xb00` = **`0x10`**, i.e. MTS_SCHEDULE TASK_COUNTED, DM0, context 0, priority 0.

Apple never sends this before alive. With empty queues, a kick should take the firmware through one background pass and back to idle (inferred). If a type-0 record then appears, alive is deferred to the first kick on this setup.

## Next boots (t3)

1. **R1, read-only:** read thread 1's PC (core-register port value `0x00011005`), T1ENABLE and T1STATUS. This shows whether thread 1 ever ran.
2. **K1:** after 5 s idle, Fender `+0x14 = 7`, then a single write of RGX `0xb00 = 0x10`. Then read the event write index, the heap diff, T0 PC and T1ENABLE.
3. **Config fields** (`+0x30`/`+0x1b8`/`+0x2f8`): these are 0 on iOS too when their source objects are absent. They are low priority until code shows they are read.
4. **AIC IRQ 138 unmask:** not needed for posting the record.

## Not resolved

- Who starts thread 1, and whether it posts alive. This needs the MiniM code.
- The name of scheduler `+0x778`.
- The exact loop structure at `0x10000358`.

## Files

- `t1-findings.tsv`: Q1–Q3, the host-side identifications with code addresses.
- `t2-kick.tsv`: Q4, Apple's doorbell and kick sequence.
- `t3-next-boots.tsv`: Q5, the ranked boots.
- `SHA256SUMS`.
