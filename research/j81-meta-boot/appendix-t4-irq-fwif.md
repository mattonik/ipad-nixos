# T4a/T4b: J81 AGXG4G (iPadOS 15.8.5, 19H394) interrupts, first handshake, FWIF shape

The method was disassembly plus the ADT only. Tags: [code] means a disassembly fact, [adt] a device-tree fact, [upstream-claim] something taken from the Linux PowerVR headers, and [inferred] my own reasoning.
Objects: `fw` = the firmware-controller object (vtable 0xfffffff006f2de28, which is `accel+0xdd8`); `accel` = the accelerator (vtable 0xfffffff006f2f2d0). Note that `fw+0x1a8` = accel and `accel+0xd10` = RGX MMIO.
`Fender` = Apple's GPC (GPU power controller) object. It is 40 bytes, vtable 0xfffffff006f2fee8, created by accel slot 0x850 = 0xfffffff00669aff4, stored at `fw+0x160`, with its MMIO at `obj+0x10`.

## Correction to the brief
Upstream defines `0x0AC0` as `META_SP_MSLVRST`. `MSLVIRQENABLE` is `0x0AD0` and `MSLVIRQLEVEL` is `0x0AD8` [upstream-claim]. The driver never writes 0xAD0 or 0xAD8 [code].

## T4a: interrupts and the first handshake

### Device tree: `/device-tree/arm-io/sgx` [adt]
- **Identity:** `compatible="gpu,t7001"`.
- **`reg`:** two ranges. `reg[0]` = 0x01000000 + 0x100000, which is **RGX** at phys 0x2_0100_0000 through arm-io `ranges` (child 0 maps to 0x2_0000_0000). `reg[1]` = 0x01e00000 + 0x100000, which is **Fender/GPC** at 0x2_01e0_0000.
- **How the code picks them:** with a count of 2, the jump table at 0x6836a8 sets RGX index 0 and Fender index 1 [code].
- **`interrupt-parent`:** 0x18, which is `/arm-io/aic` (`aic,1`, reg 0x0e100000, so phys 0x2_0e10_0000).
- **`interrupts`:** 20 bytes = `[0x86, 0x87, 0x88, 0x89, 0x8a]`, i.e. AIC IRQs 134 to 138.
- **`meta-sw-interrupt`:** 40 bytes = two 20-byte records of {u64 set_reg, u64 clr_reg, u32 mask}:
  - Record 0: set 0x2_0e10_4010, clear 0x2_0e10_4090, mask 0x40.
  - Record 1: same set and clear registers, mask 0x400.
  - In AIC v1 these are SW_SET and SW_CLR word 4 (AIC + 0x4000/0x4080 + 0x10), so mask 0x40 is IRQ 134 and mask 0x400 is IRQ 138 [inferred, from the AIC v1 layout].
- **How the driver reads it** (0x66712fc–0x671368) [code]: if the length is greater than 0x27 it takes record 1. It stores set at `accel+0x1ba8` (0x2_0e10_4010), clear at `+0x1bb0` (0x2_0e10_4090) and mask at `+0x1bb8` (**0x400**). If the property is missing it zeroes these fields.
- **Count switch:** with 5 interrupts, the switch at 0x6712a4 sets `accel+0xeb8 = 0x04` and `+0xeb9 = 0x01` (strh 0x104), and `+0xeba = 5`.
- **No other properties found:** there is no `no-gpc` or `has-kf` property anywhere in the ADT. Therefore global flag byte `0xfffffff007a4d882` has bit1 set ("use GPC/Fender", 0x683784, default when no boot-arg) and bit3 clear [code + adt absence].

