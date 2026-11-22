# Request 9: Orchard A8 GPU work (PR #196, kit 4) reconciled with J81

Offline analysis only. No device was used, nothing from the third-party sources was executed, and no Apple firmware was fetched. All source pins are in `SOURCES.tsv`.

Evidence tags:
- **[code-orchard]**: read in their code. `S:<line>` is a line in `pvr_apple_s8003.c`, reconstructed by applying the PR's 73 GPU patches. The method and the file's hash are in `SOURCES.tsv`.
- **[code-j81]**: read in our 19H394 kernel. Addresses omit the `0xfffffff0` prefix.
- **[capture]**: observed on J81.
- **[inferred]**: our inference.
- **[claim]**: stated by the third party.

## Headline

Orchard's A8 driver does not contradict request 8. Apple's interface still matches no Imagination DDK structure. Instead, the driver is a public, working decode of Apple's own interface, and it was built for two generations:
- the A8 / iOS 12.4 layout;
- the A9 / iPadOS 16.7.10 layout.

J81 on iPadOS 15.8.5 is a hybrid of the two:
- **Like the A8:** the boot path, the Fender boot stream, the boot-list encoding, the head of the PLATFORM (config) block, 4 KiB pages and 8 VM slots.
- **Like the A9:** the sizes and field offsets of the root (INIT), state (CONTROL), channel and POLICY blocks, the 0x20 ring-control lanes and the core-memory handover.

Most of request 8's open fields now have names. The driver also names the bit our identity work kept tripping over: PMGR `+0x5004` bit 30 is the GPU PLL-lock bit, and the A8 driver never touches a Rogue register while it is clear.

## Findings

**T1. Firmware (located; strong).**
- What `extract-fw.py` extracts:
  - `AGXFirmwareKextG4P`'s META LDR, found by magic `0x01aa5500` and an L1/L2 length walk, with the iOS 12.4 hash pinned (`extract-fw.py:18-98`);
  - the kext's 0x800-byte BorderColorTable, which the A8 variant refuses to probe without (S:5993-6016).
- How the driver uses it [code-orchard]:
  - The patched powervr driver runs Apple's LDR byte for byte and fills Apple's interface blocks. There is no Imagination firmware and no shim.
  - "Same family as the A9" means one chip file. The A8 is a `struct s8003_variant` with its own sizes and boot functions; the drain, alive wait, layout planner and job streams are shared (S:239-282, S:6028, S:6067).
- Our layout tool versus theirs:
  - The A8 unpack and boot list match `j81_meta_ldr_layout.py` exactly: order [2,0,1,3], the list at `+0x200`, `BASE|0xf02`, `LIMIT = max(size−1, 0xfff)`, `OUTA1 = 7<<8 | VA>>32`, 27 config writes, `0,0`, then `0xc0000ff8`, and `{INIT, CONTROL}` at `+0xff8`. Our names root and state are their INIT and CONTROL.
  - The address translator is identical, including the special 16 MiB uncached window at `0xe1c3200000`, which is their root memory (S:545-550).
  - The A8 image has no core memory; J81 has one (0x52b4 at `0x80000080`), as the A9 does.
- **Resolved:** config `+0x2f0`/`+0x2f4` is thread 1's `{pc, sp}`. J81 keeps the START_THREADS entry whose thread number is 1 and swaps the words with `rev64` before storing them (`0x6690078`–`0x669008c`) [code-j81]. This is the same rule as the A8 driver (S:3477-3491). For 19H394 the values are `0x20000000` and `0x8000b3c8`. See `t1-image-boot.tsv`.

**T2. Firmware interface (mostly located; strong for INIT/CONTROL, medium for PLATFORM).**
- The A9 object table (S:553-585) has exactly J81's sizes: INIT 0x1490, channels 0x990/0x8e0/0x8c0, POLICY 0x938, 0x4b 0x28, 0x4e 0x84, CONTROL 0x2058, event ring 0x2c00, logs 0xb000 and 0x36000.
- The A9 driver's INIT and CONTROL fill uses J81's offsets: `+0x64`, `+0x44c`, `+0x480`, CONTROL `+0x24 = 120`, `+0x30 = 1`, `+0x1044`, `+0x1048`, and channel 1 `+0x778 = 0xffffffff` (S:773-870).
- Request 8's "unresolved blocks", now named:
  - 0x990/0x8e0/0x8c0 are the TA, 3D and compute channels.
  - 0x938 is POLICY, the power-governor record. Both drivers fill it **before** boot.
  - 0x28 is object 0x4b, the firmware's lockup state.
  - fw+0x218 is object 0x4c, the BRN44455 and FenceBuffer addresses. J81 sizes it 0x10, because slot 0x990 returns 16 [code-j81].
