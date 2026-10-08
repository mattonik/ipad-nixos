# Live RAM device-state analysis: why the firmware ignores the doorbell

Static, offline analysis of the live RAM image from the stalled device (run 14, T1 hold) against the firmware image
(`rieslinga.trx`, base 0x180000, Thumb-2, Ghidra). No hardware was touched. Private bytes (RAM, NVRAM values, decompiler
output) were read but are not reproduced here; only addresses, field names and short values are quoted.

## Result in one paragraph

The firmware never enabled the PCIe2 core interrupt. The enable lives in the `pciemsgbuf0` device's `open()` op
(`FUN_001dfd48` -> `FUN_00184c38`), which the firmware's init (`FUN_001dfee8`) calls only after the **`wl` (D11) device has
been added successfully**. The `wl` probe (`FUN_001e323c` -> `wlc_attach` `FUN_001e482c` -> bmac attach `FUN_001e74ac`) ran, got
as far as looking up the NVRAM variable **`macaddr`**, failed, cleaned up and returned NULL, silently. The NVRAM the host
downloads has **no `macaddr` line**. So `open()` never ran, the PCIe2 IntMask stayed 0 (as measured), the doorbell bit
(IntStatus bit 16) stays pending, and no ring is ever read. This is not a doorbell, DS or host-ready gate in the msgbuf code.

## 1. The pciedev device structure (live)

- `pciemsgbuf0` descriptor at 0x1dbd28 (name, ops 0x1dbcd4, devid 0x43ff, handle 0x23bc84). Ops table: probe 0x1dfd6c,
  **open 0x1dfd48**, close 0x1dfd34, xmit 0x186940, ioctl 0x1868f0, txavail/poll 0x1868a8, **isr 0x1868d0**.
- Big device struct **P = 0x23aa8c** (heap block header 0x23aa84 size 0x11f0 = the 0x11f0 alloc in `FUN_001df7f4`).
  Found via `*0x1dd74c` (0x1dd750 = device count 1). Fields: +0x04 PCIe2 core rev 0xb, +0x08 osh 0x23bcdc, +0x0c sih
  0x239b34, +0x10 bus object 0x2347c0, +0x14 PCIe2 regs 0x18003000, +0x18 shared struct 0x1dd6c8, +0x7a4/+0x7a8 host-to-dev /
  dev-to-host mailbox data words 0x23aa7c / 0x23aa80 (both 0), ring descriptors from +0x8d0 ("h2dctl", "h2drx", "d2hctl",
  "d2htx", "d2hrx" strings in the heap), ring index arrays 0x23a914.. as published.
- ISR list (head `*0x1806dc`): node 0x22fd08 {fn 0x1868d1, ctx 0x1dbd28, mask 8} = the pciedev ISR is registered; node 0x23da40
  {fn 0x9a59 ROM, mask 1} = ChipCommon. **No D11/wl node.**
- ISR `FUN_001868d0` -> `FUN_00184b78`: `status = P[+0x62c] & PCIe2[0x20]; P[+0x634] = status`, then DPC `FUN_00185d54`. At the tail
  it re-enables with `PCIe2[0x24] |= P[+0x628]`.
- **Live values: P[+0x628] = P[+0x62c] = 0, P[+0x634] = 0, P[+0x11b0] = P[+0x11b4] = 0, P[+0x704] = 0, P[+0xd19] = 0,
  P[+0x7b0] = 0**, mailbox words 0, power-state byte P[+0x7ac] = 0, state-machine state P[+0xd34] = 0 with an empty history
  (P[+0x10b8] = 0). Combined with the hardware read (IntStatus 0x20 = 0x00010000, IntMask 0x24 = 0): the ISR's software mask is
  0, so even the hardware status bit would be ANDed away.
