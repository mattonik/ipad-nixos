# J81 GPU: stock path from core-ID to running META firmware (answers requests 5 and 7)

Offline static analysis, 2026-11-22. No device and no firmware execution. Inputs: the decompressed 19H394 kernel from `to-builder/2026-11-19-j81-miscacg-3dbfe00` (sha256 `c3507666766775dc854d5bcf6c375e6651ac8b2d1adb13d06331c60deb6a0008`), its j81dt, the November 11 `captures-20261121/a9tools-j81-19h394` kext split, the 8.1 image `gpu-offline/g4g81-image.bin`, and the upstream snapshot in request 7's `context/data/`.

**Scope.** Request 7 refines request 5, so this one result answers both. The same files are in `from-builder/2026-11-22-j81-rgx-post-id-result/` and `from-builder/2026-11-22-j81-meta-mtp219-boot-result/`.

How the tasks map:

| This result | Request 5 | Request 7 |
|---|---|---|
| A. Firmware image | T2 (image part) | T1 |
| B. Start sequence | T1 | T2 |
| C. Address space | T2 (memory part), T3 | T3 |
| D. Interrupts and firmware interface | T4 | T4 |
| E. First steps | T5 | T5 |

**Provenance.** Each AGXG4G and AGXFirmwareKextG4G section in the a9tools split was byte-compared against the packet kernel; all sections match. Addresses below are kernel VAs with the `0xfffffff00` prefix shortened where unambiguous.

**Tags:**
- **[code]** read from disassembly
- **[adt]** read from j81dt
- **[capture]** observed on hardware in the context notes
- **[upstream-claim]** taken from the third-party upstream snapshot
- **[inferred]** reasoning

Nothing below was observed executing.

Two parts were traced by sub-analyses and spot-checked here: the MMU (Appendix T3) and the IRQ/FWIF work (Appendix T4). Those appendices keep their own tags. One wording in Appendix T3 is superseded (see Section B).

## Findings

**A. Firmware image: located, strong.**
- [code] The META firmware is a plain Imagination META LDR stream in `AGXFirmwareKextG4G` `__TEXT.__const`: VA `0xfffffff0059ab9c8`, size `0x1cbb4` (117,684 bytes).
- [code] The kext's provider method `0x69820c0` returns exactly that pointer and size.
- [code] There is no signature, encryption or compression wrapper; integrity is per-block checksums only.
- [code] It holds two firmware ELFs, `METAFW_G4G.build/g4g_a0/g4g_a0_t0.elf` and `g4g_a0_t1.elf`.
- [code] Every L1/L2 command decodes with the upstream `ROGUE_META_LDR_CMD_*` and `meta_ldr_*` format: 88 records = 67 LOADMEM, 13 ZEROMEM, 2 CONFIG (27 register writes), 5 comments, 1 START_THREADS. See `ldr-segments.tsv` and `ldr-config.tsv`.
- [code] START_THREADS: thread 0 starts at PC `0x10000000` with SP `0x8000a3c8`; thread 1 at PC `0x20000000` with SP `0x8000b3c8`.
- [code] Core memory receives about 21 KiB of code (`0x80000080–0x80005334`) plus zeroed stack/data at `0x8000a000–0x8000c3c8`. Apple does not use upstream's `0x82000000` data window.
- [code] Everything else lives in DDR behind the GPU MMU, in four segments: seg0 `0x1…`, seg1 `0x2…`, seg2 = 56 bytes at `0xc0000000` (alias of `0x40000000`, the boot PC), seg3 = `0xe0001000–0xe0002000`.
- [inferred] The 56-byte seg2 block contains no address-like words and looks like META instruction encodings, i.e. a boot trampoline.
- [code] The 8.1 image has the same structure: 80 records, 27 config writes, 2 threads, 86 KB loaded versus 110 KB here.
- Private image sha256 is `55018c7eacef950ff438461f79ac6513e50b0c8528b191e8e064dfae40092c2f`. The bytes stay in the archive.

**B. Start sequence: located for the host side, strong; the META-side release is inferred.**