### Interrupt sources and routing [code]
- **Registration:** the loop at 0x66ec60 creates one filter-interrupt event source per index 0..4, all 5 because bit3 of the flags is clear. Filter = accel slot 0x888 = 0x672758, which just returns 1. Action = accel slot 0x890 = 0x672760, which calls `fw` slot 0x1f8 = **0x68bba0** with the index.
- **Index 1–3 (IRQ 135–137):** goes to Fender slot 0x28 = 0x69901c. It reads Fender+0x14; if that is non-zero it writes back `val & 7` and reads it again (write-1-to-clear GPC interrupt).
- **Index 0 (IRQ 134, RGX core):** `eb9 != 0`, so it calls `fw` slot 0x240 = 0x692828 (GPU accessible: Fender+0x1000 & 0xf ≥ 1, ≤ fwdata+0x29c, and Fender+0 bit29). If that passes it calls accel slot 0x898 = 0x69b054, which reads **RGX 0x1290** (BIF_MMU_ENTRY) bit0 and only reports "MMU entry pending". Then, because the GPC flag is set and accel slot 0x7b8 = 0x69abd0 always returns 1, it **returns without draining**.
- **Index 4 (IRQ 138) is the firmware-to-host doorbell.** It runs these in order:
  1. `fw` slot 0x390 = 0x694274 clears the interrupt.
  2. Slot 0x398 = 0x68c9fc runs `drainFirmwareEventRing`.
  3. Slot 0x3a0 = 0x68d020 drains the FW log ring.
  4. 0x68d5e0 drains FWTRACE.
  5. Then it drains a 36-byte record ring at `fw+0x350`/`+0x370`.
- **Clear path, J81 case:** in 0x694274, with the GPC flag set and slot 0x7b8 true, it writes **0x400** (`accel+0x1bb8`) to the CPU mapping of **AIC SW_CLR 0x2_0e10_4090**. The address is computed as `fw+0xad8`→getVirtualAddress + (0x1bb0 − 0xf00 phys) + `fw+0xb18`. **No RGX status register is read first.**
- **Clear path, other case:** otherwise, if `accel+0x12c1 == 1`, it writes 0 to **RGX 0xAC8** (META_SP_MSLVIRQSTATUS).
- **How the firmware knows where to ring:** the firmware gets the doorbell through fwdata: `+0x2e4` = SW_SET offset inside the mapped AICSWIntRegs page (0x...4010 − page = 0x10), and `+0x2e8` = mask 0x400 (0x6899d8–0x6899e8) [code]. So the firmware rings the host by writing 0x400 to AIC SW_SET word 4 [inferred]. This settles the old "134 or 138" question: **only 138 drains on J81** [code].

### Host-to-firmware kick [code]
These write `MTS_SCHEDULE` 0xB00 at `accel+0xd10`:

| fw slot | function | value written |
|---|---|---|
| 0x140 | TA submit 0x690da0 | 0x10 |
| 0x148 | 3D 0x690f78 | 0x11 |
| 0x150 | CL 0x691150 | 0x12 |
| 0x158 | `kickFirmware` 0x691328 | 0x10 |
| 0x160 | device-control-ring submit 0x6914dc | 0x10, only if flags & 3 |

- **Value format:** these match upstream TASK_COUNTED (bit4) | DM 0/1/2 [upstream-claim].
- **Pre-checks before each kick:**
  1. Fender slot 0x80 writes Fender+0x14 = 7.
  2. Fender slot 0x18: if `Fender+0x1000 & 0xf` is non-zero, kick.
  3. Otherwise read Fender+0 (slot 0x70). If it is 0 and `accel+0xe70` bit0 is clear, call 0x68ea90 (power-up, not traced) and kick.
  4. Otherwise, if Fender+0 bit29 (slot 0x78) or Fender+0x14 bit1 (slot 0x90) is set, kick.
  5. Otherwise print "MTS_SCHEDULE without SNOOP set!" with Fender+0x0 and +0x14, and kick anyway.
- **Alive gate:** every submit first checks `fw+0xb35` (alive). If it is clear it calls `waitForFWAlive`; if that fails it prints "Firmware not alive … (fBootFirmwareCalled:%d)" with `fw+0xb37`.