- The only code that sets P[+0x62c] initially is `FUN_00184c38` (value `0x20300 | 0x010100c0` = 0x010303c0, i.e. doorbell bit 16,
  mailbox bits 8/9 and 17, plus bits 6/7/24; later narrowed to 0x300 or 0x20000 by `FUN_00185a78` once the host's doorbell kind
  is seen). `FUN_00184c38` also sets P[+0x704] = 1, P[+0x7b0] = 0x80, P[+0xd19] = 1, `*(P+0x18) |= 0x10000` (shared flags: live
  value is still 0x5, bit 16 clear) and calls `FUN_00184c08` which writes the hardware `IntMask` (core +0x24) and the DMA
  interrupt enables (+0x194, +0x19c). Every one of these side effects is absent in the live image: `FUN_00184c38` never ran.
- Callers of `FUN_00184c38`: `FUN_001dfd48` (pciemsgbuf open) and `FUN_00184cf4` (DPC handler for status bit 6, a PERST-style
  event; unreachable while the mask is 0). The DS / host-ready state machine (table at 0x1dbb18, state P[+0xd34], events 0/1 from the
  DEVICE_WAKE GPIO ISR `FUN_00185f08`, 2 from status bit 6, 5/6 from mailbox data bits 1/2, 7 from a control message) is idle
  in state 0 and does not gate ring service; it only toggles `chipcommon+0x1e0` bit 4 and posts D2H mailbox data (this is
  the "isr #1 / mailbox 0x100" seen in earlier runs when DEVICE_WAKE was low).

## 2. Why `open()` was never called

`FUN_001dfee8` (RTE init, in the non-reclaimed RAM image) does, in order:

1. add device `pciemsgbuf0` (core 0x83c, devid 0x43ff) -> ok (sets global `*0x180730 = 0x1dbd00`);
2. devid from NVRAM `devid` (stack residue shows 0x43a3), then add device `wl` (descriptor 0x1dbd90, core 0x812) via
   `FUN_001de2cc` -> `wl_probe` (ops[0] = 0x1e323d);
3. **only if both succeeded**: bind (`FUN_00186a06`, links the two in the bus object at 0x2347c0, slots +0x38/+0x3c) and then
   call `open()` of the pciedev ops.

Live proof the `wl` add failed: descriptor 0x1dbd90 still has devid and handle fields zero (they are written only on success,
`FUN_001de2cc`); the bus object slots 0x2347f8/0x2347fc are 0 (not bound); the device list `*0x1dd6a8` -> 0x1dbd28 has no next.

Live proof it failed rather than hung or ran out of memory:
- the allocator's failure counter (`*0x1806a4`) is 0 and 314 KB of heap is free, so no OOM;
- the 0xac-byte `wl_info` block that `wl_probe` allocates is on the free list (0x22fc4c) = freed by the probe's error cleanup;
- stale stack frames (not overwritten) show the failure tail: return addresses 0x1e50f9 (wlc_attach error exit calling
  `wlc_detach` 0x1e46a4), 0x1e481d (detach -> free 0x1e5a0c), 0x1e5a61, and the wl_probe entry 0x1e323d / desc pointer.

Where it failed: stack residue at 0x23fe24 is the return address **0x1e7a6f**, the instruction after `bl 0x1e6d68` in
`FUN_001e74ac` (the bmac attach). `0x1e6d68` is `getvar(vars, key)` with key pointer 0x1f20f9, and the same pointer is
stale on the stack at 0x23fe0c; the string at that address in the firmware image is `macaddr`. The code right after it:
NULL -> return **0x15**; else parse as an Ethernet address and reject all-zero / multicast -> return **0x16**; success only
for a valid unicast address. Other failure codes of that function (0xc..0x13, 0x19) come from chip/core checks earlier in
the same function that the residue shows were passed.

