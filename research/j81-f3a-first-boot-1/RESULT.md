# Research request 14 result: what is wrong or missing in the first-boot firmware image (J81, 19H394)

Offline analysis of the same stock iPadOS 15.8.5 (19H394) J81 kernelcache as requests 6–13 (sha256 `c3507666…a0008`, AGXG4G), request 4's LDR tables, the run-49 addendum, and the builder in `context/`. META register names come from upstream Linux:
- `drivers/gpu/drm/imagination/pvr_rogue_meta.h` (current master);
- `arch/metag/include/asm/metag_regs.h` (v4.16, kernel.org).

Addresses drop the `0xfffffff0` prefix. Tags:
- **code**: read from the disassembly;
- **source**: upstream source;
- **capture**: the run log or the addendum;
- **inferred**.

No device was used. There is no Apple binary content beyond addresses, offsets, short mnemonics, field names and the constants the questions ask for.

## Short answer

1. **META did run, then halted on a memory fault** (Q8). T0STATUS `0x005e0008` decodes to:
   - MAJOR_HALT = 3: memory-interface fault;
   - MEM_FAULT = 1: a general fault, not a page fault or read-only fault;
   - CBMARKER: the catch registers hold the failed access;
   - PSTAT: privileged.

   T0ENABLE shows the thread off because it halted. A BIF fault of 0 fits an access that never went through the GPU MMU, for example an address outside every META segment. The SoC never died (run 48).
2. **Config `+0x2f0` must not be zero.** The host fills it from the LDR START_THREADS record (thread 1, two words swapped, `0x6690050`–`0x669008c` → fw `+0xb48` → `0x668fa34`): **`0x8000b3c8_20000000`**, i.e. thread 1's PC `0x20000000` and SP `0x8000b3c8` from request 4's `ldr-records.tsv`. It is the only start information the host passes to the firmware. Leaving it zero is the first concrete error in the image.
3. **The MMIO window table is now decoded (t2).** Apple's own slot names, in order:
   - FenderRegs (`0x5000`);
   - AICTimerRegs (`0x20e101000`, one page);
   - AICSWIntRegs (the AIC SW_SET page; `+0x2e4 = 0x10`, `+0x2e8 = 0x400` for IRQ 138);
   - RGXRegs (`0x20000`, never mapped, fwaddr 0);
   - optional UVDRegs;
   - four empty slots.

   Fender and the AIC pages are mapped in GPU-MMU partition 9 (VA `0xe1c4200000`), so their fwaddrs are `0xc42xxxxx`. An all-zero table means the firmware's first Fender or AIC access goes to address 0.
4. **Most of the remaining guesses are right or harmless** (t1):
   - Config `+0x00..+0x2f` = `0x5_0000_0000`, `0x6_0000_0000`, `0x1_0000_0000` ×2, `0x3_0000_0000` ×2, exactly the builder's values.
   - The block sizes are 16, 32, 32 and 64 bytes. Accel slot `0x990` = 16 and slot `0x760` = 8 contexts. The builder's 4 KiB zeroed blocks cover them.

The next boot should read the catch registers, at no extra risk (M1). Then fix `+0x2f0` (C1), then the window table (C2).

## Findings