[code] The start callback `createHardwareMappingsAndBootFirmware` (`0x6673f00`, registered by accelerator start `0x666d6e4`) runs these steps in order:
1. `createHardwareMappings` (accel `+0x940`).
2. `prepareHardwareMappings` (`+0x950`).
3. accel `+0x958`.
4. `prepareFirmwareData` (fw `+0xa8`, `0x668fa88`).
5. fw `+0x98` (`0x668f770`). It ends by calling fw `+0xe0`, the hardware start (`0x6690bbc`).
6. accel `+0x8a8(1)`.
7. `bootFirmware` (fw `+0xc0`, `0x6690328`).
8. accel `+0x7e8`.

Here fw is the AGXMetaFirmware controller at accel `+0xdd8` (vtable `0x6f2de28`), and the RGX base is accel `+0xd10`.

[code] **Firmware image staging.** The LDR processor (fw `+0xb8`, `0x668fbc0`, with the loader body in `0x668fd58`) does the following:
- Allocates one "Firmware Image" buffer at fw `+0xa78` and maps it into the GPU MMU with options `0x60007`.
- Walks the LDR: command = `tag & 0x1f`; address `& 0x7fffffff`; segment = address bits 30:29; core memory is based at `0x80000080`.
- Copies each payload and byte-verifies it (`0x66901ec`).
- Appends META segment-MMU tuples for segments 0, 1 and 3 to a register/value list at buffer `+0x200` (fw `+0x480`, `0x66947cc`). Segment 2 is skipped. This list is upstream's bootloader conf (`ROGUE_FW_BOOTLDR_CONF_OFFSET`).
- Ends the list with a 0,0 terminator (`0x6690224`) followed by a word pointing at the bootloader segment's last 8 bytes. Those 8 bytes hold the firmware addresses of the root blocks (`0x6690250–0x6690318`).

The host never writes META memory or segment registers through the slave port.

[code] **Register-write primitive.** fw `+0x1e0`, `+0x1e8` and `+0x1f0` are write32, write64 and write64-of-`value >> shift`.
- When global byte `0x7a4d882` bit 1 is clear, they store directly to RGX MMIO.
- When it is set, they forward to the Fender/GPC object (fw `+0x160`, vtable `0x6f2fee8`, slots `0xc0`/`0xc8` = `0x69c610`/`0x69c66c`). That object writes the register number, then the value, into a Fender mailbox word, reading back and calling Fender `+0xb0` after each word.
- The bit is "use GPC/Fender". It can be forced by boot-arg `gpu_gpc=0/1` (`0x6683778`); otherwise it defaults on when the ADT lacks `no-gpc`/`has-kf`, and J81 lacks both (Appendix T4).
- Appendix T3 calls this a "debug/capture" byte. That wording is superseded.

[code] **Hardware start, fw `+0xe0` (`0x6690bbc`).** These writes go through the primitive, so on J81 they pass through Fender:

| # | Action |
|---|---|
| 1 | Fender `+0x20(3)`, `+0x58`, `+0xa8` |
| 2 | SOFT_RESET `0x100` ← `0x00e7fffffffffc1d` |
| 3 | SOFT_RESET ← `0x00e7fe071ffffc1d` |
| 4 | SOFT_RESET ← `0x0000000100000000`: only the bit [upstream-claim] calls GARTEN, i.e. META, stays in reset |
| 5 | **META_BOOT `0xbf8` ← 1** (master-boot mode, as upstream `pvr_meta_wrapper_init`) |
| 6 | BIF_CAT_BASE0 `0x1200` ← page-catalogue physical address (accel `+0x740`, `0x6699228`) |
| 7 | SLC_CTRL_MISC `0x3800` ← `0x0003550000300001`, then `0x3808` ← 1 (accel `+0x748`, `0x669924c`) |
| 8 | If the GPC bit is set: SOFT_RESET ← 0 here, then Fender `+0xb8` |