NVRAM evidence: the staged `P-rieslinga_M-CIDR_V-u__m-2.1.txt` has 156 keys including `devid`, `boardtype`, `sromrev`, but
**no `macaddr`**; a search of the live RAM finds no `macaddr=` text (only the code string `pfn_macaddr`), so no OTP/SROM-derived
`macaddr` variable exists either. (Apple's host supplies the MAC at run time; Linux brcmfmac does not add one before boot.)

## 3. Ranked hypotheses

1. **Missing `macaddr` makes `wl` attach fail, so pciedev `open()` (interrupt enable) never runs.** Evidence: all of section 2,
   plus IntMask 0 / IntStatus bit 16 pending / software masks 0. Strong; confidence high that the `wl` add fails, fairly high that
   `macaddr` is the reason (the residue pins the failing step to the macaddr lookup but the 0x15/0x16 return itself is not
   observable).
2. `wl` attach fails for another reason after a macaddr fix (the bmac attach has later steps; NVRAM-dependent PHY/board checks
   in `wlc_attach` after it). Same live signature; distinguishable by re-reading the signature below after fix 1.
3. Host-ready / DS / DEVICE_WAKE gating: **rejected as the cause.** The state machine is idle, and nothing in the doorbell path
   consults a host-ready flag; those earlier runs (DS request, config ACK) did not change the outcome.
4. Ring-table, DMA-model, scratch/ring-update buffer differences: already refuted by runs 10-13; consistent with this finding
   (the rings are never even looked at).

Unknown: why the firmware prints nothing on `wl` failure (its error prints are gated by a runtime message level); the exact
0x15 vs 0x16 code; whether further `wl` init (CLM/TxCap/ucode are loaded later by the host) will pass.

## 4. Testable host-side actions

A. **Add a valid unicast `macaddr=xx:xx:xx:xx:xx:xx` line to the NVRAM the driver downloads** (staged
   `brcm/brcmfmac4350c2-pcie.txt`, built by `boot/assemble_private_wifi_payload.py`; use a locally administered unicast value
   such as one starting 02:, or the iPad's real address from the device tree). Re-run the T1 hold payload. Success signature
   with the existing query interface (`tcm` reads of absolute addresses, after the one-line bounds fix noted in run 13):
   - firmware console gains `wl` output (banner) after the TCAM line;
   - 0x1dbda4 = devid, 0x1dbda8 = non-zero handle (wl descriptor registered);
   - shared flags word at 0x1dd6c8 gains bit 16 (0x10005);
   - P[+0x62c] at 0x23b0b8 = 0x010303c0 (then 0x010100c0|0x300 or |0x20000 after the first doorbell);
   - PCIe2 IntMask (0x24) non-zero, IntStatus bit 16 clears, device read indices move.
B. Cheap pre-check without any change: read TCM 0x23b0b8 (P+0x62c), 0x1dbda8 and 0x1dd6c8 on a booted device; the failing signature is
   0, 0 and 0x5. Also optionally use the gated `rom` read to confirm the three `macaddr` return codes in 0x1e74ac context (not required).
C. If A does not change the signature, try the next `wl`-attach suspects in order by dumping the stale-stack and `wl` descriptor
   again: the bmac attach error return is not stored, but the residue position of the deepest remaining frame names the last
   call made (record 0x23fdc0..0x23fe40 for each experiment).
D. Not recommended: forcing IntMask (core +0x24) and the TCM shadows 0x23b0b4/0x23b0b8 from the host. It would wake the ISR
   and DPC but the control path needs the (absent) `wl` device to answer ioctls, and the DMA interrupt enables and `open()` state
   would be missing, so it proves little and risks a hang.

## 5. Method notes (reproducible, nothing private stored here)

Device struct found from the init code's global (`*0x1dd74c`), cross-checked with the shared struct at 0x1dd6c8 (+0x54 holds
the struct pointer), mailbox words 0x23aa7c/0x23aa80 (P+0x7a4/+0x7a8) and ring-memory tables (P+0x8d0.. blocks pointing at
0x23a644.., 0x23a914.., 0x23aa64..). Heap walked from 0x220c38 (block header = size, next); allocator counters at 0x1806a4 (fail),
0x1806c0 (bytes), 0x1806e4, 0x1dd624 (high water 0x21678). Stack: filled with `KATS` pattern 0x23df6c..0x23fb88 (high water ~1.1 KB used).
The chip ROM dump was not needed: all decisive logic is in the RAM image; ROM calls used were small thunks.