- Slot 0x760 returns 8 [code-j81]: J81 has 8 VM slots like the A8, so TAG_HOST and TAG_SEEN are 0x20 bytes and MMU_ROOT is 0x40.
- PLATFORM (our config, 0x318) follows the A8's head layout:
  - the six heap bases (identical values);
  - `+0x30`: YUV CSC buffer address;
  - `+0x38`: two CSC blocks (0xc0 bytes each on J81, 0xa8 on the A8);
  - `+0x1b8`: BorderColorTable address. Slot 0x920 resolves to accel+0x1c18, which is filled from 0x800 bytes of kext data [code-j81].
  - `+0x1c0`: the window table. Its order (Fender, AIC time, AIC SW set, RGX) matches the A8's, which fills only 4 windows.
  - `+0x250` "Fender boot", `+0x254` lockup detection, `+0x258` PIO supported, all identical.
- PLATFORM's tail matches with a 0x1b0 shift:
  - `+0x2e4`/`+0x2e8`/`+0x2ec`: interrupt word and bit, and the AIC time offset;
  - `+0x2f0`: thread pc/sp;
  - `+0x2f8`: FenceBuffer address. Slot 0x928 resolves to accel+0x1c20 [code-j81].
  - `+0x300` image VA and `+0x308` `0x7_00000000`.
- J81 reserves the A8's hardware-object window, `0x8_00000000` (4 MiB) in each GART (`0x6684d94`, `0x6685510`), and creates the same named objects [code-j81].
- Root `+0x490`–`+0x148f` is never written by the A9 driver, and the A9 reaches alive. So zero is sufficient there [code-orchard + claim; inferred for J81].
- Events:
  - Type 4 is lockup recovery; its layout was decoded from the A8 firmware (S:5458-5491).
  - Types 2, 3, 5, 7 and 8 are only logged, by them and by us.
- Neither driver shows the firmware checking anything before alive, beyond the following:
  - the blocks above are filled;
  - a zeroed page is mapped at GPU VA 0;
  - the hardware objects are mapped without PM/META-protect flags. The A8 driver's note claims alive never comes otherwise.

See `t2-fwif-map.tsv`.

**T3. Boot, power and Fender (located; strong).**
- The A8 boot stream (S:4191-4200) has the same registers, order and encoding as our 30-word J81 list plus terminator. Only the SLC value differs: A8 `0x200001`, J81 `0x0003550000300001`.
- Their sequence around the stream matches what we traced in the J81 kext:
  - empty stream and `+0 = 0x40000000`, then state 1, then ID, then state 0;
  - Fender `+0x10` cleared, `+0 = 0x40000000`, the stream, `+0x20000 = 0`, then `0x11`;
  - poll memory for alive;
  - the kick: `+0x14 = 7`, a state read, a SNOOP check if in state 0, then `MTS_SCHEDULE`.
- Our unresolved state-0 helper `0x68ea90` corresponds to the A8 kext's firmware restart [inferred].
- **Their code supports:**
  - F1: their ID read is exactly a 0→1→0 cycle with an empty stream.
  - F3's order and its no-kick alive wait.
  - The replay assumption behind F2 [claim + code]. On the A8 the reset release exists only in the stream, and the firmware runs.
- **Their code contradicts:**
  - Our recovery advice. On no-alive they touch nothing again and keep the memory until reboot, because Apple panics there.
  - Our 10 s alive window. They use 3 s.
- Power and fabric:
  - The A8 order is: MISC_ACG `+0x32000`, a VM_CTL `+0x23000` check, SOC_TVM `+0x2d000`, a 100 ms settle, PS `+0x20320` through Apple's writer, bridge `+0x18 = 0x80010004` plus 32 words, then Fender.
  - These are the same PMGR offsets as our J81 recipe.
  - The A8 needs no DWI handling, because the backlight keeps `ps_dwi` on. J81 needs DWI, and Orchard's `t7001/0012` (always-on) exists for that reason.
- **The PLL gate.** `T7000_PMGR_PLL5 +0x5004 bit 30` is documented as "the GPU's PLL: bit 30 locked". Every Rogue access is gated on Fender state 1 plus that bit, because an unlocked access "hung the whole SoC" (S:3862-3878) [claim].
  - That is our page-5 bit: it was 0 on every hung J81 read and `0x40000000` on iOS and on the DWI-on identity runs [capture].
  - Our earlier note said writing bit 30 is not justified. It now reads as a status bit (PLL locked), which supports not writing it.
- Omitting `power-domains` (patch 0066):
  - The A8 driver drives `+0x20320` with Apple's writer instead of genpd. It sets AUTO_PM bit 28, clears the history bits 9:8, bit 30 and DEV_DISABLE bit 10 (S:3917-3955).
  - Our J81 genpd activation leaves `0x3ff` (history set, no bit 28); iOS read the same at the poll.
  - So this is a refinement worth a read-only check (P0 in the step list), not a blocker: identity already works with the genpd path.

