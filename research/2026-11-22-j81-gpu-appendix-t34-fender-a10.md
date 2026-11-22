# T3/T4: J81 Fender (GPC) and what the A10 notes imply

Tags: [code] read from J81 19H394 AGXG4G disassembly; [a10-claim+code] OrchardLinux A10 claim that J81 code confirms; [a10-claim] A10-only, not checked on J81; [inferred]; [adt] J81 device tree. Addresses are `0xfffffff00…`-shortened.

## T3. Fender on J81

**Correction to RESULT.md.** The "mailbox" is not a register at all. It is Apple's **Fender ConfigRAM**: an array of 32-bit words at **Fender+0x10000** that the host fills sequentially. Fender object slot `0xb0` is not a wait. It is `incrementConfigRAMOffset` (`obj+0x20 += 4`), and no word is polled. [code] The A10 notes name the same methods (`initConfigRAMOffset`, `incrementConfigRAMOffset`, `terminateConfigRAMSequence`, `writeConfigRAMCommand32/64`). They are panic stubs on G9P, but J81 implements them (`agxk_fender_meta.cpp`). [a10-claim+code]

**Object** (40 bytes, vtable `6f2fee8`, created by accel `+0x850` = `669aff4`, stored at `fw+0x160`): `+0x8` last perf state, `+0xc` "powered" byte, `+0x10` Fender VA, `+0x18` accel, `+0x20` ConfigRAM write offset. Slot 0 (`669bbac`, called at `6687480` with the VA of global map `7a4d8a8`) stores VA and accel, then calls slot `0xa8`, which sets `+0x20 = 0x10000`. [code] The Fender vtable indices 0, 3, 4, 5, 8 and 10 have the same function on A10 and J81. [a10-claim+code]

### Register table (names are Apple's strings, from dump slot `0x40` = `669bbd8`)

| Fender off | Apple name | Host access (J81) | Meaning / evidence | Tag |
|---|---|---|---|---|
| +0x0 | `AGX_CR_FNDR_TIMER_SLEEP_CONTROL` | W `0x40000000` (early init `683990`; slot `0x58` at hw-start and stop); W saved value (slot `0x68`, stop path `6694228`); R | Bit 29 is what Apple calls **SNOOP** (slot `0x78`, kick path `66916bc`, message "MTS_SCHEDULE without SNOOP set!"). Bits 29+30 both set plus state 0 plus KICK_STATUS 0 means "powered off waiting for kicks" (slot `0xa0`). State 0 with bits 31:30 = 01 means "stable off" (slot `0x98`). The host never sets bit 29 itself. | code; who sets bit 29 is inferred (firmware via its FenderRegs window) |
| +0x8 | `…TIMER_KICK_STATUS` | R (slot `0xa0`) | Must be 0 for "waiting for kicks" | code |
| +0x10 | `…TIMER_POWER_INT_ENABLE` | `enableGPCHostInterrupts` (slot `0x20`): type 0/1/2 → `|= 1/2/4`; type 3 or more → `= 0`. Host writes 0 at power-on (`66927d8`) and hw start. Only fw slot `0x230(on)` ORs in bit 0. Slot `0x50` reads bit 0 | It is an interrupt enable. A10 called it the "request register"; the J81 name shows it is not a power request | a10-claim+code |
| +0x14 | `…TIMER_POWER_INT_STATUS` | IRQ 135–137 handler (slot `0x28`): if non-zero, write back `& 7` (W1C). Kick: write 7 (slot `0x80`), then test bit 1 (slot `0x90`) as an alternative to SNOOP | W1C status bits 0–2. A10 saw +0x14 = 2 after the 0x11 request, which suggests bit 1 = power-up event. One IRQ per bit is inferred | a10-claim+code; bit-1 meaning inferred |
| +0x1000 | `…VCM_PERF_STATE_CONTROL` | `setGPCPerformanceState(s)` (slot `0x10`, `6698d94`): poll bit 4 clear every 10 µs for ≤30 s (panics "Unable to change GPC performance state!"), then W `s | 0x10`, with no poll afterwards. Slot `0x18` returns `& 0xf` when powered | Low nibble = state, bit 4 = transition busy. J81 only ever uses s = 0 or 1 | a10-claim+code |
| +0x1004 | `…VCM_PERFORMANCE_NEXT_STATE` | dump only | A10 live value 8 | code (name) |
| +0x10000… | ConfigRAM | W only (slots `0xa8`/`0xb0`/`0xb8`/`0xc0`/`0xc8`) | Register-write program; see the protocol below | code |
| +0x20000 | `…VCM_PERF_STATE_OVERRIDE` | slot `0x60(0)` writes 0. Slot `0x60(1)` writes `0x20`, polls bit 5 set (≤30 s), then polls +0x1000 bit 4 clear (≤30 s) | Holds the GPU at its current state (used by fw slot `0xd8` = `6906d0`, whose role is UNRESOLVED) | code |

