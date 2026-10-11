# UART3 clock source: static result (T7001 / iOS 8.1)

This note answers the clock brief without adding a PMGR write or building a
kernel. The register capture in `2026-10-11-uart3-register-capture.md` is the
runtime evidence; the iOS kext disassembly and Hoolock PMGR driver are the
static evidence.

## What `nclk` is

**Direct evidence:** `AppleSamsungSerial::start` obtains a value through its
parent/provider using the key `"nclk"` and stores the returned numeric value at
`this+0x120`. The baud routine consumes that value arithmetically. It does not
read the two ADT `clock-ids` cells in the baud routine, and `nclk` is not the
integer clock-gate ID.

**Inference:** the provider/framework resolves the ADT clock description and
exports the resulting rate as the `nclk` property/function. The stripped
serial kext does not contain the provider's clock table, so it cannot map
`0x115` or `0x4` to a PLL and divider by itself.

The practical distinction matters: the numeric `nclk` input used by the
algorithm and the physical clock arriving at the UART divider need not be the
same named object. Hardware shows the current Linux path receives 24 MHz, while
the Apple baud-register values only make sense for a 48-MHz physical input (or
an undocumented equivalent divide-by-two inside the clock path).

## Does iOS set the clock at UART open?

**Direct evidence:** the `AppleSamsungSerial` start path contains no literal
`enableDeviceClock`, `setClockFrequency`, divider write, or PMGR frequency
programming sequence. It reads the provider's `nclk`, configures UART
registers, and later uses the generic device/provider machinery for the normal
clock-gate lifecycle. The baud routine itself writes only UART offsets
`+0x08`, `+0x28`, `+0x34`, and `+0x38`.

**Conclusion:** iOS does not frequency-program the UART in the serial baud
routine. A generic AppleARM device-clock provider may enable the ADT gate when
the device starts, but no static evidence here shows it changing the source
rate from 24 to 48 MHz at open. The faster source, if present, is inherited
from iBoot/PMGR state or selected by a separate clock provider not traced in
this kext.

## PMGR gate register layout

For gate `g`, the captured register is `PMGR + 0x20000 + 8*g`. Hoolock's
`apple-pmgr-pwrstate.c` gives the following names:

| bits | Hoolock name | meaning |
|---|---|---|
| 3:0 | `PS_TARGET` | requested power state |
| 7:4 | `PS_ACTUAL` | reported power state |
| 8 | `WAS_PWRGATED` | sticky/history flag: device was power-gated |
| 9 | `WAS_CLKGATED` | sticky/history flag: device was clock-gated |
| 10 | `DEV_DISABLE` | device-disable control |
| 11 | `PARENT_OFF` | parent-off indication/control |
| 19:16 | `PS_MIN` | minimum power-state field |
| 27:24 | `PS_AUTO` | automatic power-state field |
| 28 | `AUTO_ENABLE` | automatic enable control |
| 31 | `RESET` | synchronous reset |

Therefore bits 9:8 are **not** a two-bit UART clock-source selector. The
observed values (`00` on UART3, `01` on UART5, `10` on UART6, `11` on UART8/9)
are compatible with per-instance gate history. Bits 28:24 likewise describe
automatic power management, not a baud divider. The gate register can enable
or disable the UART clock domain; it does not expose the frequency selection
needed for 3 Mbaud.

## Which register feeds the baud generator?

**Closed:** UART3's own UCON clock-select bits, UFCON, `+0x28`, `+0x34`, and
`+0x38` cannot raise the measured 24-MHz rate. The read-only experiment
measured the legacy formula `24 MHz / (16 * (UBRDIV + 1))`, with the slot
registers only reducing it.

**Not identified:** neither the UART block nor the PMGR gate register exposes
the separate source/divider that would provide 48 MHz. The ADT's first clock
ID (`0x115`) is the leading candidate for the UART functional/baud clock and
the second (`0x4`) for its companion clock, but no T7000/T7001 clock table in
the available stripped artifacts resolves either to a PLL, reference, or
divider value. This remains a static-analysis gap, not evidence that bits 9:8
are the answer.

## Safe next step and Linux impact

There is no safe DT-only change justified yet. Do **not** write the PMGR gate
word or guess a mux/divider field. The smallest eventual Linux change is
likely one of:

1. model the real provider for ADT clock IDs `0x115` and `0x4`, if a clock
   table is recovered; or
2. add a dedicated T7001 UART baud-clock provider with an explicitly decoded
   source/divider register, then make `clk_uart_baud0` consume it.

Before any write, take read-only snapshots of:

- UART3 `UCON`, `UFCON`, `+0x28`, `+0x34`, `+0x38`;
- PMGR gate `0x53` and neighboring UART gates `0x52`, `0x55`, `0x56`, `0x58`;
- candidate clock-controller windows discovered from the AppleT7000/AppleARM
  clock provider, if and only if their mapping is independently established.

The current evidence supports changing the Linux clock model only after the
last item is found. It does not support a blind PMGR write.

## Bottom line

`nclk` is a provider-supplied numeric clock property, not the PMGR gate ID.
The PMGR gate word controls state and records gate history; bits 9:8 are not a
baud-clock mux. iOS's 3-Mbaud path still requires finding the separate clock
provider/source behind ADT clock ID `0x115` (and its companion `0x4`), or
proving that the provider's nominal 24-MHz `nclk` is transformed to a 48-MHz
UART input elsewhere. No hardware write is warranted from the present data.