[code] **`bootFirmware`:**
- If the GPC bit is clear, it writes SOFT_RESET ← 0 directly.
- If set (J81), it calls Fender `+0x60(0)`, which writes Fender `+0x20000 = 0`, then `setGPCPerformanceState(1)` (Fender `+0x10`, `0x6698d94`). That polls Fender `+0x1000` bit 4 clear (10 µs steps) and writes Fender `+0x1000 = 0x11`, the same `0x11` GPC request the Linux recipe already performs.
- It then calls `waitForFWAlive` (`0x6694d40`) and logs "GPU firmware booted successfully".

[code] Not in the host path:
- No META thread PC/SP write (`0x0480fff0` does not occur).
- No TxENABLE set.
- No MTS_GARTEN_WRAPPER_CONFIG write.
- No AXI-ACE write.
- No BIF_CTRL_INVAL write.

[inferred, strong] With META_BOOT = 1 and SOFT_RESET released, META boots from `0x40000000`. That is mapped by default to GPU VA `0xe1c0000000` [upstream-claim]. The boot code applies the list at `+0x200`, copies core memory, then runs START_THREADS from the image. This explains why the host never writes PCs.

[code] **Power-down mirror** (`0x6693efc`, `0x66992ac`):
1. Halt threads 0 and 1 over the slave port (T0/T1ENABLE ← `0xfffffffe`).
2. Write `0x1340` ← 1.
3. Write BIF_CTRL `0x12a8` ← 8.
4. Write SOFT_RESET ← `0x08000000` (bit 27 = SLC [upstream-claim]).
5. Poll SLC_IDLE `0x3898 & 0xff` until it reads `0xff`.

[code] **Slave port, matching upstream.**
- Write: MSLVCTRL0 `0xa10` ← address, then MSLVDATAT `0xa08` ← value.
- Read: MSLVCTRL0 ← `address | 1` (`0x6694a4c`), then read MSLVDATAX `0xa00` (`0x6694b2c`).
- Poll MSLVCTRL1 `0xa18` for `0x05000000` (READY|GBLPORT_IDLE) in 10 µs steps, with a 100 ms timeout.

**Differences from upstream `pvr_fw_start`:**
- Writes can be proxied by Fender.
- No Garten config write was found.
- Apple-specific SLC values and register `0x3808`.
- Two firmware threads/ELFs.
- The soft-reset staging masks differ from upstream `MASKFULL`.
- The stop path is otherwise close to `pvr_fw_stop`.

**C. Address space: located, strong (Appendix T3).**
- [code] The GPU uses Imagination's own BIF/Rogue MMU, not a DART.
  - [adt] The `sgx` node (`gpu,t7001`, regs `0x2_0100_0000` and `0x2_01e0_0000`, 1 MiB each) has no mapper; the DART nodes are display, scaler, jpeg, isp, ave and apcie1 only; `carveout-memory-map` is empty.
- [code] Page-table format, three levels:
  - PC: 1024 × 4 bytes, entry `((PD_pa >> 12) << 4) | 1`.
  - PD: 512 × 8 bytes, entry `PT_pa | (pageshift - 12) | 1`.
  - PT: 512 × 8 bytes, entry `pa | 1 | flags`.
  - All tables are 4 KiB-aligned.
  - The page size is a global defaulting to 12; whether J81 overrides it to 14 is open.
- [code] The page catalogue's physical address goes raw into BIF_CAT_BASE0.
- [code] GPU-VA partitions include the firmware heap at `0xe1c0000000` (2 MiB), `0xe1c0200000` (48 MiB), `0xe1c3200000` (16 MiB), `0xe1c4200000` (4 MiB) and `0xe1c4600000` (4 MiB).
- [code] The firmware-address translator (fw `+0x1a8`, `0x6691704`) computes `fw = (u32)(va + 0x40000000) | region`, with region `0xc0000000` by default or `0x40000000`. The 16 MiB window at `0xe1c3200000` is special-cased. This is the same formula as iOS 8.1.
- [code] Segment tuples written into the list, `n ∈ {0, 1, 3}`:

