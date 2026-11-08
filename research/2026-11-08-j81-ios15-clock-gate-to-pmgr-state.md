# J81 iOS 15: GFX clock gate reaches ApplePMGR's generic state path, not the T7000 special action

Date: 2026-11-08. Offline objdump disassembly of the iPadOS 15.8.8 J81
kernelcache (`artifacts/live/private/gpu-offline/ios15-kernel`). Slices cut:
`ApplePMGR` `__TEXT_EXEC` `0xfffffff006bb9000`+`0x34a4c`, `AppleT7001PMGR`
`0xfffffff006c88000`+`0x2f28`, and `AppleT7000` `0xfffffff006c8f000`+`0xaadc`.
No device access.

## 1. The clock-gate `+0x80` target (the last open link)

- `ApplePMGRFunctionClockGate` is registered at `0x...6bdd200` (size `0x30`,
  metaclass vtable `0xfffffff006fd0950`). Its allocator installs the instance
  vtable `0xfffffff006fd08b0`, and `getMetaClass` is at `+0x38` as expected.
- Instance vtable `+0x80` is `0xfffffff006bdd39c`. It splits the gate ID: bits
  31:28 are the PMGR instance and bits 27:0 are the device ID. It checks the
  instance against `pmgr+0x2724` and requires the enable argument to be below 4.
  Then it calls `0x...6bd7a1c(pmgr, devid, enable & 1, enable >> 1, instance)`
  and returns 0.
- `0x...6bd7a1c` emits kdebug `0x2700c001`, then runs `0x...6bd7ad0` through
  the command gate (`[pmgr+0x160]` vtable `+0xe8`), then emits `0x2700c002`.
- `0x...6bd7ad0` is the generic device power-state change. Enable selects
  state 15. It compares against a cached per-(instance, device) state byte
  and does nothing if the state is unchanged. Otherwise it builds the
  dependency list (`0x...6bc8de4`) and performs the transition
  (`0x...6bd81a8`). That function calls `0x...6bc6c20` and `0x...6bc6ed8`, the
  state read, compare and write-with-timeout helper documented in
  `2026-11-08-j81-ios15-pmgr-state-transition-helper.md`. **So the iOS 15 GFX
  clock enable does reach that helper.**

Complete chain: G4G → `AppleT7001IO +0x568` → cached `function-clock_gate` object
`+0x80` (`ApplePMGRFunctionClockGate`) → `ApplePMGR 0x...6bd7a1c` →
`0x...6bd7ad0` → `0x...6bd81a8` → `0x...6bc6ed8`.

There is **no per-device reference count** on this path. The per-device record
of 8.1 (`count != 0` → active) becomes a cached-state compare here. The 8.1
question "was G4G's request a 0→1 edge?" does not carry over to iOS 15.

## 2. Which PMGR driver binds on J81 under iOS 15

- The iOS 15 ADT capture (`20261106T060741Z-pongo-adt.adt`) names the node
  `pmgr1,t7001`. The iOS 8.1 tree (`ios81-dt.json`) has `pmgr,t7000`.
- The iOS 15 personalities are `AppleT7001PMGR` (`IONameMatch pmgr1,t7001`),
  in its own kext, and `AppleT7000PerformanceController`
  (`IONameMatch pmgr,t7000`) in `AppleT7000`. So on J81 under iOS 15 the
  ApplePMGR-family driver binds. AppleT7000PerformanceController does not.
- `AppleT7001PMGR` derives from `AppleT7000PMGR`. Their strings show
  overrides for perf states, ISP/video clocks, CPU energy accumulators and
  `function-mcc_ctrl`. Neither has a GFX special action or a bridge writer.
- The iOS 15 `AppleT7000` code that applies GFX bridge selectors
  (`FUN_...c961f8`, `...c97278`, `...c9739c`; see
  `2026-11-08-j81-ios15-t7000-clock-callback-boundary.md`) sits behind
  `AppleT7000PerformanceController` vtable `0xfffffff006fead10` slots
  `+0x680` (`0x...c960b4`) and `+0x6b8` (`0x...c965f4`). These are the same
  clock/power slot numbers 8.1 used. That class matches `pmgr,t7000`, so this
  is an iOS 15 copy of the 8.1 mechanism that **does not bind on J81 iOS 15**.
  Static inference from personalities and the ADT compatible string, not a
  runtime IORegistry read.

## 3. Bridge tables in the iOS 15 model

The iOS 15 ADT carries the bridge data directly in the `pmgr` node:
`#bridges`, `bridge-reg-index` and `bridge-settings-0` through `-12`.
ApplePMGR parses them (string refs at `0x...6bc09b8` and around it into
`BridgeData` objects). Selectors 9/10 in the 8.1 record match
`bridge-settings-9`/`-10` by number, which supports test4's choice of tables.
This pass did **not** find where or when iOS 15 ApplePMGR applies a device's
bridge settings during the state change. It could be inside `0x...6bd81a8`'s
callees, or only at init or wake. That is the next open point.

## 4. Record-flag platform actions

For device records with flag bit 1, `0x...6bd7ad0` calls `0x...6bd523c` with
action `0xe` (or `0xf` when bit 7 is set). It runs after the state-on when
bit 6 is clear, and before the state-off. Dispatch depends on a mode word at
`pmgr+0x1b0`:

- Mode 1 sends the action to the `function-pmp_control` object. The J81 ADT
  has no `pmp` entries.
- Mode 2 handles it internally (`0x...6bd5934`). That path needs mailbox-style
  structures at `pmgr+0x34048`; otherwise it returns `0xe00002bc`.
- Any other mode returns `0xe00002c7` (unsupported).

The J81 mode value is set from a parsed property (`+0x560`/`+0x564` →
`+0x1b0`) and was not resolved here. The GFX record's iOS 15 flag byte was
also not decoded.

## What this means for the RGX read hang

- For iOS 15 the "missing Apple step" search narrows to two concrete things.
  One is the generic PMGR state transition, which Linux test4 approximated
  and which reached `0x3ff`. The other is when or whether ApplePMGR applies
  `bridge-settings-9/10` for GFX, plus any dependency-list transitions
  (`0x...6bc8de4`) that power other devices first.
- The dependency list is the new candidate: iOS 15 may bring up a parent
  power state before GFX, which test4's single-domain Linux PMGR operation
  would not. Decode `0x...6bc8de4` and the GFX record's dependency fields next.
- Nothing here justifies a hardware access yet.
