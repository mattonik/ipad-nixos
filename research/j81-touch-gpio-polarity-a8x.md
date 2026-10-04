# J81 touch GPIO polarity from Apple's AP GPIO provider

Date: 2026-10-04. Static analysis only (Ghidra, iPad5,3 iOS 8.1 12B410
kernelcache, SHA-256 `19c277d6...cc28bf`; classes `AppleS5L8960XGPIOFunction`
and `AppleS5L8960XGPIOIC`, plus `AppleMultitouchSPI`). No device access.
Labels: **E** read in the decompilation or ADT, **I** inference, **U** unknown.

This resolves the "Apple GPIO-provider polarity" gap in
[`j81-touchscreen-bringup-offline.md`](j81-touchscreen-bringup-offline.md).

## How an `OIPG` function descriptor is interpreted (E)

An ADT `function-*` property whose selector is `OIPG` is handled by
`AppleS5L8960XGPIOFunction`. Its init copies 16 bytes of the property into the
object: `phandle`, `OIPG`, then the **pin** (dword) and **four flag bytes**
`f0 f1 f2 f3`. Its `callFunction(value, readback, mode)` does:

- **write a logical value `v`:** the GPIO controller's data setter is called
  with the electrical level **`v ^ f1 ^ 1`**; with `f1 = 1` the level equals
  `v` (active-high) and with `f1 = 0` it is inverted (active-low);
- **read:** the logical result is `electrical ^ f1 ^ 1`;
- **mode argument** (when present): `0 -> 0`, `1 -> 1`, `2 -> f0`, `3 -> f3`,
  passed to the controller's pin-mode setter; other values return an error.

The controller's data setter is a thin wrapper over its pin-mode setter
(`mode 0xe` drives low, `0xf` drives high), which sets bit 0 of the pin's own
32-bit configuration word to the level directly. There is no second inversion
below this layer, so the electrical level is exactly `v ^ f1 ^ 1`.

## J81 touch pins (E for the arithmetic, from the private ADT bytes)

| Function | Pin | Flags `f0 f1 f2 f3` | Electrical level for logical 1 | Result |
| --- | ---: | --- | --- | --- |
| `function-reset` | 82 | `01 00 01 00` | low | **active-low reset** |
| `function-enable_cs` | 51 | `01 01 00 00` | high | active-high |
| `function-power_ldo` | 95 | `01 01 00 00` | high | active-high |
| `function-display_sync` | 55 | `01 01 00 02` | high | active-high; `f3 = 2` only affects mode-3 callers |

For reset, `AppleMultitouchSPI` calls its reset helper with **1 to assert and 0
to release**: with 1 it logs the reset line, waits the minimum interval, and with
0 it first sends a dummy SPI transfer and, after release, waits the personality's
reset-deassert delay (15). Combined with the table, asserting reset drives GPIO82
**low** and releasing it drives GPIO82 **high**. That confirms the existing
active-low DTS draft as **E**, not just **I**.

## New: "ensuring S_CLK is high" (E)

Before releasing reset, the driver sends one 16-byte full-duplex transfer: TX
`1a a1` followed by seven `18 e1` words (the same filler pattern as the long
ACK), RX ignored. Its log line is "ensuring S_CLK is high" / "initiating dummy
transfer". Likely purpose: leave the SPI clock line at its idle level before the
controller wakes. Whether that means clock idle-high (CPOL = 1) is **I**; the
code does not set the mode there. It does tell us the reset-release sequence
must include an SPI-clock-idle step, so a Linux sequence that releases reset
without it would differ from Apple's.

## What this settles and what it does not

- Settled: electrical polarity and logical assert/deassert values for reset and
  the other three touch GPIOs.
- `power_ldo` pin 95 is active-high; Apple enables the D2207 analog source
  first, then drives pin 95 high, and reverses at power-off (earlier audit).
- Still **U**: the inter-rail delay, the interrupt trigger polarity (separate
  GPIO84 path), the SPI mode/clock, and the clock block's register meaning
  ([`j81-touch-clock-kclt-a8x.md`](j81-touch-clock-kclt-a8x.md)).

## Not done / not safe

No GPIO was touched. These are properties of Apple's code, and nothing here
authorizes a GPIO write. Pin 95 and 82 remain unclaimed in the Linux baseline.