See `t3-power-boot-order.tsv`.

**T4. A8 versus A8X (located; strong).**
- **Carry over:** the register bases (RGX, Fender, PMGR, bridges); the PMGR offsets and the PLL bit; the heap bases; page size; slot count; the 0x4c size; the hardware-object reservation; the AIC windows and the doorbell encoding; the boot-list rules.
- **Re-derive for J81:**
  - the ID constants (A8 checks `0x00030a00`; J81 is `0x00070500`/`0x011b0803`);
  - cluster count (4 versus 8);
  - the bridge table (33 versus 66 stores);
  - clocks and volts;
  - the location of the PLATFORM perf and chip-info fields (J81's 0x318 block has no room for the A8's tables at `+0x300`..`+0x374`);
  - the CSC and border tables;
  - the SLC boot value;
  - the INIT/CONTROL/POLICY layouts (use the A9's);
  - the ring-control size (0x20, not 0x30);
  - the image layout (our tool);
  - the VM heap split.

See `t4-chip-values.tsv`.

**T5. Risk and reuse.**
- **License:** all Apple glue files are `GPL-2.0-only OR MIT`. The repository is GPL-2.0-or-later; Mesa is MIT.
- **Read first:** 0063 (variant table), 0067 (A8 boot and power), 0020 (A9 boot: J81's interface sizes), 0017 (LDR placement), 0066, and `devices/t7001/0012`.
- **Copy:** the `s8003_variant` shape, the object-packing rule (64-byte aligned, in Apple's order), and the A9 INIT/CONTROL fill. Do not copy the A8's values.
- **Cautions:**
  - Tested only on the iPod.
  - The PR's own kernel is "built but not yet flown".
  - The A9 and A10 paths were not retested after 0063–0073.
  - `a8_joint` and 0073 are experimental.
  - The Mesa PR is open, and kit 4 was built from an older Mesa commit than its head.
  - Many constants come from live iOS memory dumps.
  - The patches are tagged "Assisted-by: LLM". Treat the comments as one reader's interpretation.
- Nothing from the kit should run on J81.

See `t5-reuse.tsv`.

**T6. Revised steps.** See `t6-steps.tsv`.
- **New:**
  - M4: offline confirmation of the remaining J81 field sources.
  - P0: a read-only guard. Never touch RGX unless Fender state is 1 and `+0x5004` bit 30 is set.
  - A no-alive policy: leave everything and reboot.
  - F4: drain the rings after alive.
- **Changed:**
  - M1 adds the zero page at VA 0, the hardware objects at `0x8_00000000` and fixed firmware VAs.
  - M2 names every block and fills POLICY before boot.
  - M3 resolves `+0x30`, `+0x1b8`, `+0x2f0` and `+0x2f8`, and uses 4 windows.
  - F3 clears Fender `+0x10` before the stream and polls memory for 3 s.
  - F2 becomes optional.
- **Smallest path to alive:** identity recipe with DWI on → M0–M4 offline → F1 → F3 → F4.
- F3's memory contents are now specified field by field. The fields still marked [inferred] are the POLICY offsets, the PLATFORM flags `+0x26c`..`+0x28c` and the perf pins; M4 must confirm them.

## Not resolved

- Config `+0x290`–`+0x29b` and `+0x310`–`+0x317`, and the exact meaning of `+0x26c`..`+0x28c` beyond the −8 shift inferred against the A8.
- Where J81 keeps the perf tables and chip info that the A8 holds in PLATFORM `+0x300`..`+0x374`, and the CONTROL `+0x1028`..`+0x1040` perf pins.
- The offsets of each hardware object inside `0x8_00000000`, the VM heap split, the first host VM slot, and which J81 objects the kext puts in the uncached window.
- Event types 2, 3, 5, 7 and 8, and whether J81's type 4 has the A8 layout.
- Whether J81 iOS sets PS bit 28 after power-on, and the meaning of Fender `+0` bit 29 (SNOOP is read, never written, in both drivers).
- Whether the firmware validates any field before alive; neither driver tests this.
- Whether a Fender replay is proven on J81; F2 is still the cheapest proof.

## Files

- `RESULT.md`
- `SOURCES.tsv`
- `t1-image-boot.tsv`
- `t2-fwif-map.tsv`
- `t3-power-boot-order.tsv`
- `t4-chip-values.tsv`
- `t5-reuse.tsv`
- `t6-steps.tsv`
- `SHA256SUMS`

No firmware bytes and no third-party code are included; paths and line numbers are cited instead.
