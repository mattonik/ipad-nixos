# J81 GPU: LDR/layout tool, Apple firmware-interface blocks, Fender ConfigRAM (answers request 8)

Offline only, 2026-11-22. No device, no firmware execution. This follows up `from-builder/2026-11-22-j81-meta-mtp219-boot-result`.

Inputs:
- The 19H394 kernel (sha256 `c3507666…a0008`).
- The private 19H394 LDR image (sha256 `55018c7e…092c2f`).
- The 8.1 image (sha256 `314454e8…534b8`).
- The packet's `context/` (the OrchardLinux A10 notes are third-party claims about a different SoC).
- Public Imagination DDK trees, listed in `appendix-t2-ddk.md`.

Two sub-analyses wrote `appendix-t2-ddk.md` and `appendix-t34-fender-a10.md`. Their central claims were re-checked in the disassembly here, as noted in each finding.

Tags:
- **[code]**: 19H394 disassembly.
- **[capture]**: J81 hardware, from the context notes.
- **[ddk-claim]**: public Imagination source, unverified for Apple.
- **[a10-claim]**: OrchardLinux A10 notes.
- **[inferred]**: reasoning, not directly observed.

Addresses drop the `0xfffffff00` prefix.

**Corrections to the previous result:**
- It described a Fender "mailbox" whose words take effect one by one, and slot `0xb0` as a wait. Both are wrong. Slot `0xb0` only advances the list offset by 4, and the list is Fender ConfigRAM, applied at a power transition (T3).
- Its W1 advice is superseded by T3/T5.
- The GPU page size is no longer open: it is fixed at 4 KiB (T4).

## Findings

**T1. LDR parser and layout builder: done, tested.**

`tool/j81_meta_ldr_layout.py` is Python 3, standard library only. It reproduces Apple's two loader passes [code]:
- **First pass** (`668fc0c`): segment bounds.
- **Layout** (`668fd58`): `size_n = align_up(end − start, A)`; order seg2, seg0, seg1, seg3, then core memory; tail at `size2 − 8`.
- **Second pass** (`668ffe8`):
  - LOADMEM is copied and byte-verified.
  - ZEROMEM is cleared, except in core memory.
  - CONFIG entries must be type 2 (write) and are appended to the boot list.
  - The host keeps only thread 1's `(pc, sp)`.
- **Boot list at buffer `+0x200`** (`668ff04`):
  - First 12 segment-MMU pairs for n = 0, 1, 3 (`66947cc`): BASE = `min | 0xf02`, LIMIT = `size − 1` (minimum `0xfff`; the same rule as upstream `configure_seg_id`), OUTA0 = VA[31:0], OUTA1 = `dm << 8 | VA >> 32`.
  - Then the 27 LDR config pairs, a `0,0` terminator, and the tail word, which is the firmware address of the tail (`6690218`–`6690318`).
- **Translator** (`6691704`): firmware address = `(u32)(va + 0x40000000) | region`.
- **Extra output:** the stock Fender ConfigRAM word list (T3).

Outputs:
- Text tables and `manifest.json`, with SHA-256 hashes only. They may be public.
- `fw-buffer.bin` and `boot-list.bin`, written only to a caller-named private directory (mode 0700/0600). The tool refuses a directory inside a Git work tree unless Git ignores it.

`tool/test_j81_meta_ldr_layout.py` has 11 tests and all pass:
- **Synthetic stream (always runs):** layout, copy and zero, boot list, tail, translator, rejection of non-write config types, ConfigRAM encoding, private-directory refusal, and a check that no table contains payload bytes.
- **19H394 image:**
  - 88 records: 67 load, 13 zero, 2 config, 5 comment, 1 start; 27 config writes.
  - Segment bounds as in the previous result; core memory `0x80000080 + 0x52b4`; 3 core-memory zero records skipped.
  - Boot list of 12 + 27 pairs.
- **8.1 image:** 80 records, 27 config writes, 3 skipped core-memory zero records.