| Register | Value |
|---|---|
| BASE | `base \| 0xf02` |
| LIMIT | `max(size, 0x1000) - 1` |
| OUTA0 | segment GPU-VA, low 32 bits |
| OUTA1 | `(va >> 32) \| (dm << 8)` |

  - The DM is 7 or 0, depending on ordering (open). Expected seg0 BASE is `0x10000f02`.
  - [capture] Linux read SEG0 = `0x08000f02` / `0x17fff000`. Those are therefore hardware defaults, not Apple's values.
- [code] All allocations use options `accel[0x1a98] | 3`, where `accel[0x1a98]` is only ever 0. [inferred] That means default cacheable memory.
- **Linux must allocate before release:**
  - the PC, plus PDs and PTs for the `0xe1c0000000` range;
  - the firmware buffer at VA `0xe1c0000000` in context 0, laid out seg2, seg0, seg1, seg3, then core memory;
  - the boot list at `+0x200` with its tail;
  - a root block (`0x1490` bytes) and a state block (`0x2058` bytes) whose firmware addresses go in the tail;
  - the rings that the root block points to (D).

**D. Interrupts, handshake and firmware interface: located, medium–strong (Appendix T4).**
- [adt] The `sgx` interrupts are AIC IRQs 134–138 (`interrupt-parent` = `/arm-io/aic`).
- [adt] `meta-sw-interrupt` holds two {SW_SET `0x2_0e10_4010`, SW_CLR `0x2_0e10_4090`, mask} records; the driver uses the second, mask `0x400`.
- [code] **IRQ 138 (index 4) is the firmware→host doorbell.** It is an AIC software interrupt, not an RGX status bit.
  - The handler writes `0x400` to AIC SW_CLR, then drains the event ring, log ring and FWTRACE.
  - The firmware learns the doorbell from the config block, which holds the SW_SET offset at `+0x2e4` and the mask at `+0x2e8`.
- [code] The other IRQs:
  - IRQ 134 is MMU/BIF (reads `0x1290`).
  - IRQs 135–137 are Fender (read Fender `+0x14`, write back `& 7`).
  - On the non-GPC fallback the doorbell clear writes RGX `0xac8` ← 0.
- [code] Host→firmware kicks go to MTS_SCHEDULE `0xb00`: `0x10` for TA, kick and device-control; `0x11` for 3D; `0x12` for CL.
- [code] **Alive is an event-ring record of type 0**, not a register.
  - Its handler (fw `+0x388`, `0x6693ea8`) stores record word `+4`, sets fw `+0xb35` and wakes `waitForFWAlive`.
  - `waitForFWAlive` sleeps on an IOCommandGate, up to 10 × accel `+0xc20` (value unresolved).
- [code] The firmware interface is Apple's own; see `fwif-objects.tsv`. It has:
  - a root block (`0x1490`);
  - a config block (`0x318`) with 9 MMIO window descriptors (FenderRegs, RGXRegs, AIC timer, AIC SW interrupt …) that the firmware maps as "Firmware PIO";
  - 4 host→firmware rings of 256 × 20 bytes;
  - an event ring of 256 × 44 bytes;
  - log and trace rings.
- [inferred] This is not upstream's `rogue_fwif_sysinit`/`osinit`/KCCB/FWCCB. Upstream's FWIF init and boot-wait code cannot be reused. Reusable pieces are the LDR parser, META slave-port access, SOFT_RESET/META_BOOT/BIF_CAT_BASE programming, the MMU format and the MTS values.
- [code] DVFM: `setGPCPerformanceState` is only ever called with 0 or 1. State 1 is part of the boot; the idle-off timer and perf statistics matter only for performance.

**E. First steps for Linux: see `t5-steps.tsv`.** Every step below runs after the existing recipe has identified the GPU.

