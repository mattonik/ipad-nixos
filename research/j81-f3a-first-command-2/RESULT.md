# Research request 20 result: why the first device-control command (run 69) is ignored (J81, 19H394)

Sources:
- the 19H394 AGXG4G kext (J81 host);
- Orchard's reconstructed `pvr_apple_s8003.c` (request 9's pin; "S:n" = its line n);
- upstream `pvr_rogue_cr_defs.h` and `pvr_mmu.c` for MTS register names;
- the run-69 notes in `context/`.

Tags: **code** (the J81 kext), **orchard**, **source** (upstream), **capture**, **inferred**. There is no Apple binary content beyond addresses, offsets, field names and small constants.

The firmware is still MiniM and can't be decoded (request 16), so anything about what the idle loop itself does is inferred from the host side and from the run state.

## Short answer

- **Run 69's host side is Apple's, write for write.** Apple's `submitDeviceControl` (`0x66914dc`) does exactly what run 69 did:
  - write the entry, `dmb`, advance the producer, `dmb`;
  - Fender `+0x14 = 7`, read the GPC state;
  - RGX `0xb00 = 0x10` (MTS_SCHEDULE, TASK_COUNTED, DM0).

  `0x10` is the right kick for the DC ring; it is the same value as TA.
- **The host writes nothing else to wake the firmware.** On any ring there is no META software interrupt, no AIC write, no MTS association, enable or interrupt-enable register, and no thread start (t1). So the missing piece is not a host register write.
- **The firmware is not running its scheduler periodically.** Orchard sees an alive record on every scheduler run, about 290 a second on the A9 (S:213). We see one, and the write index stays at 1. So thread 0 parks in "waiting for BG kick" at `0x80009c14`, and the kick does not reach it, or reaches it and is not run (inferred).
- **Where a kick can get lost is inside the MTS**, in state the firmware programs itself (upstream: the host clears it at firmware stop, so the firmware sets it at start):
  - SCHEDULE_ENABLE (`0xbc8`) may mask DM0;
  - DM0 may be associated with thread 1 only (`0xb30`/`0xb38`), and our thread 1 never runs;
  - the counted schedule (`0xba8`) shows whether the kick is pending.

  These are plain RGX reads, safe in state 1. **M1 reads them** and tells "never delivered", "delivered but not run" and "run and rejected" apart (t4).

## Q1: what wakes ring processing (t1)

Per ring, Apple's host writes only the doorbell: Fender `+0x14 = 7` and then MTS_SCHEDULE:

| Ring | MTS_SCHEDULE |
|---|---|
| TA | `0x10` |
| 3D | `0x11` |
| CL | `0x12` |
| device control | `0x10` |

The value is a constant per ring (TASK_COUNTED | DM n), not computed from the entry. In state 0 the host does SNOOP checks or a restart instead of the kick (request 17). The only MTS-related string in the kext is the warning about writing MTS_SCHEDULE without SNOOP set. The kext never reads or writes `0xb30`–`0xbc8`; the hits in that range are firmware-object fields.

Whether the idle loop polls on a tick or sleeps until the MTS wakes it can't be read from MiniM. One alive record against Orchard's ~290 a second says it is not ticking on J81 (inferred).

## Q2: thread 1 and timers

- **The host never starts thread 1** on J81. It only passes `{pc, sp}` in config `+0x2f0` (from the LDR START_THREADS record). Orchard's A9 path does the same and its firmware runs, so on a healthy boot the firmware starts thread 1 itself (code; orchard).
- **Between state 1 and the first command, Apple's host writes nothing:** bootFirmware requests state 1, waits for alive, and the next host action is the first command's doorbell (`0x6690384`–`0x669039c`).
- **There is no Fender or MTS route to start a META thread.** The only route is the slave port. The DM-to-thread association (`0xb30`/`0xb38`) at least shows whether thread 1 matters for DM0.
- **Runs 61–64** (thread 1 started by hand) are void, because their events were trapped in the SLC (request 18). Thread 1 is untested under the E1 page flags.
- **The model-slow / agf_timer fields** (config `+0x25c`, `+0x274`) follow ADT `model-slow`, which J81 lacks. Our 0 and 1 are right (`0x6683548`–`0x6683588`).