One real difference showed up. The 8.1 image starts its core memory at `0x80000000`, but the 19H394 loader hard-codes `0x80000080` (`6690040`). So the 19H394 rules cannot place the 8.1 image: the tool refuses it rather than misplacing it, and `--coremem-base 0x80000000` lays it out [inferred: the 8.1 loader's own rule was not traced].

19H394 result with defaults (`tables-19h394/`):
- **Buffer:** `0x212b4` bytes at GPU VA `0xe1c0000000`. seg2 `+0x0` (0x1000), seg0 `+0x1000` (0x18000), seg1 `+0x19000` (0x2000), seg3 `+0x1b000` (0x1000), core memory `+0x1c000` (0x52b4, firmware address `0x4001c000`).
- **Boot list:** `+0x200`–`+0x343`. Tail at `+0xff8`, tail word `0xc0000ff8`.

Placement assumptions are parameters, recorded in the manifest:
- **A1, GPU VA `0xe1c0000000`:** required, because seg2 sits at offset 0 and META boots through the default seg2 mapping read on J81 [capture].
- **A2, alignment `0x1000`:** see T4.
- **A3, DM 7.**
- **A4, root/state tail addresses:** supplied by the caller.
- **A5, core-memory base.**

**T2. Apple's init blocks against the public DDK: located; descent from the DDK at the boot layer only.**

Four DDK trees were fetched, all Imagination, dual MIT/GPLv2: 1.3@2966915, 1.4@3158044, 1.6 (headers only) and 1.8@4688949. The Fuchsia mirror the packet named no longer exists.

- [ddk-claim + code] **No firmware-interface structure matches Apple's in size or field order.**
  - `RGXFWIF_INIT` is 0x1a8 / 0x1b8 / 0x258 in 1.3 / 1.4 / 1.8; Apple's root block is 0x1490.
  - CCB control is 0x10; Apple's ring control is 0x20.
  - KCCB commands are 0x30 / 0x90; Apple's ring entries are 20 bytes.
  - FWCCB commands are 0x20; Apple's events are 44 bytes.
  - The trace buffers differ.
  - The kext has no FWIF strings.
- **The boot layer does descend from DDK ≈1.3–1.5:**
  - **Hardware start = DDK 1.3 `RGXStart` (strong).** The first two SOFT_RESET values differ by exactly `0x1f8e0000000`, the RASCAL and DUST_A–H bits; I re-checked this here.
  - **Bootloader config at `+0x200` (strong):** it is `RGXFW_BOOTLDR_CONF_OFFSET`, with a `0,0` terminator.
  - **Segment numbering and base (strong):** text 0, shared 1, bootloader 2, data 3, firmware heap at `RGX_FIRMWARE_HEAP_BASE 0xe1c0000000`.
  - **Data master 7 in OUTA1 = `0x7e1` (medium):** this form exists only up to DDK 1.5, which dates the descent.
  - **The LDR CONFIG block (strong):** it is upstream's `configure_meta_caches()` sequence, carried inside the image instead of generated by the host [code + upstream-claim]. `LOCAL_EBCTRL 0x04830600 ← 0xc0c0` is identical; it also has DCPART and ICPART with Apple's own values, D-cache and I-cache control `← 1`, the same unexplained `0x040000c0 ← 0`, and TxPRIVEXT `← 0x80` (MINIM_EN).
- **Alive differs.** The DDK has the firmware set `bFirmwareStarted` in the init struct while the host polls. Apple's firmware sends a type-0 event record whose word `+4` is the META PC of its idle loop.
- **Conclusion:** the DDK's init, command-buffer and trace code cannot be reused. Apple's blocks are Apple-only.
- `appendix-t2-ddk.md` §3 gives the host-written field layout: root, state, config (six heap bases, a 9-entry MMIO window table at `+0x1c0`, doorbell `+0x2e4`/`+0x2e8`, `+0x300 = 0xe1c0000000`, `+0x30c = 7`), the list-head blocks, and the rings. The minimal first-boot content is in §4. The root block's last part, `+0x490`–`+0x148f`, is never written by the host.

**T3. Fender: ConfigRAM, not a mailbox. Located, strong. Verified here.**

[code] The Fender object (40 bytes) is at fw `+0x160`. Its fields:
- `+0x10`: Fender virtual address.
- `+0x20`: ConfigRAM write offset.

The ConfigRAM methods are slots `0xa8`/`0xb0`/`0xb8`/`0xc0`/`0xc8` = `669c5dc`/`669c5e8`/`669c5f8`/`669c610`/`669c66c`:
- **Start (`0xa8`):** offset ← `0x10000`.
- **Advance (`0xb0`):** offset += 4.
- **End (`0xb8`):** store `0xffff0000` at the current offset, then read it back.
- **32-bit write:** two words, `reg | 0xff << 16` and the value.
- **64-bit write:** four words, high half first: `(reg + 4) | 0xff << 16`, `val >> 32`, `reg | 0xff << 16`, `val & 0xffffffff`.

[a10-claim + code] The A10 notes name the same methods (`initConfigRAMOffset` … `writeConfigRAMCommand64`) as panic stubs on G9P; on J81 they are implemented.

[code] With the GPC bit set (the J81 default), the firmware write primitives fw `+0x1e0`/`+0x1e8`/`+0x1f0` write only to ConfigRAM, never to RGX. Their only callers are hardware start and accelerator `+0x740`/`+0x748`. All runtime accesses are direct RGX stores: the MTS kick, the stop path, the slave port, `0xac8`, and the MMU reads.

The stock list is 30 words at Fender `+0x10000`–`+0x10074` with the terminator at `+0x10078`. The tool's `fender-configram.tsv` reproduces it:
1. SOFT_RESET ×3.
2. META_BOOT ← 1.
3. BIF_CAT_BASE0 ← page-catalogue physical address.
4. `0x3800` ← `0x0003550000300001`.
5. `0x3808` ← 1.
6. SOFT_RESET ← 0.

**Applying the list** [code + inferred]:
- Accelerator start first drops the early state-1 power to state 0 (`666d958`: `+0x1000 ← 0x10`, poll bit 4).
- `bootFirmware` writes `+0x20000 ← 0`, then runs `setGPCPerformanceState(1)`: poll `+0x1000` bit 4 clear (10 µs steps, 30 s), write `0x11`. Then it waits for alive.
- [inferred, strong] Fender replays ConfigRAM into RGX at that 0→1 transition: META_BOOT and the reset release exist only in ConfigRAM, yet stock firmware boots.

Fender register map, with Apple's names from its dump function (`669bbd8`):

| Offset | Apple name | Role |
|---|---|---|
| `+0x0` | `TIMER_SLEEP_CONTROL` | early init writes `0x40000000`; bit 29 is "SNOOP" |
| `+0x8` | `TIMER_KICK_STATUS` | |
| `+0x10` | `TIMER_POWER_INT_ENABLE` | the A10 notes call it a request register; on J81 it is an interrupt enable |
| `+0x14` | `TIMER_POWER_INT_STATUS` | write-1-to-clear, bits 2:0 |
| `+0x1000` | `VCM_PERF_STATE_CONTROL` | state in bits 3:0, busy in bit 4 |
| `+0x20000` | `VCM_PERF_STATE_OVERRIDE` | |

[a10-claim only] The A10's `+0x2000`–`+0x2058` IOP block belongs to the A10's A7 coprocessor. The J81 host never touches it, and none of the RTKit/IOP material applies to a META firmware.

**T4. Other A10 implications: mostly answered.**
1. **Page size: GPU pages are 4 KiB, fixed [code, verified here].** `AGXAccelerator::start` (`666d9f0`) switches to the kernel's 16 KiB page shift only if accelerator slot `0x878` ("TEST_PAGE_SIZE_16K") returns true. On G4G that slot is `69b048: mov w0, #0; ret`. The A10's 16 KiB GPU pages do not apply. A Linux kernel built with 16 KiB pages would need 4 GPU PT entries per CPU page.
2. **`pwr_ops` [a10-claim + code]:** the A10's AP-side `+0x1000 = 0x11` is exactly the J81 stock request. RGX is read only once the state is at least 1 (fw slot `0x240`).
3. **Firmware from the kernelcache [a10-claim + code]:** the same provider pattern. J81's provider is `AGXFirmwareKextG4G` `69820c0` → `0x59ab9c8`, size `0x1cbb4`. J81's image is a META LDR, so none of the A10 RTKit/init-data/ring work transfers.
4. **Static device info [inferred]:** still needed. Neither the LDR nor the kext carries a BVNC or feature table. Read `0x18`/`0x20` only in state 1.
5. **Performance states [adt + a10-claim]:** J81's static ADT has `perf-states`, `perf-state-count` and `gpu-num-perf-states` all zero; the A10 notes say iBoot fills them. The J81 host uses only states 0 and 1.
6. **Shader ISA: unresolved.** G4G has Apple-defined shader-core registers at RGX `0xe010`–`0xe080` (`AGX_CR_USC_INST_BASE_*`, `AGX_CR_USC_PARTITION_CONFIG`) next to stock `RGX_CR_USC_SERV_*` [code]. That is evidence of Apple changes, not of a non-Rogue ISA. The A10 test applies: obtain a G4G shader binary and check for a Rogue `nop.end` ending padded with `0xff`.
7. **What the A10 notes leave unknown for A8/A9:** the IOP, RTKit and init-data items do not apply to J81. The Fender items are answered above for J81.

**T5. Revised step list: `t5-steps.tsv`.** The smallest sequence to a firmware alive record:
- **M0–M3, memory only:**
  - the tool's buffer at `0xe1c0000000`;
  - a 4 KiB Rogue page table;
  - root, state, config and the other blocks and rings, zeroed with the [code] fields set;
  - the MMIO window table and doorbell.
- **F1, control step:** Linux performs the stock 1→0→1 cycle with an empty ConfigRAM and re-reads the identity.
- **F2, replay proof:** a ConfigRAM list holding only the two SLC writes, then 0→1, then read `0x3800`/`0x3808` directly. The R1 values `0x00320001`/`0` should become `0x00300001`/`1`.
- **F3, first firmware run:** the full 31-word ConfigRAM, then 0→1, then wait up to 10 s for the event-ring write index (`+0x10` of the event control) or AIC IRQ 138, and check for a type-0 record.
- **D-alt:** the direct-store path, analogous to `gpu_gpc=0`, held in reserve in case F2 shows Fender does not replay. W2a already proved that direct SOFT_RESET stores land [capture].

## Not resolved
- What ConfigRAM bits 16–23 mean (stock always writes `0xff`), the ConfigRAM capacity, and whether it is replayed on every wake. F2 tests whether it is replayed at all.
- Who sets SNOOP (Fender `+0` bit 29), and the meaning of bits 30 and 31. The fw `+0x358` table was not traced.
- The power-up helper `68ea90`.
- Root `+0x490`–`+0x148f`.
- Config `+0x30`, `+0x38`–`+0x1b7`, `+0x290`–`+0x29b`, `+0x2f0`, `+0x2f8`.
- Window-table entries beyond Fender, RGX and AIC.
- The contents and fill time of the `0x938` block.
- Event types 2–8.
- Whether the firmware checks any of these fields before sending alive.
- The alignment global (GOT `6f2a698`). The tool defaults to `0x1000`, consistent with the fixed 4 KiB GPU pages.
- Why only some SOFT_RESET bits read back in W2a.
- The 8.1 loader's core-memory rule.
- The G4G shader ISA.

## Files
- `RESULT.md`
- `t5-steps.tsv`
- `tool/j81_meta_ldr_layout.py`, `tool/test_j81_meta_ldr_layout.py`
- `tables-19h394/`: `ldr-records.tsv`, `ldr-config.tsv`, `buffer-layout.tsv`, `boot-list.tsv`, `fender-configram.tsv` (with `--pc-phys 0`), `manifest.json`
- `appendix-t2-ddk.md`, `appendix-t34-fender-a10.md`
- `SHA256SUMS`

No firmware bytes are included. `ldr-records.tsv` carries payload SHA-256 hashes only.

To reproduce:

```
python3 -I tool/j81_meta_ldr_layout.py <private 19H394 LDR> --tables T --private P [--pc-phys <PC phys>]
J81_LDR_19H394=<ldr> J81_LDR_81=<8.1 image> python3 -I tool/test_j81_meta_ldr_layout.py
```
