# Research request 15 result (partial): what the firmware waits for before the alive record (J81, 19H394)

Offline analysis of the 19H394 AGXG4G kext, the locally laid-out 19H394 META firmware image (request 4's tool; private, not reproduced) and the run notes in `context/`.

Tags:
- **code**: the host kext disassembly;
- **LDR**: the firmware image's own load records;
- **source**: upstream Linux PowerVR/META headers;
- **capture**: run 54;
- **inferred**.

There is no Apple binary content beyond addresses, offsets, short mnemonics, field names and small data values.

**This is a partial answer.** The firmware is META code, and no META disassembler is available on this machine. Capstone, llvm and Ghidra have no META support, and the image carries no strings. So Q1 (the init sequence and its waits), Q2's variable names, Q4 (which config fields the firmware reads) and Q5 (who starts thread 1) cannot be decoded from code here. What follows is what the host code, the LDR layout and the image's load values settle, plus a cheap way to locate the wait from hardware.

## Findings

**Q2, the three words, located against the image (LDR; capture)** (t1). All three sit in a 0x1c-byte initialised-data block at META `0x10013c00` (LDR record `0x2e9c`):

| Address | Load value | After run 54 |
|---|---|---|
| `0x10013c08` | `0x00000202` | `0x00000101` |
| `0x10013c10` | `0` | `1` |
| `0x10013c14` | `0xc` | `0xd` |
| `0x10013c18` | `0xc` | `0xc` (unchanged) |

So these are firmware variables initialised at load, not error codes written from scratch. The pair `0x10013c14`/`0x10013c18` reads like a producer index one ahead of its consumer: one item queued and not taken (inferred, low). Without the code this stays a reading, not a decode.

To sort the other 118 changed words:
- hits in seg0's initialised data (`0x10013bd8`–`0x10013c1b`, `0x10013c54`–`0x10013dab`, `0x10015dc0`–`0x10015e7f`, …) are variables;
- hits in the zeroed blocks (`0x10013dac` + `0x2014`, `0x10015e80` + `0x75c`, `0x10016710` + `0xc5c`, …) are stacks, queues or trace buffers.

**Q3, the host-side inputs, located (code)** (t2). Before `waitForFWAlive`, Apple's host gives the firmware nothing the runner lacks, except unmasking AIC lines `0x86`/`0x87`/`0x8a` (accel `0x8a8 (1)`):
- There is no MTS kick at boot.
- Fender host interrupts (`+0x10`) are left at 0.
- State 1 is reached.
- Thread 1 is not started by the host.

The alive record goes to memory before the IRQ-138 doorbell, and the event-ring write index is still 0. So the firmware is stuck before posting, not waiting on a doorbell acknowledge (inferred). The AIC timer page (window 1) is one input that could stall a firmware delay loop if its counter doesn't advance on this boot. P3 checks that read-only.

**Q5 (inferred).** The host never starts thread 1. It only passes `{pc, sp}` in config `+0x2f0`, so thread 0 must start it. Thread 1 still being off means thread 0 hasn't reached that point, or starts it only after alive.

**Q6, how to read thread 0's PC, located (code; source)** (t3).

Apple's slave-port write (stop path `0x6693f38`–`0x6694010`):
1. Poll RGX `0xa18` until bits `0x05000000` (READY, GBLPORT_IDLE) are set.
2. RGX `0xa10` = META address.
3. RGX `0xa08` = data.
4. Poll `0xa18` again.

The read protocol is upstream `pvr_meta_cr_read32`: `0xa10` = address | 1, fence, poll, read `0xa00`.

Thread 0 PC:
1. Write META `0x0480fff8` = `0x00010005`.
2. Read `0x0480fff8` until bit 31 is set.
3. Read META `0x0480fff0`.

Safe to read while thread 0 runs:
- TXENABLE/TXSTATUS/TXDEFR/TXTIMER (`0x04800020`)/TXCATCH0–3 for both threads;
- the MMCU segment registers.

Never write TXENABLE unless you mean to stop the thread (Apple's stop writes `0xfffffffe` there).

## Next boots

Full table in t4.
1. **P1:** run 54 unchanged. Read thread 0's PC three times, 100 ms apart, at 1 s and at 5 s, plus TXSTATUS/TXDEFR/TXTIMER. A constant PC or a short range is the wait loop.
2. **P2:** diff the heap at 1 s and at 5 s. This shows which words keep moving, i.e. polling counters versus settled state.
3. **P3:** read-only, read the AIC timer page twice, 1 ms apart.
4. Then map the PC and the changed words onto the firmware code with a META disassembler, and fill whichever field the wait reads.

## What is needed for the rest

A META disassembler. GNU binutils supported the `metag` target up to release 2.30; it was removed in 2.31. Building `objdump` for `metag-linux` from the 2.30 source would let me:
- decode the firmware's init path and every wait before the type-0 record (Q1);
- name the variables at `0x10013c08`–`0x10013c18` (Q2);
- list the config and root fields read before alive (Q4);
- find the thread-1 start (Q5).

The disassembly would stay local. Only addresses and short mnemonics would go into a reply.

## Files

- `t1-changed-words.tsv`: Q2, the three words against their load values, and the seg0 region map for classifying the rest.
- `t2-host-inputs.tsv`: Q3/Q5, each host-side input and whether Apple provides it before alive.
- `t3-meta-reads.tsv`: Q6, the slave-port protocols, the PC read sequence and the safe reads.
- `t4-next-boots.tsv`: the ranked boots.
- `SHA256SUMS`.