*R: reads only*
- **R1.** Read RGX META_BOOT `0xbf8`, BIF_CAT_BASE0 `0x1200`, SLC_CTRL_MISC `0x3800`, `0x3808`, SLC_IDLE `0x3898`, BIF_CTRL `0x12a8`, `0x1340` and MSLVIRQSTATUS `0xac8`. The fault-status reads Apple's own handlers use (`0x1288`, `0x1290`, `0x12b0–0x12c8`) are also safe.
- **R2.** Over the slave port, read META segments 1–3 (`0x04850010–0x0485003c`), TxPRIVEXT and the MMCU cache control. Add the planned core-memory reads of `0x80000000`/`0x82000000`.
  - Expected: META_BOOT = 0, which would explain why META never ran despite SOFT_RESET = 0. CAT_BASE0 = 0. Segment 2 holds the boot default.

*W0: memory only, no MMIO*
- Build the page tables, firmware buffer, boot list and a zeroed root block in Linux memory, then dump and verify them offline against `ldr-segments.tsv`.

*W: the first GPU writes (higher risk)*
- **W1.** First GPU write: write META_BOOT's R1 value back unchanged, then read it back. This tests whether direct RGX writes land on J81, where stock routes them through Fender.
  - If the readback differs, or a later real write does not stick, implement the Fender mailbox (`0x69c610`) first.
- **W2.** Stock staging: SOFT_RESET ← `0x00e7fffffffffc1d`, then `0x00e7fe071ffffc1d`, then `0x1_00000000`. Read back after each. The expected old value is 0 [capture]. The unwind is SOFT_RESET ← 0, then re-read the identity.
- **W3.** META_BOOT ← 1 (expected old value 0 from R1).
- **W4.** BIF_CAT_BASE0 ← the W0 page catalogue's physical address (expected old value from R1).
- **W5.** SLC_CTRL_MISC ← `0x0003550000300001` and `0x3808` ← 1. Old values come from R1; do not proceed if they are unexpected.
- **W6 (first firmware run, highest risk).** Write SOFT_RESET ← 0, then GPC state 1 exactly as the existing recipe does it. Observe, without waiting for alive:
  - T0ENABLE bit 0 set means the loader ran START_THREADS;
  - MMCU cache control = 1 and TxPRIVEXT = `0x80` mean the CONFIG block ran;
  - BIF fault status `0x12b0` shows MMU faults;
  - AIC IRQ 138.

  With a zeroed root block, the firmware may fault or assert after starting. A BIF fault with threads enabled still proves the boot path. Recovery is the stock stop sequence in B, or the watchdog.

Do not write voltage, PLL or segment registers over the slave port.

## What could not be resolved
- **Release ordering.** Whether META_BOOT is 0 at reset on J81 (R1 answers this), and whether direct writes work without the Fender mailbox (W1 answers this).
- **Fender mailbox details.** The register offset (Fender object `+0x20`) and the meaning of Fender slots `0x20`, `0x58`, `0xa8`, `0xb0` and `0xb8`.
- **Page size.** Whether the effective MMU page size on J81 is 12 or 14.
- **Segment tuples and buffer placement.** The DM field value, the exact landing VA of the firmware buffer, and whether the page-table writes are cache-cleaned.
- **Firmware-interface contents.** The `0x1490`, `0x2058`, `0x990` and `0x8e0` blocks, event types 2–8, and the alive-wait interval accel `+0xc20`. Without these, a firmware run will not complete a full handshake.
- **Register meanings.** `0x1340`, `0x3808`, SLC decode mode `0x30`, and accel `+0x12c1`.
- **Seg2 content.** Whether the 56-byte block is a boot trampoline (inferred only).

**What would close the gaps:** a decompiler pass (Ghidra is not installed here) over `0x668a03c`, `0x687b50`, `0x68911c`, `0x6897a8` and the Fender class. Hardware runs R1 and W1 settle the two ordering questions.

## Files
- `RESULT.md`
- `ldr-segments.tsv`, `ldr-config.tsv`
- `host-start-sequence.tsv`, `rgx-register-writes.tsv`
- `mmu-format.tsv`, `irq-handshake.tsv`, `fwif-objects.tsv`
- `t5-steps.tsv`
- `appendix-t3-mmu.md`, `appendix-t4-irq-fwif.md`
- `SHA256SUMS` (mailbox copies only; this repository copy is otherwise byte-identical)

No firmware bytes are included.