### Boot and "firmware alive" [code]
- **bootFirmware** = `fw` slot 0xc0 = 0x690328, called from `createHardwareMappingsAndBootFirmware` (accel 0x673ff4 → fw slot 0xc0).
  - **GPC flag set (J81):**
    1. Fender slot 0x60(0) = 0x69c238 writes Fender+0x20000 = 0.
    2. Fender slot 0x10(1) = 0x698d94 (`setGPCPerformanceState`) polls Fender+0x1000 bit4 until clear, in 10 µs steps with a 30 s limit (0x1c9c377 µs; message says 30000 ms). It then writes **Fender+0x1000 = 1 | 0x10**.
  - **GPC flag clear:** `fw` slot 0x1e8 writes RGX 0x100 (SOFT_RESET) = 0. Note that with GPC set, the slot 0x1e8 and 0x1f0 RGX writes are proxied through Fender slot 0xc8.
  - **Then:** it calls `waitForFWAlive`. On success it logs "GPU firmware booted successfully" and sets `fw+0xb37 = 1` (**fBootFirmwareCalled**).
- **waitForFWAlive** = 0x694d40:
  - If `fw+0xb35` is already set, it returns 1.
  - Otherwise it sets `fw+0xb36 = 1` (waiting) and loops: `clock_interval_to_deadline(accel+0xc20, 1e9)`, then `IOCommandGate(accel+0xd18)` slot 0x110 (timed commandSleep) on event `&fw+0xb35`.
  - It allows up to **10** timeouts (10 × `accel+0xc20` seconds; the 8.1 notes say 1 s each). On exhaustion it prints "META not alive" and returns 0.
  - **It is not a register poll.**
- **Alive producer** = `fw` slot 0x388 = 0x693ea8, called from the event-ring drain for record type 0. If `fw+0xb35` is 0, it stores record word +4 into `fw+0xb38`, sets `fw+0x1c8 = 1` and `fw+0xb35 = 1`, and calls commandWakeup(&`fw+0xb35`) (gate slot 0x108).
- **Readiness check:** `fw` slot 0xe8 = 0x690d0c returns `b35 && !b36`.
- **Stubs:** `isFWAwake` (0x68c3f0/0x692c08), `setGFXDeviceBusy` (0x6928d0) and `submitCmdGPUIdlePowerOff` (0x692988) all print "Unimplemented" and panic. They are not used on G4G META.

### Table 1: interrupt/handshake register sequence (J81: GPC flag set)
| insn | register | R/W | mask/value | purpose |
|---|---|---|---|---|
| 0x69c260 | Fender+0x20000 | W | 0 | pre-boot (Fender slot 0x60(0)) |
| 0x698dc0 | Fender+0x1000 | R poll | bit4 == 0, 10 µs, ≤30 s | GPC busy wait |
| 0x698e98 | Fender+0x1000 | W | 0x11 (state 1 \| 0x10) | power up / start GPU (boot) |
| — | memory `fw+0xb35` | sleep/wake | type-0 event record | FW alive (10 × `accel+0xc20` s) |
| 0x672758 | — | — | returns 1 | primary filter, no MMIO |
| 0x6942d8/0x694300 | AIC SW_CLR 0x2_0e10_4090 (mapped) | W | 0x400 | ack IRQ 138 doorbell |
| 0x694300 (alt) | RGX 0xAC8 MSLVIRQSTATUS | W | 0 | ack, only when GPC flag clear and `accel+0x12c1 == 1` |
| 0x68ca1c… | `fw+0x338` ring: rd +0, wr +0x10 | R/W | 8-bit wrap | drain event ring |
| 0x69b068 | RGX 0x1290 BIF_MMU_ENTRY | R | bit0 | IRQ 134 (index 0) handler |
| 0x699028 | Fender+0x14 | R then W | `& 7` | IRQ 135–137 ack |
| 0x691640 | Fender+0x14 | W | 7 | before each kick |
| 0x690e24/0x690ffc/0x6911d4/0x691380/0x691668 | RGX 0xB00 MTS_SCHEDULE | W | 0x10/0x11/0x12/0x10/0x10 | host→FW kick |

