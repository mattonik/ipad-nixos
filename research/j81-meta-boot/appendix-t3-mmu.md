# T3: how the G4G GPU and META see memory (iPadOS 15.8.5 / 19H394, AGXG4G kext)

Tags: [code] read from the disassembly, [adt] read from the J81 device tree, [upstream-claim] from the provided upstream Linux PowerVR files, [inferred] my reasoning.

Object map used below [code]:
- The accelerator (vtable 0x6f2f2d0, AGXAcceleratorG4G_A0) owns these objects:
  - `+0xd10`: RGX register base.
  - `+0xdd8`: AGXMetaFirmware object. It is created by accelerator vtable slot 0x848 (0x669afa8, size 0xb60) and its vtable is 0x6f2de28.
  - `+0x150`: legacy MMU object (vtable 0x6f30ad8, size 0x3c8). Assigning it to `+0x150` is [inferred]: firmware mapping calls take `accel[0x150]` as the MMU argument, and `accel[0x150]` vtable slot 0x110 matches MMU slot 0x110.
  - `+0x19b0`: MMU format descriptor (vtable 0x6f30d10, size 0xf0), filled by its slot 0xb0 (0x669dd9c).
- Register-write helpers on the firmware object [code]:
  - slot 0x1e0 = write32 (`str w2,[rgx,w1]` at 0x6691834).
  - slot 0x1e8 = write64 (`str x2,...` at 0x6691870).
  - slot 0x1f0 = write64 of `value >> shift` (0x66918b0).
  - When the debug byte 0x7a4d882 has bit 1 set, all three go to a capture object at `fw+0x160`. That object's vtable is UNRESOLVED.

## 1. Imagination BIF/MMU or DART: **located, Imagination BIF/MMU, no DART**

- [adt] `/arm-io/sgx` has `compatible "gpu,t7001"` and two 1 MiB `reg` ranges at 0x0100_0000 and 0x01e0_0000. Through the arm-io `ranges` these become CPU physical 0x2_0100_0000 and 0x2_01e0_0000. The node has no mapper, `iommu-parent` or DART property. The `dart-*` nodes are disp0, scaler, jpeg, isp, ave and apcie1 only; none is for the GPU. `chosen/carveout-memory-map` is empty.
- [code] Accelerator slot 0x740 (0x6699228) writes `BIF_CAT_BASE[idx]`. It computes `off = (0x1200 + idx*8) & 0xfff8` and calls fw slot 0x1f0 with shift 0, so the 64-bit register gets the raw physical address. This matches [upstream-claim] `CAT_BASEx` ADDR bits [39:12] in place.
- [code] The only caller found is in fw slot 0xe0 (0x6690c94). It writes idx 0 with the value `*(u64*)fw[0x3e8]`.
  - `fw[0x3e8][ctx]` is a per-context PC-address array in FW-shared memory. It is allocated through the table at 0x66888e0 and updated by 0x668ba8c, which also sets `fw[0x3d8][ctx]`.
  - Entry 0 is set at 0x66891c4 from MMU slot 0x110 (0x669dcac), which returns `getPhysicalAddress(MMU+0x2c0)`. `MMU+0x2c0` is the PC buffer.
- [code] Fault and debug strings (`BIF%d page fault`, `RGX_CR_BIF_FAULT_BANK0_MMU_STATUS`, `RGX_CR_BIF_MMU_ENTRY`) and the PC/PD/PT fault walker at 0x66863e4 (MMU slot 0x128) confirm the Rogue MMU.
- [code] `agxkHalHandleMMUEntryPendingInterruptPreG5` (0x669b0ac) only logs "Should never get MMU entry pending interrupt!".
- [code] The host never writes `BIF_CTRL_INVAL` (0x12a0). It writes `BIF_CTRL` (0x12a8) = 8 and 0x1340 = 1 only in power-down paths (0x66992e4, 0x6694214), when `(accel[0x1a94] & 3) == 0`.

## 2. Page-table format: **located**

The descriptor is built at 0x669dd9c and copied into `MMU+0x310/0x330/0x350` at 0x668549c.

