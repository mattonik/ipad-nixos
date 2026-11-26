# Research request 18 result: what Orchard's A8/A9 driver does that our J81 boot does not (19H394)

A reference-driver comparison. Sources:
- Orchard's reconstructed `pvr_apple_s8003.c`, sha256 `0efc2a93…`, as pinned in request 9. It contains the A9 (s8003) path and the A8 (t7000) path. "S:n" means its line n.
- Orchard's public docs in `context/orchard-public/`.
- The 19H394 J81 AGXG4G kext, for what Apple's J81 host itself does.

Tags:
- **orchard**: read in Orchard's sources;
- **code**: the J81 kext;
- **adt**;
- **capture**: our runs and builder;
- **source**: upstream;
- **inferred**.

There is no Apple binary content beyond addresses, offsets, field names and small constants.

## Short answer

Four host-side differences stand out. None needs a new register write; all are in the memory image or the page tables.

1. **The firmware's pages bypass the SLC on A8 and are PM/META-protected** (`T7000_FW_FLAGS = BYPASS_DEVICE_CACHE | PM_FW_PROTECT`, S:3406, S:3566–3573). Ours are valid-only, so every GPU write to the heap goes through the SLC, a write-back cache.
   - Our host reads uncached DRAM. The firmware is idle in its scheduler loop, and Orchard says alive is posted "each time its scheduler runs" (S:213).
   - So **the alive record may already exist but be sitting in the SLC** (inferred).
   - E0 tests this read-only, plus one SLC flush, before any rebuild.
2. **POLICY (the `0x938` block) is filled on the boot path.** Requests 4 and 14 had this wrong. The J81 kext calls fw slot `0xa0` (`0x6689cc0`) at the end of shared-memory init (`0x6689ca4`). It writes:
   - `+0x10` = 1.0f, `+0x28` = `0x1_00000001`, `+0x38` = 100;
   - `+0x8f8` = a timestamp;
   - `+0x6fc`/`+0x7cc` = state count × 100;
   - a set of governor floats.

   Orchard's A9 driver fills the same fields before boot. Ours is all zero.
3. **The perf-state table in config is empty.**
   - `+0x29c` = `gpu-num-perf-states` (4);
   - `+0x2a0` = `perf-state-count` (16);
   - `+0x2a4..+0x2e3` = 16 MHz values (0, 365, 450, 500, 550, 182, 225, 250, 275, then 0).

   All are written by the J81 kext (code). Our captured ADT has these properties at 0, so our image hands the firmware an empty table. Apple's kext refuses to start in that case ("Failed to find valid GPU and GPU_SRAM perf state configuration").
4. **The hardware objects are absent.** On A8 Orchard puts a YUV CSC buffer, a BRN44455 object, the BorderColorTable and a FenceBuffer at `0x8_00000000 + {0, 0x4000, 0x8000, 0x10000}`, plain flags. J81's kext creates the same objects and names them in config `+0x30`, `+0x1b8`, `+0x2f8` and the fw `+0x218` block. Ours are absent and their fields zero.

There is no separate timer-period field on J81. The A8's `+0x280 = 24000` has no counterpart in the 19H394 kext: no constant, no store in `+0x278..+0x280`. The RGX `0x1740`/`0x1790`/`0x17a0`/`0x17a8` writes are not a host step on J81; Orchard's own code says the firmware loads MCU_FENCE itself.

## Q1: the sequences side by side (t1)

Everything Orchard's A9 and A8 paths do from "image loaded" to "alive", marked present or missing against our run:
- **Present:** register windows, INIT ring layout, channel heads and `+0x778`, CONTROL fields, boot stream and release, alive polling.
- **Missing:**
  - PTE flags for firmware memory;
  - POLICY;
  - the perf table;
  - the hardware objects;
  - the plain zero page at GPU VA 0 (low priority, since BIF fault stayed 0).

The A9-only items don't apply to J81: SLC3 and scramble, Fender `0x2010`/`0x2014`, the CR `0xe160` spare page, CONTROL `+0x104c`.

## Q2: the hardware objects (t2)

There are four `0x4000` pages, mapped valid + SLC bypass only. Any PM/META-protect flag and "the firmware never posts its alive event" (S:3386–3397):
- **YUV CSC buffer:** `0x8_00000000`, config `+0x30`.
- **BRN44455:** `0x8_00004000`, fw `+0x218` block `+0`.
- **BorderColorTable:** `0x8_00008000`, config `+0x1b8`. Its 0x800 bytes are kext data at `0x7a4c4f0`; extract them locally from your own kernelcache and don't ship them.
- **FenceBuffer:** `0x8_00010000`, config `+0x2f8` and fw `+0x218` block `+8`.

Orchard zeroes all four apart from the border table. The two CSC blocks at config `+0x38..+0x1b7` are J81-specific (2 × `0xc0`), so leave them zero for a first boot (inferred).

## Q3: timer and numeric inputs (t3)

The perf table and POLICY values are listed with their code addresses. For `+0x8f8`, use the AIC timebase the firmware reads (window 1, `+0x20`); Apple uses `mach_absolute_time`, which runs at 24 MHz too. The rest of POLICY (governor floats from the ADT's `gpu-pwr-*`/`gpu-perf-*` properties and a 0x160-byte copy) is not decoded. Orchard's A9 reached alive with only the fields listed plus perf pins.

## Q4: other gates

- **No interrupt order and no kick:** Orchard polls the ring with no IRQ and no doorbell before alive, the same as Apple.
- **BIF:** `BIF_CAT_BASE0` through the stream, as ours.
- **SLC:** the J81 SLC pair, as ours.
- **Thread 1:** Orchard's A9 path does not start it; the firmware does. We had to start it ourselves (runs 61–64), which means our firmware never got far enough to.
- **The real gate candidates** are the mapping flags and the empty perf and POLICY inputs above.

## Q5: ranked boots (t4)

0. **E0, read-only first:** read the AIC SW-int word for IRQ 138 (`0x20e104010` and the state word, bit 10). Then flush the SLC: RGX `0x3818 = 0x1` (SLC_CTRL_FLUSH_INVAL ALL), poll `0x3898 & 0xff == 0xff`, and re-read the event write index and the heap. If the index moves, alive was there all along, and the fix is E1. The AIC state-word offset comes from the AIC1 layout (inferred).
1. **E1:** PTEs for the heap/root/shared = valid | bit 3 | bit 62; for the window pages = valid | bit 3.
2. **E2:** the perf table in config `+0x29c..+0x2e3`.
3. **E3:** the POLICY minimum.
4. **E4:** the four hardware objects and their config/block fields.

Each goes on its own boot after E0.

## Not resolved

- How the J81 kext turns map option 7 into PTE bits. Orchard's A8 reading of bypass + protect is the best evidence.
- The remaining POLICY governor fields.
- Whether J81's firmware reads the CSC blocks before alive.

## Files

- `t1-sequence-compare.tsv`: Q1, Orchard's A8/A9 steps against the J81 kext and our run, marked present or missing.
- `t2-hardware-objects.tsv`: Q2, the four objects with VA, size, flags, contents and naming fields.
- `t3-perf-fields.tsv`: Q3, the perf table and POLICY values for J81.
- `t4-next-boots.tsv`: Q5, the ranked boots.
- `SHA256SUMS`.
