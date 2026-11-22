# T2: J81 (G4G, META MTP219) firmware interface vs public Rogue DDK

Offline. Inputs: the 19H394 AGXG4G kext disassembly (`agx.ann`, `a9/AGXG4G.macho`) and public DDK sources. No device access, no firmware bytes. Helpers are in `$SCRATCH/t2/tools/`: `rd.py` reads kext data; `lay.sh` and `lay1[348].c` compute DDK struct sizes at compile time with clang. Nothing from the downloads was run.

Tags: **[code]** J81 disassembly · **[ddk-claim]** DDK source, unverified for Apple · **[inferred]** reasoning.

## 1. Sources

| DDK | URL / commit | Local dir (`$SCRATCH/t2/`) | Licence |
|---|---|---|---|
| 1.3@2966915 (Allwinner A80) | github.com/allwinner-zh/linux-3.4-sunxi @ `6964d467510849e3e262518cb87bff7ef92e01f5`, `modules/rogue_km/` (108 files: include, hwdefs, services/include, rgxinit/fwutils/power/heapconfig) | `src-allwinner-a80-ddk13-6964d46` | Dual MIT / GPLv2 file headers; MIT-COPYING and GPL-COPYING in tree; repo-level licence NOASSERTION |
| 1.4@3158044 (Intel fugu, G6430) | android.googlesource.com/kernel/x86_64 @ `18285c37db1d005ccc1a2f7be16730b0fa94cfec` (android-5.0.0_r0.4/r0.12), `+archive/.../drivers/external_drivers/intel_media/graphics/rgx.tar.gz` (sha256 `8cc71579…15df`) | `src-android-fugu-lollipop-18285c3` | Dual MIT / GPLv2 |
| 1.6@3490026 (MediaTek ChromeOS) | github.com/mtk09422/chromiumos-third_party-kernel-mediatek @ `781cb140f53f455e63c92ec35c3fcd9bc3ea6b77`, `drivers/gpu/drm/img-rogue/{rgx_meta.h,rgx_fwif_km.h,pvrversion.h}` | `src-chromeos-mtk-ddk16-781cb14` | Dual MIT / GPLv2 |
| 1.8@4688949 (brief's tree) | android.googlesource.com/kernel/x86_64 @ `606832966f458025cc2860316dfa201f3b9a3738`, `drivers/staging/imgtec/rogue` (sha256 `ec7d6828…0efb`), plus `pvrversion.h`, `config_kernel.h` and `powervr/` | `src-android-x86_64-6068329` | Dual MIT / GPLv2 |

What could not be fetched:
- **Fuchsia mirror.** `third_party/imgtec-pvr-rgx-km` no longer exists on fuchsia.googlesource.com ("Repository is not found"; absent from the repo index).
- **Android log.** One `+log` query on android.googlesource.com returned a bot-check page. I did not try to get past it.
- **Host boot-config code for 1.3–1.6.** No public 1.3–1.6 tree carries `rgxsrvinit` (it was user-mode then), so the 1.3–1.6 form of the host-written boot config is not public. The earliest host-side code seen is 1.8 `rgxfwimageutils.c`.

## 2. Verdict

**The FWIF objects are Apple's own. None of them descends from `RGXFWIF_*` (strong).** The boot and loader layer *does* descend from a DDK of about 1.3–1.5 (strong for the descent; medium for the version range).

**No whole-struct match.** DDK sizes computed by clang for a 32-bit target and the G6430 configuration [ddk-claim]:

| struct | 1.3 | 1.4 | 1.8 | closest Apple object |
|---|---|---|---|---|
| RGXFWIF_INIT | 0x1a8 | 0x1b8 | 0x258 | root 0x1490 / config 0x318 |
| RGXFWIF_CCB_CTL | 0x10 | 0x10 | 0x10 | ring ctl 0x20 |
| RGXFWIF_KCCB_CMD | 0x30 | 0x30 | 0x90 | ring entry 0x14 |
| RGXFWIF_FWCCB_CMD | 0x20 | 0x20 | 0x20 | event record 0x2c |
| RGXFWIF_TRACEBUF | 0xbda4 | 0xbdb0 | 0x2d0 | FWTRACE 256 × 0x2c |
| HWRINFOBUF / GPU_UTIL_FWCB / REG_CFG | 0x390 / 0x810 / 0x2008 | 0x390 / 0xfc8 / 0x2008 | 0x690 / 0x2030 / 0x3008 | 0x990, 0x8e0, 0x8c0, 0x938, 0x84, 0x2058 |

None of these is equal to an Apple size.

**Offsets do not line up either.**
- Apple root `+0x00..+0x3c` holds 16 u32 firmware addresses. `RGXFWIF_INIT` starts with a u64 `sFaultPhysAddr` [code vs ddk-claim].
- Apple's ring control is `{rd@0, wr@0x10}`: fixed 256 entries, 8-bit wrap, consumer index at +0. The DDK's is `{ui32WriteOffset@0, ui32ReadOffset@4, ui32WrapMask@8, ui32CmdSize@0xc}`.

**Strings.**
- The kext contains no DDK services identifiers (no RGXFWIF/KCCB/PVRSRV). The only DDK-style string is `"RGX_CR_META_BOOT 0x%08X"`.
- The firmware image strings use Apple "AGF" names (`AGFAcceleratorCheckGPUProgress`, `agfPollFenderReg`, `META FW started! (%s)`, a 2025 build date) plus DDK `RGX_CR_*` register names. They contain no FWIF names [code, strings only].

**Convention-level matches with the DDK, with strength:**

| item | Apple [code] | DDK [ddk-claim] | strength |
|---|---|---|---|
| Hardware start (fw +0xe0, `0x6690bbc`) | SOFT_RESET ← `0x00e7fffffffffc1d` → `…fe071ffffc1d` → `0x1_00000000`, SLC init, META_BOOT ← 1, CAT_BASE0, SOFT_RESET ← 0 | 1.3 `RGXStart`: MASKFULL → MASKFULL ^ RASCALDUSTS_EN → GARTEN_EN, SLC init, META_BOOT ← MODE_EN, (GARTEN_WRAPPER_CONFIG), BIF init, SOFT_RESET ← 0. The XOR difference `0x1f8e0000000` is exactly RASCAL + DUST_A..H | strong (Apple drops GARTEN_WRAPPER_CONFIG and AXI-ACE) |
| Boot config list | at image +0x200; {reg, val} pairs; 0,0 terminator; then one argument word (`0x6690218..0x6690318`) | `RGXFW_BOOTLDR_CONF_OFFSET` 0x80 dwords; pairs; `0x0, 0x0` "end of conf"; then "FW main argv" (1.8: INIT address, coremem fwaddr, coremem devVA hi/lo) | strong for the list; the argument form differs (Apple: one pointer to an 8-byte {root, state} array) |
| META segments | 4 segments, IDs 0, 1, 3 programmed and 2 = bootloader skipped; BASE \| 0xf02; boot at META 0x40000000 = GPU VA 0xE1C0000000 | 1.3/1.4/1.6: TEXT=0, SHARED=1, BOOTLDR=2, DATA=3; `ALLTHRS_WRITEABLE` = 0xf02; `RGXFW_BOOTLDR_META_ADDR` 0x40000000; `RGX_FIRMWARE_HEAP_BASE` 0xE1C0000000 (1.8 merges TEXT into ID 2) | strong |
| OUTA1 BIF-DM | config +0x308/+0x30c = {PC 0, DM 7} (`0x668fa2c`) | `RGXFW_SEGMMU_META_DM_ID` 7; `BOOTLDR_DEVV_ADDR_1` = 0x7E1 in 1.3/1.4, 0xE1 in 1.6 and 1.8 | medium; this is what dates the fork to ≤1.5 |
| Coremem handoff | root +0x480 fwaddr (region 0x40000000), +0x484 u64 GPU VA, +0x48c size of the coremem copy | INIT `sCorememDataStore` (1.3/1.4); argv[1..3] coremem fwaddr / devVA (1.8) | medium (same information, different place) |
| Per-DM host→firmware queues | 4 rings (TA, 3D, CL, DevCtl) plus 1 firmware→host event ring | 1.3/1.4: `psKernelCCBCtl[DM_MAX]` and per-DM firmware CCBs; 1.6: single firmware CCB | weak. MTS DM numbers differ (Apple TA/3D/CL = 0x10/0x11/0x12; DDK TA/3D/CDM = 0x12/0x13/0x14) |
| Config +0x00..+0x2f | 6 u64: 0x5_0, 0x6_0, 0x1_0, 0x1_0, 0x3_0, 0x3_0 (each `_0` = `_0000_0000`; heap bases [inferred]) | INIT +0x00..+0x2f: fault phys, PDS/USC exec bases, 3× Doppler base | weak (same shape; 1.3 heap values differ) |
| Alive | event-ring record type 0 via AIC SW IRQ 138 (`0x693ea8`) | firmware sets `RGXFWIF_INIT.bFirmwareStarted`; host polls (`rgxpower.c` RGXStart) | **no match** |

## 3. Field tables (first boot)

`fwaddr(x)` = `(u32)(gpu_va + 0x40000000) | 0xC0000000`, which is `offset_in_FW_heap | 0xC0000000` (fw slot 0x1a8). All writers are in fw slot 0x98 (`0x668f770` → `0x668911c`) unless stated otherwise. The host never reads root back.

**Root block (0x1490; CPU at fw+0x1d8, fwaddr at fw+0x238)**

| off | size | meaning | DDK | writer | first-boot value | tag |
|---|---|---|---|---|---|---|
| +0x00..+0x1c | 8×4 | fwaddr {ctl, buf} for TA, 3D, CL, DevCtl rings | (per-DM KCCB ctl/buf pointers, concept only) | 0x66891e4..0x66892c4 | addresses | [code] |
| +0x20..+0x3c | 8×4 | fwaddr {ctl, buf} for event (0x2c00), log (ctl 0x80, buf 0xb000), FWTRACE (0x2c00), 36-byte ring (0x2400) | FWCCB / tracebuf pointers (concept) | 0x66892e4..0x66893c4 | addresses | [code] |
| +0x40..+0x63 | 0x24 | not written at init | – | – | 0 | [code: no store] |
| +0x64..+0x74 | 5×4 | fwaddr of blocks 0x990, 0x8e0, 0x8c0, 0x938, 0x28 | – | 0x6689b08..b88 | addresses | [code] |
| +0x78..+0x44b | 0x3d4 | zeroed | – | memset 0x6689ae8 | 0 | [code] |
| +0x44c / +0x450 / +0x454 | 3×4 | fwaddr of the 0x84 block, of the fw+0x218 block (size = accel slot 0x990), and of the **config** block | – | 0x6689ba8 / bc8 / be8 | addresses | [code] |
| +0x458 | 4 | fwaddr of fw+0x3f8 (4 × accel-slot-0x760 bytes) | – | 0x6689c08 | address | [code] |
| +0x45c | 4 | fwaddr of the second log buffer (0x36000) | – | 0x6689c28 | address | [code] |
| +0x480 | 4 | fwaddr (region 0x40000000) of the coremem copy at image + fw+0xa6c (= total segment size) | ≈ argv coremem fwaddr | 0x66902b8 | address | [code] |
| +0x484 | 8 | GPU VA of the same copy | ≈ argv coremem devVA | 0x66902dc | VA | [code] |
| +0x48c | 4 | coremem size (fw+0xa60) | – | 0x66902e4 | size | [code] |
| +0x490..+0x148f | 0x1000 | never written by the host | – | – | 0 (firmware-owned [inferred]) | [code: no store] |

**State block (0x2058, uncached; CPU fw+0x2a8, fwaddr fw+0x2b0).** This is a shared page that the host reads and writes at runtime (about 50 sites).

| off | meaning | writer | first boot | tag |
|---|---|---|---|---|
| +0x00 | fw+0x67c (zeroed at 0x6874e0) | 0x6689c34 | 0 | [code] |
| +0x04 | agf_timer_cs: 7 if accel+0xe70 bit 25, else 0 | 0x6689588 | 0 or 7 | [code] |
| +0x08 / +0x0c / +0x10 | cdmpause / memless_render / disable_cs | 0x66895ac / d0 / 0x668960c | 0 | [code] |
| +0x14 | gpu_cl_task_timeout (accel+0x16e8) | 0x6689c9c | 0 | [code] |
| +0x1c | – | 0x6689c38 | 0 | [code] |
| +0x24 | temperature limit | 0x6689880 | 120 | [code] |
| +0x28 / +0x2c | qos enable / period | 0x66897b0 / b4 | 0 / 0 | [code] |
| +0x30 | (accel+0x1a94 & 3) == 0 | 0x6689c94 | 1 [inferred] | [code] |
| +0x1044 / +0x1048 | fwaddr of fw+0x3f0 and fw+0x400 (accel slot 0x760 × 4 / × 8 bytes) | 0x6689c58 / c78 | addresses | [code] |
| +0x2054 | – | 0x668fa3c | 0 | [code] |

**Config block (0x318; CPU fw+0x220, fwaddr fw+0x270)**

| off | meaning | writer | first boot | tag |
|---|---|---|---|---|
| +0x00..+0x2f | 6 u64 heap bases: 0x5_0000_0000, 0x6_…, 0x1_…, 0x1_…, 0x3_…, 0x3_… | 0x66898dc/e8 | constants | [code]; meaning [inferred] |
| +0x30 | u64 from accel+0x1828 object slot 0x88 | 0x6689a2c | VA or 0 | [code] |
| +0x38..+0x1b7 | 2 × (8 × 24 B) copied from accel+0x18f0 and accel+0x19b0 | loop 0x6689a40 | unresolved | [code] |
| +0x1b8 | u64 from accel slot 0x920 | 0x6689a94 | unresolved | [code] |
| +0x1c0..+0x24f | 9 × {u64 phys, u32 fwaddr of its mapping, u32 size}. Index 0 = Fender (0x5000), 2 = AIC SW int, 3 = RGX (0x20000) … | phys/size 0x6689928..; fwaddr 0x668f804..0x668fa14 | per ADT | [code] |
| +0x250 / +0x25c | global flag 0x7a4d882 bit 1 (GPC) / bit 4 | 0x6689aa0 / a8 | 1 / ? | [code] |
| +0x254 | lockup detect (accel+0xe70 bit 6) | 0x6689658 | ? | [code] |
| +0x258 | accel slot 0x7b8 (returns 1) | 0x6689ac0 | 1 | [code] |
| +0x260 / +0x264 / +0x268 | simpal / cache-flush timer / disable ctx-id per DM | | 0 | [code] |
| +0x26c | agf_timeslice | 0x668951c | 1 | [code] |
| +0x270 | – | 0x668f78c | 1 | [code] |
| +0x274 | agf_timer: 200 if flag bit 4, else 1 | 0x6689870 | 200 or 1 | [code] |
| +0x284 | 1 if accel slot 0x7d8 is non-zero | 0x6689538 | ? | [code] |
| +0x288 / +0x28c | usc_exc_state (1, or 2 if accel+0xe70 bit 25) / accel+0xe70 bit 17 | 0x668968c / d8 | 1 / ? | [code] |
| +0x290 / +0x298 | u64 accel+0xd38 / u32 accel+0xd44 | 0x6689ad0 / d8 | unresolved | [code] |
| +0x2e4 / +0x2e8 | AIC SW_SET offset within window 2 / mask | 0x66899e0 / e8 | 0x10 / 0x400 | [code] |
| +0x2ec | 0x1020 & (page − 1) | 0x6689a08 | 0x20 (4 KiB pages) | [code] |
| +0x2f0 | u64 taken from an LDR-stream record, 32-bit halves swapped (0x69008c) | 0x668fa34 | from image | [code] |
| +0x2f8 | u64 from accel slot 0x928 | 0x6689900 | unresolved | [code] |
| +0x300 | u64 boot devVA | 0x668f798 | 0xE1C0000000 | [code]; = `RGX_FIRMWARE_HEAP_BASE` [ddk-claim] |
| +0x308 / +0x30c | PC index / BIF-DM for OUTA1 | 0x668fa2c | 0 / 7 | [code]; = `META_DM_ID` [ddk-claim] |

**Other blocks [code]:**
- 0x990, 0x8e0 and 0x8c0 each start with `{0, self, 0, self+8}` (0x66893f0..0x66894a8). That is two empty TAILQ heads (first = NULL, last = &first) [inferred]. Block 0x8e0 also has +0x778 = 0xffffffff.
- The 0x28 and 0x84 blocks are zeroed (0x66894b4, 0x66894c0).
- The 0x938 block is filled by fw slot 0xa0 (`0x689cc0`: floats 1.0, 100, …). It is not in the boot sequence, and when it is called is unresolved.

**Rings [code]:**
- **Control** (0x20 bytes): u32 consumer read index at +0, u32 producer write index at +0x10, both `& 0xff`, all zeroed before boot. The log control is 4 such pairs (0x80 bytes).
- **Host→firmware push** (`0x6915cc`): the ring is full if `rd == (wr + 1) & 0xff`. The host copies a 20-byte `AGFIAcceleratorRingEntry` to `buf + wr*20`, issues a DMB, sets `wr = (wr + 1) & 0xff`, then writes MTS_SCHEDULE.
- **Event record** (0x2c bytes): +0 u32 type (0..8).
  - Type 0 (alive): +4 = the META PC of the firmware's "waiting for BG kick" idle loop; the host prints it as such at `0x691b40`, and it is not validated.
  - Type 1: four u32 completion masks at +4, +8, +0xc, +0x10.
  - Type 6: META-halt path.
  - The host consumes records at index `rd`, then advances `rd` (`0x668caa4`).

## 4. Minimum for a first "alive" record (Linux)

1. **Firmware image buffer** at GPU VA 0xE1C0000000 (context 0, catalogue in BIF_CAT_BASE0), laid out as seg2 (page-aligned) | seg0 | seg1 | seg3 | coremem copy, as in `0x668fd58`.
   - At image +0x200: the segment tuples for n = 0, 1, 3, then `0, 0`, then **one word = fwaddr(image + size(seg2) − 8)**, which is 0xC0000FF8 for a 4 KiB seg2.
   - At image + size(seg2) − 8: **{fwaddr(root), fwaddr(state)}**.
2. **Root** (zero-filled): +0x00..+0x3c ring addresses, +0x64..+0x74, +0x44c..+0x45c, +0x480/+0x484/+0x48c as in §3. Every referenced block must be allocated in the firmware heap and zeroed.
3. **State** (zero-filled): +0x24 = 120, +0x30 = 1, +0x1044/+0x1048 addresses. Everything else 0.
4. **Config**: +0x00..+0x2f constants, the 9 MMIO windows (phys, fwaddr of a GPU-MMU mapping of that MMIO page, size), +0x250 = 1, +0x258 = 1, +0x26c = 1, +0x270 = 1, +0x274 = 1 or 200, +0x288 = 1, +0x2e4 = 0x10, +0x2e8 = 0x400, +0x2ec = 0x20, +0x2f0 from the LDR, +0x300 = 0xE1C0000000, +0x30c = 7.
5. **Rings**: all control indices 0. Allocate the event ring buffer (0x2c00); allocate the other buffers but they can stay empty. No kick is needed: Apple calls `waitForFWAlive` right after the GPC power-up, with no MTS write in between.
6. **Detection**: poll event ctl +0x10 != +0 (or take AIC IRQ 138 and clear 0x400 at SW_CLR), then check that record[rd].type == 0.

**Unresolved:**
- The accel+0xe70 feature bits and global flag bit 4 (they drive state +0x04 and config +0x254/+0x274/+0x288/+0x28c).
- Sizes from accel slots 0x760 and 0x990.
- Config +0x30, +0x38..+0x1b7, +0x1b8, +0x290..+0x29b and +0x2f8, and the LDR record type behind +0x2f0.
- The contents of the 0x938 block and when it is filled.
- Whether the firmware checks any of these before it sends alive.
- Whether the root region beyond +0x490 must be zero.
- The meaning of event types 2–8.

## 5. Apple-only (no DDK counterpart)

- Root, state and config layouts.
- The MMIO-window ("Firmware PIO") table and the AIC software-interrupt doorbell.
- Fixed 256-entry rings with `{rd@0, wr@0x10}` control.
- 20-byte ring entries and 44-byte event records.
- The type-0 alive record.
- The 4-channel log ring, and FWTRACE as 0x2c-byte records.
- Fender/GPC power-up as the release step.
- The MTS DM numbering 0x10/0x11/0x12.
- The two-thread firmware (`g4g_a0_t0/t1`).

The DDK's `RGXFWIF_INIT`/KCCB/FWCCB/tracebuf code cannot be reused. What does carry over from DDK 1.3–1.5:
- RGXStart's reset and boot staging.
- The META segment/bootloader conventions (+0x200 list, terminator, argument word, segment IDs, DM 7, 0xE1C0000000).
- The LDR format.