| Level | VA bits (index mask) | Entries x size | Table size / alignment | Entry layout |
|---|---|---|---|---|
| PC | 39:30 (0xffc0000000) | 1024 x **4 B** | 4 KiB / 0x1000 | `((PD_pa >> 12) << 4) \| 1`, address mask 0xfffffff0 |
| PD | 29:21 (0x3fe00000) | 512 x 8 B | 4 KiB / 0x1000 | `PT_pa \| (PAGE_SHIFT-12) \| 1`, address mask 0xffffffffe0 |
| PT | 20:12 (0x1ff000) | (512 >> (PAGE_SHIFT-12)) x 8 B | 0x1000 alignment | `page_pa \| f` |

Evidence and notes for the table:
- [code] Entry-writing sites:
  - PC entry: 0x668592c..0x6685954, with flags from MMU slot 0x170 = `[MMU+0x318]` = 1.
  - PD entry: 0x6685a80..0x6685aa4 and 0x6685b30, with flags from slot 0x178 (0x669dcd0) = `(gGpuPageShift-12) | 1`. The page-size field sits at bit 1, so 4 KiB gives 0 and 16 KiB gives 1 [inferred, matches Rogue PD PAGE_SIZE].
  - PT flags come from slot 0x180 (0x669dce4): `1 | (a&0xc) | (a.bit0 << 1) | (a.bit4 << 62)`. The bit names (RO = bit 1, bits 2/3 = CC/SLC-bypass, bit 62 = PM/META-protect, valid = bit 0) are [inferred]: pvr_rogue_mmu_defs.h was not in the provided set.
- [code] PT shift = `gGpuPageShift` (global 0x7a4cf80, default 12). 0x666da4c may overwrite it from a kernel global, after a check against PAGE_SHIFT==14. The PT index mask is hard-coded for 4 KiB pages, and the mapping granule depends on which global wins. UNRESOLVED [inferred].
- [code] GPU VA partitions (11 IORangeAllocators at `MMU+0x268..0x2b8`, set in MMU init 0x6685154):
  - 4 GiB each at 0x1_, 0x3_, 0x5_, 0x6_ and 0x7_0000_0000.
  - 0x8_0000_0000 (4 MiB "shared range"; its PD/PT are preallocated through MMU slot 0xd0).
  - **0xE1_C000_0000 (2 MiB)**, 0xE1_C020_0000 (48 MiB), 0xE1_C320_0000 (16 MiB), 0xE1_C420_0000 (4 MiB) and 0xE1_C460_0000 (4 MiB).
- [code] Who allocates: MMU slot 0x188 (0x66867bc) creates the PC with stub 0x66b15b8 (`withOptions(opts, 4096, 0x1000)` [inferred]). Then it calls `prepare(3)` and `getBytesNoCopy`, and zeroes the buffer. PDs and PTs are allocated the same way on demand in 0x66857ac. Physical addresses come from stub 0x66b1378 (getPhysicalAddress [inferred]).

## 3. META segment MMU: **located; the host never writes segment registers through the slave port**

- [code] The only `0x0485xxxx` immediates in the kext are in fw slot 0x480 (0x66947cc, configureSegment(fw, outaddr, n)).
  - It returns at once for n==2.
  - For other n it appends four {addr, value} pairs to an in-memory list at `fw[0xb40]`. That list starts at host buffer + 0x200, matching [upstream-claim] `ROGUE_FW_BOOTLDR_CONF_OFFSET` = 0x80 words. The META bootloader applies the list; the host does not.
- [code] It is called at 0x668ff34/60/8c/b8 for n=0..3, from the LDR processor fw slot 0xb8 (0x668fbc0). That processor is called from accelerator start at 0x666e8ec.
- [code] Segment index = (META load address bits 30:29). Base = min(addr & 0x7fffffff). Size = page-aligned extent. Core-memory loads (0x80000080 .. +0x17f*0x80) are tracked separately.
- [code] One host buffer holds all segments in the order seg2 @0, seg0 @size2, seg1 @size2+size0, seg3 @size2+size0+size1 (0x668fd5c..0x668fe1c).
- [code] That buffer is created by stub 0x66b127c (symbol UNRESOLVED) and mapped with `obj->vt[0x98](MMU, 0x60007)`. It is kept at `fw+0xa78`, and its GPU VA comes from `mapping->vt[0x88]`.
- [inferred] The 0x60007 high half (6) selects partition 6, the 0xE1C0000000 partition. That would put the bootloader (seg2, offset 0) at GPU VA 0xE1C0000000.