## Q3: ring encoding (t3)

Confirmed against Apple's code:
- consumer at control `+0x00` (firmware), producer at `+0x10` (host);
- both count entries, 256 entries, wrap `& 0xff`, stride 20 bytes;
- no size or mask field in root, state or control. The firmware knows the sizes, so nothing was left zero.

`{8, 0, 0, 0, 0}` is Apple's own template for PerfCtrSamplerCommitCounterList (`0x57c339c`). Its payload is found through state `+0x40` with the count in state `+0x1020`, not through the argument. So type 8 with argument 0 is a valid first command.

## Q4: preconditions (t3)

- **No host-ready, init-done or power-handshake word** is written after alive. The host's only gates are its own alive flag and the GPC state, which run 69 met.
- POLICY, the perf table and the hardware objects are image inputs, all in blob f.
- The log ring (root `+0x28`) is not enabled by any host write found.
- The AIC SW-int page is for the firmware's use. Apple's host never writes it to kick.

## On the slave-port stall

MSLVCTRL1 `0x06000040` has both idle bits set and READY clear: a request is pending inside META. Under PM/META protect, the firmware's pages refuse requesters other than META (upstream `pvr_mmu.c`). A slave-port memory read of such a page may never complete (inferred). So M2 checks whether control-register reads alone still work, before any thread-1 attempt.

## Q5: next boots (t4)

1. **M1 (read-only MTS):** run 69 unchanged. Read RGX `0xb30`, `0xb38`, `0xb40`, `0xb48`, `0xb50`, `0xb58`, `0xb98`, `0xba0`, `0xba8`, `0xbb0` and `0xbc8` after alive, then again 10 ms after the kick. Interpret:
   - `0xbc8` bit 0 clear → DM0 is masked: never delivered.
   - DM0 set only in `0xb38` (thread 1) → it needs thread 1: go to M3.
   - `0xba8` bits 7:0 rise and stay → delivered, not run.
   - Count falls but the DC consumer stays 0 → run and rejected. Then read the log ring at root `+0x28`.
2. **M2 (META control reads only):** before any other slave-port access, read T0 TXSTATUS (`0x04800010`) and T1ENABLE (`0x04801000`). No memory addresses. Record MSLVCTRL1 before and after.
3. **M3 (thread 1),** only if M1 points at thread 1 and M2 shows the port usable:
   - Thread 1 PC = `0x20000000`: TXUXXRXDT, then TXUXXRXRQ = `0x00001005`.
   - SP = `0x8000b3c8`: RQ = `0x00001003` (A0StP).
   - Then T1ENABLE bit 0, then the DC kick again.

   Success means the DC consumer moves to 1 and alive records keep arriving.

In every boot, keep draining the event ring. **"Never woken"** shows as no change in `0xba8`, the event write index or T0's PC. **"Woken, rejected"** shows as the count consumed and the consumer unchanged, possibly with a non-alive event or a log entry.

## Not resolved

- The idle loop's own wait mechanism: tick or MTS-driven (needs MiniM).
- Which MTS values the firmware programs on a good boot. M1 gives J81's, but there is no reference capture to compare against.
- Whether the slave-port stall is the protect flags or META being clock-gated.

## Files

- `t1-doorbell.tsv`: Q1, every host wake write per ring, with code addresses.
- `t2-mts-reads.tsv`: Q1/Q5, the MTS registers for M1 and what each shows.
- `t3-findings.tsv`: Q2–Q4, the encoding, thread-1, timer and precondition findings.
- `t4-next-boots.tsv`: Q5, the ranked boots with exact values.
- `SHA256SUMS`.
