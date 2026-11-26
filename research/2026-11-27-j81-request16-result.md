# Research request 16 result (partial): the MiniM firmware around the polled PCs (J81, 19H394)

Offline analysis of the locally laid-out 19H394 META firmware image (private, not reproduced), the AGXG4G and AppleInterruptController kexts, the captured ADT, and the run-57/58 addendum.

Tags:
- **code**: host kext disassembly;
- **LDR**: the firmware's load records and image words;
- **adt**;
- **capture**;
- **inferred**.

There is no Apple binary content beyond addresses, offsets, field names and small data values.

## Q1: no MiniM decoder is possible from public material

There is no public MiniM specification or tool:
- binutils' META port (2.30, the last with `metag`) has none: `opcodes/metag-dis.c` and `include/opcode/metag.h` have no MiniM code.
- Web searches turn up only classic-META material: binutils, a Ghidra plugin and Wikipedia.

Classic decoding gives garbage on seg0 and on the 0x38-byte block at META `0xc0000000`. Reverse-engineering a compressed ISA from one stripped image, with no strings and no known reference code, is not something I can do reliably here. So there is **no listing** of the routines at `0x10000260`, `0x1000034c..36c`, `0x10016a18..a68`, `0x100228d0..291c` or `0x1000b4e8`. Q2 and Q3 can't be answered from code. What the data settles is below (t1), along with hardware reads that answer Q2 without a decoder (t2).

## What the data settles

- **No absolute MMIO constants in the code.** No 32-bit literal for any window address (`0xc4200000`, `0xc4205000`, `0xc4206000`) appears in seg0, seg1 or coremem. The firmware takes the window addresses from the config table at run time (LDR; inferred).
- **Globals.** A1GbP = `0x10013c00` (run 57) is the start of the initialised data block, which holds the three words from request 15. `0x10013c54..0x10013dab` is a pointer table: `[GbP+0x64] = 0x8000a000` and `[GbP+0x78] = 0x10016358` (LDR).
- **Q6, the structure at `0x8000a000`.** It lies in a zeroed block (`0x8000a000` + `0x3c8`), so the firmware wrote all of it:
  - `+0x00` = 1 (a flag);
  - `+0x0c` = `0x10016358` (the same pointer as `[GbP+0x78]`);
  - `+0x1c..` = `0xe200, 0xe208, … 0xe240` (nine entries, stride 8).

  Those values are **RGX register offsets**. Apple's host failure dump walks 32 slots at RGX `0xe100 + 8i` and `0xe200 + 8i`, tests bit 0 (valid), prints bits 31:1 as "PC" and logs "Found USC Exception" (`0x669a4e0`–`0x669a578`, code). So the firmware has built a list of the first nine per-slot USC exception/state registers, plus a handler pointer (inferred: USC exception or pipe-state setup during init).
- **Q5, PC `0x80009c74`.** This is outside the loaded coremem code (`0x80000080`–`0x80005334`) and below the thread-0 stack block, and the reads there are noise. Without the decoder it can't be settled whether this is a racy core-register-port read on a running thread, an interrupt or trap context PC, or a code/data alias. A halted snapshot (H1) settles it.
- **A candidate for the wait: the AIC timebase.** Window 1, which Apple calls "AICTimerRegs" (`0x20e101000`), is the ADT node `aic-timebase` (one page). The AppleInterruptController kext never touches that page (no access in `0x1000`–`0x1fff`, by search), so on iOS something outside the kernel (iBoot or hardware) brings it up. On this boot it reads 0 at words 0 and 1. A firmware delay or timeout built on a stopped timebase would loop forever without writing memory, which matches the "polling, no writes" signature. This is inferred, and T1 below tests it.

## Next boots (t2)

1. **T1 (read-only):** read the whole timebase page twice, 1 ms apart. If every word stays static, the timebase is stopped. In that case its enable has to be found; I haven't decoded it, and blind writes there aren't safe.
2. **U1:** with the firmware running in state 1, read RGX `0xe100`–`0xe1f8` and `0xe200`–`0xe2f8`. A slot with bit 0 set means a USC exception or an occupied slot the firmware is waiting on.
3. **H1:** at the end of a run, stop thread 0 (Apple's `0xfffffffe` write to T0 TXENABLE, using the slave-port recipe from request 15) and read PC, PCX and D0/D1/A0/A1. That gives one consistent snapshot instead of racy samples.
4. **P4:** take PC samples together with the D/A registers. In run 57, D0.1/D1.5/D1.6 = `0x8000a000` and D1.4 = `0x100103a8` are the candidates for the polled location.

## Not resolved

- The MiniM encoding, and with it every code-level question in Q1–Q3.
- The timebase enable.
- The meaning of `0x10013c08..0x10013c18` beyond request 15's reading.

## Files

- `t1-findings.tsv`: what the data settles, with sources.
- `t2-next-boots.tsv`: the ranked boots.
- `SHA256SUMS`.