The host never touches A10's +0x2000…+0x2058 block (IOP window, run bit, reset poll). That block is [a10-claim] only: J81 has no A7 IOP. Map all of reg[1] (1 MiB) on J81, because the host touches +0x10000 and +0x20000. The 0x5000 FenderRegs window is only what the firmware gets. [code, adt]

### ConfigRAM protocol (J81) [code]

- **Start:** slot `0xa8`, `off = 0x10000`. This runs at object init and again at hw-start step 1.
- **write32(reg, val)** (`69c610`): `[F+off] = (reg & 0xff00ffff) | (flag << 16)`, read back, `off += 4`; `[F+off] = val`, read back, `off += 4`.
- **write64(reg, val)** (`69c66c`): the high half goes first. `{(reg+4) | flag<<16, val>>32}`, then `{reg | flag<<16, val & 0xffffffff}`. That is 4 words.
- **End:** slot `0xb8` writes `[F+off] = 0xffff0000` without advancing. `flag` is the low byte of w3, and the only callers (the fw primitives `6691848`/`6691884`/`66918c8`) always pass **0xff**. Bits 16–23 are therefore always 0xff, and the terminator differs from a command by bits 24–31 = 0xff. What bits 16–23 mean is UNRESOLVED; they could be a per-state mask or byte enables [inferred]. Register offsets must be < 0x10000.
- **Completion:** none per word; each store is just read back to flush the posted write. The program takes effect at the next GPC transition 0→1: `+0x20000 = 0`, then `setGPCPerformanceState(1)` (poll +0x1000 bit 4 clear, write 0x11), then `waitForFWAlive`. It is [inferred, strong] that Fender replays the program into RGX on that power-up. META_BOOT and the SOFT_RESET release exist only in ConfigRAM, yet the firmware boots. In addition, `AGXAccelerator::start` first drops the early state-1 power to state 0 (`666d958`: +0x1000 = 0x10, poll), so the boot request really is a 0→1 transition.
- **Stock J81 program**, built by hw start `6690bbc` plus accel `+0x740`/`+0x748`: 30 words at F+0x10000…+0x10077, terminator at **+0x10078**:
  - SOFT_RESET ← `00e7fffffffffc1d`, ← `00e7fe071ffffc1d`, ← `0000000100000000`
  - META_BOOT `0xbf8` ← 1 (32-bit)
  - BIF_CAT_BASE0 `0x1200` ← PC physical address
  - `0x3800` ← `0003550000300001`
  - `0x3808` ← 1
  - SOFT_RESET ← 0

  The first word is `0x00ff0104`, followed by `0x00e7ffff`.

