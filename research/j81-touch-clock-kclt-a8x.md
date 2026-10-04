# J81 touch clock: the iOS 8.1 `KLCT` handler

Date: 2026-10-04. Static analysis only (Ghidra on the iPad5,3 iOS 8.1 12B410
kernelcache, SHA-256 `19c277d6...cc28bf`; kext `AppleT7000`, i.e. the
`AppleT7000PerformanceController` driver). No device access. Labels: **E** read
in the decompilation or ADT, **I** inference, **U** unknown.

This answers the open KLCT item in
[`j81-klct-resource-audit.md`](j81-klct-resource-audit.md) for the exact
firmware generation J81 runs. It supersedes using the iOS 10.3 helper layout.

## Where the handler is

- **E:** the ADT touch property `function-clock_enable` targets phandle `0x1a`,
  which is the `pmgr` node (`pmgr1,t7001`), with selector `KLCT`.
- **E:** the kernelcache registers the function class
  `AppleT7000PerformanceControllerFunctionEnableTouchClock` beside its siblings
  (`EnableCore`, `ISPConf`, `ClearSOCHOT`, `RGBCLKFrequency`). Its `callFunction`
  slot calls one routine on the owning `AppleT7000PerformanceController`,
  forwarding the two argument words it receives.
- **E:** the string `KLCT` does not exist anywhere in the kernelcache, as a
  literal or as a 16-bit-half immediate, so the selector is bound by the
  function-class table rather than by a visible comparison. The class-to-selector
  link is therefore **I** (class name and ADT usage), not a located compare.

## The register block (E)

The controller's start routine maps two ranges from its ADT provider:
memory-map 0 logged as `pmgr` and memory-map 1 logged as `TCC_pwrctl`. The
`pmgr` node's `reg` has four entries; entry 1 is the one used by the touch
handler:

| `reg` entry | Offset in `arm-io` space | Size | Driver label |
| --- | --- | --- | --- |
| 0 | `0x0e000000` | `0x40000` | `pmgr` |
| **1** | **`0x02220000`** | **`0x2000`** | **`TCC_pwrctl`** |
| 2 | `0x08000000` | `0x32000` | not used here |
| 3 | `0x07000000` | `0x2000` | not used here |

The offset is `arm-io`-relative as stored in the ADT; the CPU physical address
follows the same `arm-io` base convention as the PMGR entry `0x0e000000`
(`0x20e000000`), giving `0x202220000` for `TCC_pwrctl`. That conversion is **I**.
The block is **not** in the generic PMGR power-state array, which confirms the
audit's warning against indexing it with an ADT device ID.

## What the routine does (E)

For `callFunction(a, b)` the owner performs, on the `TCC_pwrctl` block `R`
(64-bit registers):

1. wait while `R+0x20` bit 31 is set (poll with a 1-unit delay);
2. if `((R+0x50) >> 3) & 7` already equals `a`, skip step 3;
3. write `R+0x20 = (R+0x20 & ~0x03c00000) | (a << 22) | 0x02000000`, then poll
   `((R+0x50) >> 3) & 7` until it equals `a` or `b`;
4. `R+0x48 |= 0x8000`;
5. `R+0x20 = old_R20 | 0x02000000`.

The multitouch driver passes a literal `3` to enable and `0` to disable (from
the earlier callback audit), so enabling selects state 3 in the 3-bit field.

## What this changes

- The touch clock on A8X is a **3-bit state field with a status poll**, not the
  ten-bit divider/gate-off/apply/busy layout recorded from iOS 10.3. The earlier
  "divisor 732" arithmetic does **not** describe this handler: it never reads the
  ADT tuple's `100` or `32768`, and the `8` is not visibly used either. The tuple
  is carried in the ADT but this handler ignores it (**E** for the code, **I** that
  it is only ADT metadata on this generation).
- The "missing KLCT index" is a **register block**: `pmgr` `reg` entry 1,
  `0x2000` bytes. A Linux clock provider would map it and implement the five
  steps above, keeping the clock-state field values encoded as bits.
- The **TCC** name collides with thermal records elsewhere in the ADT
  ("TCC Temp Sensor", "TCC sochot"); this block carries power control but whether
  state 3 drives only the 32.768 kHz output or a wider domain is **U**.

## Not done / not safe

Nothing here authorizes a write. Unknown: what `b` is, what state values 0-7
mean electrically, whether bit 25 is a trigger or a flag, and what `R+0x48 |
0x8000` latches. A guessed write to this block could change a power state shared
with other consumers. Next evidence: trace `AppleMultitouchSPI`'s second argument
to the clock callback, then decide whether a read-only status sample
(`R+0x50`) is acceptable in a diagnostic build.