## T4b: firmware interface shape [code unless tagged]
- **Layout:** the shared memory is laid out by `fw` slot 0x130 from sub-allocation tables in 0x687b50 (after 0x68f350 maps the MMIO pages listed in `accel+0xed0` into firmware space). Each table entry is {CPU-pointer field, firmware-address field, size}.
- **prepareFirmwareData:** `fw` slot 0xa8 = 0x68fa88 → 0x68a03c, which is only `IOMemoryDescriptor::prepare()` (slot 0x98) over the backing descriptors at `fw+0x290, 0x2a0, 0x3c0, 0x3d0, 0x8a0, 0x8d8, 0x910, 0x948, 0x980, 0x9b8, 0x9f0, 0x28, 0x98, 0x108`. It does not fill any data.
- **Fill:** 0x68911c and 0x6897a8.
- **Boot pointer:** 0x690250–0x690284 write two u32 firmware addresses, the 0x1490 root block (`fw+0x238`) and the 0x2058 block (`fw+0x2b0`), into the loaded **firmware image** at image offset `fw+0xa5c` (= a data segment's size − 8). This is the **only boot-time pointer handoff found**. It is consistent with the 8-byte LDR records at `…ff8` [inferred].

### Table 2: FWIF objects
| object (CPU ptr / FW addr in `fw`) | size | filled by / role |
|---|---|---|
| Root block 0x1d8/0x238 (cached group, 9 entries) | 0x1490 | 0x68911c: +0x00..+0x1c = 8 u32 FW addresses of host→FW rings (TA ctl/buf, 3D, CL, DevCtl); +0x20..+0x3c = FW→host rings (event ctl/buf, log ctl/buf, trace ctl/buf, 36-byte ring ctl/buf); +0x64..+0x74 = addresses of blocks 0x240..0x260; +0x44c/+0x450/+0x454 = addresses of 0x278 / 0x268 / **0x270 (config)**; +0x480/+0x484/+0x48c = FW image addresses and size |
| Blocks 0x1f0, 0x1f8, 0x200, 0x208, 0x210 | 0x990, 0x8e0, 0x8c0, 0x938, 0x28 | contents not traced |
| Block 0x218 | accel slot 0x990 | not traced |
| **Config 0x220/0x270** | **0x318** | 0x6897a8: +0x0..+0x30 constants; +0x1c0..+0x24f = 9 × {u64 phys, u32 0, u32 size} MMIO windows (FenderRegs 0x5000, AICTimerRegs, AICSWIntRegs, RGXRegs 0x20000, UVDRegs/Unused, …, DisplayUnderrunWA); +0x254 lockup-detect; +0x260 simpal; +0x264 cache-flush timer; +0x268/+0x26c context id / timeslice; +0x274 agf_timer; +0x288/+0x28c usc_exc; +0x2e4/+0x2e8 AIC SW-set offset/mask; +0x2ec timebase offset (0x1020); +0x2f8 u64 from accel slot 0x928 |
| 0x228/0x278 | 0x84 | not traced |
| 0x2a8/0x2b0 (uncached group, 18 entries) | 0x2058 | host/FW state page: +0x24 temperature limit (120), +0x1c, +0x28/+0x2c flags |
| TA / 3D / CL / DevCtl ring control: 0x2b8, 0x2d8, 0x2f8, 0x318 | 0x20 each | FW read index +0, host write index +0x10, zeroed at 0x689130 |
| TA / 3D / CL / DevCtl ring buffers: 0x2c0, 0x2e0, 0x300, 0x320 | 0x1400 each | 256 × 20-byte commands (DevCtl submit 0x6915cc) |
| FW event ring: control 0x338, records 0x358 | 0x20 / 0x2c00 | 256 × 0x2c (44-byte) records, types 0..8; 0 = alive, 1 = completion bitmasks |
| FW log ring: control 0x340 (4 channels) | 0x80 / 0xb000 (0x360) + 0x36000 (0x230) | "%u,%u,%llu>: %s" printer 0x68d020 |
| FWTRACE: control 0x348, records 0x368 | 0x20 / 0x2c00 | trace dump 0x68bf38 |
| 36-byte ring: control 0x350, records 0x370 | 0x20 / 0x2400 | 256 × 0x24, sent to 0x6a9844 |
| 0x3e0/0x3f8; 0x3d8/0x3f0; 0x3e8/0x400 | accel slot 0x760 × 4 / × 4 / × 8 | not traced |

### Comparison with upstream
- **Same in principle:** circular buffers with read/write control words, a host kick through MTS_SCHEDULE, firmware-address translation (`fw` slot 0x1a8), a trace buffer, and MMIO windows mapped into firmware space [upstream-claim].
- **Different everywhere else:**
  - There is no `rogue_fwif_sysinit`/`osinit`, no `firmware_started` flag and no KCCB/FWCCB command format.
  - Rings are 256-entry with 8-bit wrap and 20- or 44-byte records.
  - "Alive" is an event-ring record delivered by an AIC software interrupt.
  - Boot is started by Apple's Fender GPC, not by a META_BOOT plus SOFT_RESET sequence.
  - Firmware-to-host notification is an AIC software interrupt, not MSLVIRQSTATUS TRIGVECT2.
- **Conclusion [inferred]:** upstream's FWIF init, ccb and boot-wait code **cannot be reused**. What may carry over:
  - The register helpers: META slave-port access (MSLVCTRL0/1, DATAT), MTS_SCHEDULE with TASK_COUNTED|DM values, and SOFT_RESET for the non-GPC path.
  - The META LDR loading logic.
  
  A J81 driver needs an Apple-specific layer: Fender power-up, the root/config blocks, the ring set, the pointer slot in the image, and the AIC SW interrupt 138 handling.

### DVFM and power requests
| request | where | needed for first handshake? |
|---|---|---|
| Fender early init: +0x10000 = 0xffff0000, +0 = 0x40000000 (if no has-kf), +0x1000 = 0x11, poll bit4 | 0x683980 | likely yes [inferred] |
| Fender+0x20000 = 0, then setGPCPerformanceState(1) | 0x690384–0x690394 (boot) | **yes** |
| setGPCPerformanceState(0) | 0x690454 (stopFirmware, `fw` slot 0xc8), 0x68f318 | no (idle power off / teardown) |
| Fender slot 0x20 (0 or 3), from `fw` slot 0x230 | 0x68c3bc | performance/power only [inferred] |
| setGFXDeviceBusy, submitCmdGPUIdlePowerOff | stubs that panic | not used |
| IdlePowerOffTimerEvent, gpu_idle_poweroff, perf-state statistics (fw_perf_state_*, "PState/SubPState/DC" read from `fw+0x208`) | various | performance only |

The setGPCPerformanceState call sites only ever pass 0 or 1. The ADT `perf-states`, `gpu-num-perf-states` and `perf-state-count` are all zero in this static ADT [adt].

## Not resolved
- The value of `accel+0xc20` (the alive-wait interval); no store to it was found.
- `accel+0x12c1` and the meaning of RGX 0x1340.
- The 0x68ea90 power-up path.
- Fender slots 0x20 and 0xc8 semantics, and Fender register names (the "SNOOP" bit naming is inferred).
- Event record types 2–8 (only 0 and 1 decoded). The type-6 META-halt path in 0x693efc writes T0/T1ENABLE 0x04800000/0x04801000 = 0xfffffffe, then RGX 0x1340 = 1, 0x12a8 = 8, 0x100 = 0x08000000; the caller of that path was not identified.
- Contents of the 0x990/0x8e0/0x8c0/0x938/0x84/0x2058 blocks.
- Whether the image pointer slot at `fw+0xa5c` is the only firmware-to-root handoff.
- No vtable call in the paths above was left unresolved, except Fender slot 0xc8 (resolved to 0x69c66c but not analysed) and `IOCommandGate` slots 0x108/0x110, which are taken from the 8.1 notes.