Values written into the boot-config list [code], with [inferred] numbers for this image assuming 16 KiB host page alignment:
- `BASE(n)` = seg_base | 0xF02, giving seg0 0x10000F02, seg1 0x20000F02, seg3 0x60001F02.
- `LIMIT` = max(size, 0x1000) - 1, giving seg0 0x17FFF, seg1 0x3FFF, seg3 0x3FFF.
- `OUTA0` = low32(bufVA + off_n). If bufVA = 0xE1C0000000, these are 0xC0004000 (seg0), 0xC001C000 (seg1) and 0xC0020000 (seg3).
- `OUTA1` = (VA >> 32) | ((init[0x30c] & 0xF) << 8).
  - The only store to init[0x30c] is 7 (0x668fa2c, constant {0,7} at 0x57c2d68). That is the upstream META BIFDM ID 7, giving 0x7E1. PC index is 0 in bits 15:12.
  - The first-boot order looks like LDR processing (0x666e8ec) happens before fw slot 0x98, which does that store. If so, the BIFDM field emitted is 0 rather than 7. UNRESOLVED.

Segment 2 and the Linux readback:
- No tuple for segment 2 is emitted [code]. Apple relies on the preconfigured bootloader mapping, [upstream-claim] META 0x40000000 -> devVA 0xE1C0000000, limit 0x1FFFF000.
- That fits the FW address translator, fw slot 0x1a8 (0x6691704) [code]: `meta = (u32)(gpuVA + 0x40000000) | region`.
  - region is 0xC0000000 by default.
  - region is 0x40000000 when `fw+0x1c9 == 0` and either flag `w2` is set or the VA is in [0xE1C3200000, 0xE1C4200000).
  - This is the same as the iOS 8.1 note's `(addr - 0xe1c0000000) | region`.
- The Linux readback SEG0_BASE=0x08000F02 / LIMIT=0x17FFF000 is not a value Apple writes. Apple overwrites seg0 (to 0x10000F02) via the bootloader. Those registers are probably the hardware reset or default state [inferred]. Segment 2 (0x04850020..2c) is the one to read back on Linux.
- [code] Slave-port writes that do exist are stop and inspection only:
  - 0x04800000 and 0x04801000 (`META_CR_CTRLREG_BASE(0/1)`, the thread 0/1 control-register block per [upstream-claim]) get 0xFFFFFFFE (0x66905c4, 0x6690954, 0x6693ff8, 0x669412c).
  - TXUXXRXRQ 0x0480FFF8 reads (0x6694b48).
  - No PC or SP writes: boot uses `META_BOOT`=1.

## 4. Allocations made before the firmware starts: **mostly located**

All of these use IOBufferMemoryDescriptor-style options `accel[0x1a98] | 3`. `accel[0x1a98]` is only ever zeroed (0x669c7f0), so the options are kIODirectionInOut with the default cache mode, i.e. cacheable [code; cacheability inferred]. No physically-contiguous or uncached flag is visible.
- PC: 4 KiB, 4 KiB-aligned (`MMU+0x2c0/0x2c8`). A dummy page (1 << PAGE_SHIFT, options 0) is kept at `MMU+0x300` [code].
- PDs and PTs: 4 KiB each, 4 KiB-aligned, on demand. The 0x8_0000_0000 shared range is prefilled at init [code].
- The firmware image buffer described in section 3, mapped into the GPU MMU (flags 0x60007), bzeroed, then filled by the LDR processor [code].
- The tail of the bootloader segment (`buf + size2 - 8`) gets two META addresses, those of the objects at `fw+0x238` and `fw+0x2b0` (0x6690268, 0x6690284) [code]. Their identity is UNRESOLVED; they are probably the init and OS-config structures [inferred].
- After the list terminator (0,0 at 0x6690224), one more word gives the META address of that tail (0x6690318) [code].
- `fw+0x1d8` receives the core-memory backing address and size at +0x480/0x484/0x48c [code].
- About 20 FW-shared objects are mapped by 0x668a03c (fw slot 0xa8 path). The init structure `fw+0x220` gets +0x300 = 0xE1C0000000 and +0x308/+0x30c = {0, 7} [code].

## 5. What Linux must do before releasing META: **[inferred], from the order the code uses**