**Is every GPU register write routed through it?** No. [code] Only fw slots `0x1e0`/`0x1e8`/`0x1f0` (write32/64/64-shifted; entry `6691818`/`6691854`/`6691890`) are redirected. With bit 1 of `7a4d882` set, they *only* append to ConfigRAM: no direct store. If their `flags` argument is non-zero with bit 0 clear, they do nothing. A scan of every `[vt+0x1e0/0x1e8/0x1f0]` call site finds them used only by hw start, by accel `+0x740`/`+0x748` (called from hw start) and by the non-GPC `bootFirmware` branch. All runtime accesses are direct `str` to `accel+0xd10`: the MTS_SCHEDULE kick `0xb00`, the stop path (`0x1340` = 1, BIF_CTRL `0x12a8` = 8, SOFT_RESET = `0x08000000`), the META slave port, `0xac8`, and the MMU reads. The scan is by vtable-offset pattern, so indirect calls through other registers could be missed.

**Power sequences on J81** [code]:
- **Early probe** (`683968`, gated by `7a4d882` bits 0 and 2 and byte `7a4d87f`; whether J81 meets these is inferred yes): +0x10000 = `0xffff0000` (empty program) and +0 = `0x40000000` (both skipped if `7a4d882` bit 3 is set), then +0x1000 = 0x11, then poll bit 4 with no timeout, then a 10 µs delay.
- **Power on** (`66926c0`): slot `0x30(1)`, then +0x10 = 0.
- **Stop:** slot `0x58`, then quiesce META, write the direct RGX stop registers, +0 ← fw-table value (`fw+0x358`), +0x20000 = 0, `setGPC(0)`.
- **Kick:** +0x14 = 7. If the state is non-zero, kick. Otherwise, if +0 == 0, call the power-up helper `68ea90` (UNRESOLVED). Otherwise SNOOP or +0x14 bit 1 means kick; anything else logs a warning and kicks anyway.

## T4. What the A10 work implies for J81

