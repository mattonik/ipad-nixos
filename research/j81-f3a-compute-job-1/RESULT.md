# Research request 30 result: the first compute job on J81 (19H394)

Sources:
- the 19H394 AGXG4G kext;
- the decoded META firmware (private, provisional);
- Orchard's public A9/A8 driver, `pvr_apple_s8003.c` at OrchardLinux/linux `059fadee` ("S:n"), read on GitHub;
- Orchard's notes of 2026-11-27.

Tags: **code**, **fwdis**, **orchard**, **capture**, **inferred**. There is no Apple binary content beyond addresses, offsets, field names and small constants.

## Short answer

- **Ring and entry, confirmed in Apple's J81 kext and the firmware** (t1):
  - Compute goes on the **CL lane**, root `+0x10`/`+0x14` (our `0x46000`/`0x47000`).
  - The entry is 20 bytes, `{2, channel fwaddr, end, 0, 0}`. That's Apple's `submitCLChannel` (`0x6691150`) with its enqueue at `0x668a884`, and Orchard's `{engine, channel, end}`.
  - The firmware's reader checks type 2 and hands the channel and `end` to the compute scheduler block, root `+0x6c` (the `0x8c0` block).
  - **The doorbell is `0xb00 = 0x12`** (counted, DM2), the J81 kext's own value. Orchard's A9 rides the geometry doorbell instead.
- **Channel page and record: follow Orchard's A9 path.** Our 19H394 firmware has the A9's object sizes (Orchard notes section 1).
  - **Channel page** (t2): one 4 KiB page in the heap. Header, watermarks at `+0x100`, a 16-entry pointer ring at `+0x200`, the record at `+0x400`, the microsequence at `+0x800`, TQ at `+0x900`, finish stamps at `+0x940`, the dependency object at `+0x980`.
  - **Record:** t3 has every field Orchard's `s8003_submit_compute` writes.
  - **Microsequence:** t4 has its words.
  - **Completion:** both stamps reach `seq` and the watermarks reach `end`.
- **Open for 19H394:**
  - the record size: A9 `0x290` is the likelier, inferred;
  - the compute terminate word: A9 `0x00a00004` or A8 `0x00900004`;
  - the A8X cluster-mask word (`W+0x20 = 0xff` on 16G77);
  - the microsequence opcodes.

  The 19H394 record builder and the firmware's microsequence dispatcher weren't traced.
- **First boot J0 (t6) tests the plumbing without running anything.** Initialise a compute channel page, queue a CL entry with `end = 0`, and kick `0x12`. If the CL consumer moves, the lane, the channel address and the DM2 doorbell all work. J1, the empty job, follows.

## Q1: channel and ring (t1)

- Apple's J81 functions:
  - `submitCLChannel` (`0x6691150`) does the enqueue, `dmb`, the Fender `+0x14` acknowledge, the state check, then `0xb00 = 0x12`;
  - the enqueue (`0x668a884`) writes the entry, `dmb`, producer + 1.
- The firmware reader is at `0x10002cd8`–`0x10002d08` and calls `0x10004d64`.
- Pointers are firmware addresses: `0xc0000000` + heap offset.

## Q2: the record (t3) and microsequence (t4)

- **The record:** the fields of Orchard's A9 path, with the J81 status of each.
- **The CDM control stream:** for an empty job it is only a terminate, with Mesa's fence-terminate PDS program.
- **A one-word kernel:** a PDS-only program with a single store.
- **Pointer formats:** the record's pointers into the channel are firmware addresses; the control stream and the PDS programs are GPU VAs in the job's VM.

## Q3: the VM (t5)

- Compute uses the VM's geometry slot. Use slot 1, which is loaded with our catalogue.
- One VM for everything works for a first job.
- The job VM must map the control stream, the PDS heap (Orchard A8: `0x3_0000_0000`), the hardware objects at `0x8_00000000` and a zero page at VA 0.
- The page-table format is the same as the firmware's.

## Q4: doorbell and completion

- **Doorbell:** `0x12` (code).
- **Completion:**
  - poll the channel stamps at `+0x940`/`+0x944` and the watermarks at `+0x100`–`+0x140`;
  - IRQ 138 is optional (polling works);
  - Orchard times a job out at 5 s.
- **A bad record:** it most likely shows as a BIF fault, bank 0 (the CDM), or as a firmware stall, rather than a SoC hang (inferred).

## Q5: boots (t6)

1. **J0:** plumbing only.
2. **J1:** the empty job.
3. **J2:** the J81 record words: the terminate word, then the cluster mask.
4. **J3:** the one-word kernel.

Each boot reads the fault registers `0x130`/`0x12c0`/`0x12c8`, the event ring and the log ring.

## Not resolved

- 19H394's compute record builder, its size and its J81-specific words.
- The firmware's microsequence opcode table.

Decoding those two is worth doing before J1.

## Files

- `t1-cl-path.tsv`: Q1, the CL lane end to end in Apple's host and the firmware, against Orchard.
- `t2-channel-page.tsv`: Q1/Q5, the compute channel page layout and its placement.
- `t3-record.tsv`: Q2, the record fields and their J81 status.
- `t4-useq.tsv`: Q2, the A9 microsequence words.
- `t5-vm.tsv`: Q3, the job's VM.
- `t6-next-boots.tsv`: Q5, the ranked boots.
- `SHA256SUMS`.