1. Build a Rogue 3-level page table: a 4 KiB PC of u32 entries, PD and PT of u64 entries, using the entry formats in section 2, with 4 KiB GPU pages.
2. Map one physically backed firmware buffer at GPU VA **0xE1C0000000** in context 0. Lay it out as [seg2 bootloader @0][seg0][seg1][seg3][coremem], each page-aligned.
3. Copy the LDR payloads in. Write the boot-config list at +0x200: seg0, seg1 and seg3 tuples, then the LDR CFG-WRITE pairs, then 0,0, then the pointer to the tail. Fill the 8-byte tail at the end of seg2. Use META addresses = `(VA - 0xE1C0000000) | 0xC0000000` (or `| 0x40000000` for cached).
4. Program the RGX registers in Apple's order:
   - `SOFT_RESET` = 0x00E7FFFFFFFFFC1D, then 0x00E7FE071FFFFC1D, then 0x1_0000_0000.
   - `META_BOOT`(0xBF8) = 1.
   - `BIF_CAT_BASE0`(0x1200) = PC physical address (64-bit, as-is).
   - `SLC_CTRL_MISC`(0x3800) = 0x0003550000300001 and 0x3808 = 1.
   - Then `SOFT_RESET` = 0.
5. Do not program META segments over the slave port. Verify instead that segment 2 already maps 0x40000000 to 0xE1C0000000.

## Ordered register-write table

| # | Instr addr | Register | Value / composition | Condition |
|---|---|---|---|---|
| 1 | 0x6690c20 | SOFT_RESET 0x100 (64) | 0x00E7FFFFFFFFFC1D | fw slot 0xe0, reached from fw slot 0x98 tail (0x668fa64) when slot 0x240 is true, or on resume (0x6671fd8) |
| 2 | 0x6690c48 | SOFT_RESET | 0x00E7FE071FFFFC1D | same |
| 3 | 0x6690c64 | SOFT_RESET | 0x0000000100000000 (GARTEN only) | same |
| 4 | 0x6690c80 | META_BOOT 0xBF8 (32) | 1 | same |
| 5 | 0x6690ca0 -> 0x66918b0 | BIF_CAT_BASE0 0x1200 (64) | `fw[0x3e8][0]` = PC physical address, shift 0 | same |
| 6 | 0x6699284 | SLC_CTRL_MISC 0x3800 (64) | 0x0003550000300001 | same (accelerator slot 0x748) |
| 7 | 0x66992a8 | 0x3808 (64) | 1 | same |
| 8 | 0x6690cdc | SOFT_RESET | 0 | only when debug byte 0x7a4d882 bit 1 is set |
| 9 | 0x6690364 | SOFT_RESET | 0 (META runs) | fw slot 0xc0, normal path; then wait at 0x6694d40 |
| L | 0x66947f4..0x6694844 | boot list: SEG n BASE/LIMIT/OUTA0/OUTA1 | n = 0, 1, 3 as in section 3 | written to memory, not MMIO; n = 2 skipped |
| - | 0x66992dc/e4, 0x669420c/14 | 0x1340 = 1, BIF_CTRL 0x12a8 = 8 | | power-down only |

## Could not resolve

- The real symbols behind the stubs:
  - 0x66b127c: firmware-buffer allocator, (accel, task, 0, 0, options, size).
  - 0x66b15b8 and 0x66b1378 (probable withOptions and getPhysicalAddress).
  - The memory-object vtables: slot 0x98 = map(MMU, flags), 0x88 = GPU VA.
- Whether the firmware buffer really lands at exactly 0xE1C0000000; the partition-6 selection by 0x60007 is inferred.
- Whether OUTA1's DM field is 7 or 0 at the time the list is built.
- The real `gGpuPageShift` (12 vs 14) on J81.
- Register 0x3808's name; the SLC decode mode 0x30 is not in the upstream list.
- The PT flag bit names.
- Whether the host does a CPU cache clean after PTE writes (not traced).
- The capture object at `fw+0x160`, all vtable calls: UNRESOLVED.
- Accelerator slot 0x8a8 (0x6672800, called between pre-boot and release) only fans out to sub-objects at `accel+0xe30/0xde8/0xd30/0xe00`; those vtables are UNRESOLVED.
- The origin of the Linux SEG0 values 0x08000F02 / 0x17FFF000.