1. **GPU page size: J81 uses 4 KiB, shift 12.** [code] `7a4cf80`/`f88`/`f90` default to 12, `0xfff` and `0x1000`. At `666d9f0`, `AGXAccelerator::start` calls accel slot `0x878` ("TEST_PAGE_SIZE_16K"). Only if that returns true does it require kernel page_shift == 14 (otherwise it fails "GPU uses 16K page size but CPU does not") and copy the kernel's page_shift/mask/size (GOT `6f2ad98`/`ad90`/`ada0`) over the defaults. On `AGXAcceleratorG4G_A0` (the only accelerator class in the kext), slot `0x878` = `69b048` = `return 0`. The value is therefore fixed at compile time: no ADT property and no boot-arg (the J81 ADT `sgx` node has none either [adt]). This matches the 4 KiB-only PT index mask in appendix T3. The A10's 16 KiB `pvr_mmu` pages are [a10-claim] and must not be copied: a 16K-page Linux kernel on J81 needs 4 GPU PTEs per CPU page.
2. **`pwr_ops`.** The idea applies [a10-claim+code]: power on means "GPC state 1, then touch RGX". J81's version differs. Power on = PMGR/provider on, +0x10 = 0, +0 = `0x40000000`, the ConfigRAM program (or direct writes, see below), +0x20000 = 0, +0x1000 = 0x11. Power off = the stop sequence above, then +0x1000 = 0x10. The AP-side `+0x1000 = 0x11` that A10 proved is exactly what the stock J81 host does [a10-claim+code]. "Never read RGX before state ≥ 1" also matches: fw slot `0x240` checks `+0x1000 & 0xf ≥ 1` [a10-claim+code].
3. **Direct writes vs ConfigRAM** [inferred]. Apple keeps a supported non-GPC path (`gpu_gpc=0`) that writes SOFT_RESET and the other registers directly, so direct writes are architecturally possible. However, a register written directly is probably lost whenever Fender power-gates the GPU. For J81 bring-up, either reproduce the 30-word ConfigRAM program before the 0→1 transition, or write directly once state 1 is reached and keep SNOOP/timer sleep off (+0 = `0x40000000`). This supersedes RESULT.md's W1 advice ("direct writes, else implement the mailbox").
4. **Firmware from the kernelcache.** The pattern carries over [a10-claim+code]: a firmware kext provider returns a pointer and size into `__TEXT.__const` (J81: `AGXFirmwareKextG4G`, VA `59ab9c8`, size `0x1cbb4`, RESULT §A). The A10 image is raw ARM32; J81's is an IMG META LDR and needs the upstream LDR parser. The A10 RTKit, A7 IOP, init-data X/P/Q/T/U/V, ring and mapping-ring work does **not** transfer [a10-claim].
5. **Static device info.** This applies [inferred]. J81's LDR has no IMG firmware header (RESULT §A), and the kext carries no BVNC, core-ID or feature table (no such strings; it has only 24 `RGX_CR_*` and 16 `AGX_CR_*` names). A static 7.5.8.3 entry is needed. Read CORE_ID `0x18` and REVISION `0x20` only after state 1, and treat them as the legacy format until proven otherwise [a10-claim].
6. **DVFS.** A10: perf state = +0x1000 nibble 1–6, from the `sgx` `perf-states` that iBoot fills at boot (zeroed in a static ADT) [a10-claim]. J81 has the same names [code] and the static ADT also has `perf-states`, `perf-state-count` and `gpu-num-perf-states` = 0 [adt]. The J81 host only uses states 0 and 1; whether higher J81 states exist is UNRESOLVED. A10's PMGR+0x68000 SoC/memory state is [a10-claim] T8010-only.
7. **Shader ISA / Mesa.** The A10 claims that G9P's USC runs Apple's ISA, so `pco` is unusable there, while PDS, CDM, MMU and `RGX_CR` are Rogue [a10-claim]. For J81 this is **UNRESOLVED**. Evidence [code]: G4G already has Apple-defined USC control registers in an Apple block, RGX+0xe000…:
   - `AGX_CR_USC_STATUS_CTRL` `0xe010`, `EXT_INT_STATUS0` `0xe018`
   - `USC_INST_BASE_FRAG/VERT/COMP` `0xe020/0xe030/0xe040`, each followed by `DBG_BASE_*` at +8
   - `USC_PARTITION_CONFIG` `0xe080`

   These sit next to Rogue's `RGX_CR_USC_SERV_*` at `0x40d8…0x40f8`. A10's firmware also programs RGX `0xe140…0xe208`, in the same range. This shows Apple modified the USC front end by the A8X, but it does not prove a non-Rogue ISA [inferred]. The decisive test is the A10 one: take any G4G USC binary (from the iPadOS 15 `AGXMetalG4G` compiler or a device capture; whether `metal-tt` offers a G4G target is unknown) and check Rogue `nop.end`/`0xff` padding against Apple `0x8000` end/`0xc000` padding.
8. **What the A10 notes mark as unknown or different for A8/A9.** Most "A9" lines say unknown: the IOP mailbox (assumed to carry over from SmartIO), the RTKit HELLO and endpoint map, the Fender base and state register and perf-state count, the init-data layout (per firmware build), clocks/PMGR, the firmware job-ordering waits, the shader ISA, and display (ADBE "should" work). FENDER.md says, unverified, that "the A9's Fender at 0x201e00000 is in the same family"; J81's is at 0x2_01e0_0000 too [adt]. For J81, the IOP, RTKit, init-data and job-ordering items are moot (META firmware). The Fender items are answered above.

## Unresolved

- ConfigRAM: meaning of bits 16–23 (always 0xff); capacity; whether it is replayed on every timer wake or only on host-requested 0→1 transitions.
- Who sets SNOOP (+0 bit 29) and the meaning of bits 30/31. The stop-path restore value comes from `fw+0x358[idx].+4` (source not traced).
- Power-up helper `68ea90`; callers of fw slot `0x230`; role of fw slot `0xd8` (`6906d0`); the exact gating flags of early init.
- Delay stub `66b0f7c` is assumed to be `IODelay(µs)`.
- G4G shader ISA (Apple or Rogue).
- No Fender vtable slot is left unresolved: every slot was resolved and disassembled.
- Helpers: `$SCRATCH/t34/fslots.py` (Fender slot call-site scan), `$SCRATCH/t34/crnames.txt` (register-name strings).
