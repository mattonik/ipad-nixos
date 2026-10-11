# Bluetooth remaining hypotheses: LPO clock and Wi‑Fi dependency

Date: 2026-10-11. Software-only review of the extracted iOS kexts, the
BCM4350C2 firmware/NVRAM, and the existing Wi‑Fi hardware traces. No build,
DFU cycle, firmware modification, or hardware write was performed.

## 1. Missing 32.768 kHz/LPO clock

**Result: no Bluetooth-specific iOS enable path found.**

Evidence:

- The extracted `AppleBluetooth` image contains only the three optional
  platform functions `function-bt_reset`, `function-bt_wake`, and
  `function-power_enable`. Its `BTReset::start()` path resolves those
  functions and registers the character devices; it has no clock property or
  clock-gate lookup.
- `nm` on the public `AppleBluetooth` image has the single platform-function
  dependency `AppleARMFunction::withProvider`; there is no clock-provider,
  frequency, LPO, TCXO, or 32-kHz symbol/import.
- The Bluetooth UART driver consumes `nclk` for baud calculation only. The
  32-kHz strings `clk32-clock-enable-addr` and `clk32-clock-enable-val` in the
  kernelcache belong to the multitouch SPI personality, whose ADT clock tuple
  is `KLCT [8, 100, 32768]`; they are not properties of the Bluetooth node.
- The board NVRAM says `xtalfreq=37400`, which is the BCM reference crystal in
  kHz (37.4 MHz), not a 32.768-kHz sleep clock.

This does **not** prove that the module does not require an LPO electrically;
it proves that the iOS Bluetooth path identified here does not turn one on.
The module may have a supplied/on-board clock, or the clock may be enabled by
an earlier board-level stage not represented by `AppleBluetooth`.

## 2. Wi‑Fi firmware as a Bluetooth prerequisite

**Result: coexistence support is proven; BT power-up dependency is not.**

The proven BCM4350C2 NVRAM contains:

```text
btc_mode=1
device_wake_opt=1
host_wake_opt=0
uart_wake_gpio=2
xtalfreq=37400
```

The firmware image exports strings for `btc_select_profile`, `btc_params%d`,
`btc_flags`, `bt_regs_read`, `wci2_config`, `wci2_msg`, `wci2_txind`, and the
`mws_*` coexistence controls. This is enough to establish that the Wi‑Fi
firmware knows about the Bluetooth side and can arbitrate shared radio time.
It is not evidence that Wi‑Fi boot asserts BT reset, enables a BT rail, or
releases a BT core reset. `bt_regs_read` is a firmware diagnostic/control
surface, not a demonstrated boot-time action.

The host-side evidence points the same way:

- Linux's working Wi‑Fi attach does not issue a host Bluetooth power/reset
  operation.
- The iOS Bluetooth driver independently powers the radio through PMU GPIO2;
  its start path has no call into the Wi‑Fi driver and no Wi‑Fi readiness
  prerequisite.
- The Wi‑Fi static analysis found Apple's extra host actions to be PCIe wake,
  deep-sleep, mailbox, and ChipCommon GPIO handling. Nothing there is a
  proved BT-core enable write.

Therefore the Wi‑Fi dependency remains plausible only on the **device-side**:
Wi‑Fi firmware might set a BCM backplane bit as part of combo-chip startup
without exposing that fact through the host driver.

## What static analysis closed

| Question | Status | Confidence |
|---|---|---|
| Does `AppleBluetooth` enable a 32-kHz/LPO clock? | No path found | High |
| Is a 32-kHz clock required by the module? | Unknown electrically | Low |
| Is BCM4350C2 Wi‑Fi/BT coexistence configured? | Yes (`btc_*`, WCI2/MWS, NVRAM) | High |
| Does Wi‑Fi boot demonstrably power/release BT? | No evidence | Medium |

## Only remaining high-value test

Use the existing Wi‑Fi diagnostic kernel and take **read-only** ChipCommon/
backplane snapshots at these points:

1. before Wi‑Fi firmware start;
2. after the firmware banner and normal Wi‑Fi attach;
3. after asserting PMU GPIO2 and AP BT_WAKE.

Compare only registers already on the diagnostic safe list. A repeatable
change in a BT-core/reset/clock-related region after Wi‑Fi attach would support
the dependency hypothesis. No unknown-register sweep and no backplane write is
justified. This test requires one DFU cycle; it is not a software-only step.

## Practical conclusion

Do not spend another software-only round trying to invent a Bluetooth LPO
enable sequence from the current evidence. The LPO branch is closed at the
iOS-driver level. The next useful work is either the read-only Wi‑Fi snapshot
above, or a hardware timing/reset experiment; both require a diagnostic kernel
run. The current UART/PMU findings do not identify a further host-side static
fix.