**Q1, located (code)** (t1):
- `+0x00..+0x2f` come from a 16-byte constant plus two immediates (`0x66898d0`–`0x66898e8`).
- These stay 0 at first boot unless their source objects exist:
  - `+0x30` (the accel `+0x1828` object's VA);
  - `+0x1b8` and `+0x2f8` (accel slots `0x920`/`0x928`, which return the objects at `+0x1c18`/`+0x1c20` only when present);
  - `+0x290`/`+0x298` (accel `+0xd38`/`+0xd44`, values not resolved).
- `+0x38..+0x1b7` is copied from accel `+0x18f0` and from the MMU format descriptor at `+0x19b0`. Contents not decoded; leave 0 until the fault address points there.
- `+0x2f0` is described above.

**Q2, located (code)** (t2):
- The table source is accel `+0xed0 + 0x18·i` = `{phys, size, name}`, filled at `0x66719b8`–`0x6671a88`.
- The mapping loop (`0x668f3bc`–`0x668f4ac`) maps every entry with phys ≠ 0 and size ≠ 0, **except index 3 (RGX)**:
  1. builds a physical descriptor;
  2. creates the GPU mapping with options `0x90007` (partition 9);
  3. stores the page offset at fw `+0xb10 + 4i`.
- The table's fwaddr field is then the translator applied to (mapping VA + page offset). The translator (`0x6691704`) gives region `0xc0000000` for partition 9.
- The VA order within partition 9 (Fender first, then the AIC pages) is inferred from allocation order.
- Window 2's physical page comes from accel `+0x1ba8`. Its value, `0x20e104010`, is inferred from `+0x2e4 = 0x10` and the IRQ-138 bit mask `0x400` (138 = 4·32 + 10).
- Whether UVDRegs is present on J81 is not resolved.

**Q3, partly located (code).** The table formats are as already built:
- PC = `((PD >> 12) << 4) | 1`;
- PD = `PT | page-size(0) | 1`;
- 4 KiB pages.

PT flags come from MMU slot `0x180` (`0x669dce4`): valid, plus `a & 0xc` (upstream: bit 2 cache-coherent, bit 3 SLC bypass), plus `a` bit 0 → read-only (bit 1), plus `a` bit 4 → PM/META protect (bit 62). How the map option value 7 (used for both the heap `0x60007` and the windows `0x90007`) becomes `a` was not traced. Valid-only did not cause a BIF fault in run 49.

The host writes no BIF/MMU control register before META starts. Only `BIF_CAT_BASE0` goes through the stream; `BIF_CTRL` is written only on power-down (request 4).

**Q4, located (code).** Accel slot `0x760` = 8 (system contexts) and slot `0x990` = 16.
- fw `+0x218` block: 16 B.
- fw `+0x3e0`/`+0x3f8` blocks: 4 × 8 = 32 B (`0x66886d4`).
- fw `+0x3e8`/`+0x400` blocks: 32 B.
- fw `+0x3c8`/`+0x3d0` blocks: 8 × 8 = 64 B (`0x66888fc`).

All are zero at first boot except the TAILQ heads listed in request 4.

**Q5–Q6, partly located.**
- With META_BOOT master boot, thread 0 starts by itself at reset release from META VA `0x40000000` (seg2 at buffer `+0`). The host never writes TXENABLE (source; code).
- The bootloader applies the boot list at `+0x200`: segments 0/1/3, then the 27 cache/JTAG writes. Segment 2 is never reprogrammed (`0x66947cc` returns for n == 2).
- It then needs the firmware entry (inferred: thread 1 from `+0x2f0`) and later the window table.
- The general fault with a zero BIF fault means META touched an address no segment covers, or a bus target returned an error. Address 0, from a zero `+0x2f0` or a zero window fwaddr, fits both (inferred).
- The catch registers settle which one. The SoC-death question is answered by run 48: it was the runner's own watchdog.

**Q8–Q10** (t3):
- **Q8:** the TXSTATUS decode is above.
- **Q9:** thread 0 starts by itself under master boot. "Booted and idle" means TXENABLE bit 0 set with no halt bits, plus the type-0 alive record carrying the META idle PC. SEG2 = `0x40000f02`/`0x1ffff000` is expected to stay as it is.
- **Q10:** the reads to add, all safe with T0 halted:
  - TXCATCH0..3 (`0x04800080`/`88`/`90`/`98`);
  - TXDEFR (`0x048000a0`) and TXPRIVEXT (`0x048000e8`);
  - T0 PC through the core-register port (`0x0480fff8` ← `0x00010005`, poll bit 31, read `0x0480fff0`);
  - MMCU segment 0/1/3 registers (`0x04850000`–`0x0485003c`);
  - SEG2 OUTA0/OUTA1.

## Q7: next boots (one change each)

Full table in t4.
1. **M1:** run 49 unchanged, plus the reads above. This shows the exact faulting address, and whether the bootloader finished its list.
2. **C1:** config `+0x2f0 = 0x8000b3c8_20000000`.
3. **C2:** map Fender, the AIC timer and the AIC SW-int pages in partition 9 and fill table entries 0–3 per t2.
4. **S:** Apple's stop procedure, needed only once META runs past its first fault.

## Not resolved

- The attribute behind map option 7, i.e. the exact PT flags for heap and MMIO pages.
- What accel `+0x1ba8` holds (inferred `0x20e104010`) and whether UVDRegs exists on J81.
- The contents of `+0x38..+0x1b7` and the other optional config fields.
- What the bootloader does with `+0x2f0`. Inferred; M1 and C1 test it.

## Files

- `t1-config.tsv`: Q1, every config field with its first-boot value, source and code address.
- `t2-mmio-windows.tsv`: Q2/Q3, the window table you can paste, plus the translator and PT-flag rule.
- `t3-meta.tsv`: Q8–Q10, the META register decode and the next reads.
- `t4-next-boots.tsv`: Q7, the ranked boots.
- `SHA256SUMS`.
