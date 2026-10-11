# iOS 8.1 UART3 3-Mbaud static analysis (2026-10-11)

Software-only analysis of the decoded iPad5,3 12B410 kernelcache. The
`AppleSamsungSerial` embedded Mach-O is at load address
`0xffffff8002d75000` (kernelcache file offset `0xd0c000`). No hardware,
firmware bytes, private data, or build was used.

## What AppleSamsungSerial actually programs

The baud routine starts at `0xffffff8002d76bb8`. Before opening the port, the
driver reads these platform properties:

```text
nclk             -> this + 0x120
uart-version     -> this + 0x11c
no-flow-control  -> this + 0x11d/related mode state
function-rts/tx/rx -> platform-function handles
```

For a requested baud in `0xffffff8002d76bd8`, the driver computes from the
`nclk` value; it does not use a hard-coded 24 MHz constant:

```text
scaled = (nclk << 17) / requested_baud
```

It then searches a divider/oversampling candidate and stores the result in the
UART register block. The relevant stores are:

```text
base + 0x28  divider register (the Samsung UBRDIV position)
base + 0x34  fractional/baud adjustment register
base + 0x38  additional divider-slot/baud-mode register
```

The driver also writes the FIFO/control register at `base + 0x08`; flow-control
and TX/RX mode are configured separately. The baud routine does not merely
write UBRDIV and stop.

The `uart-version` branch is decisive. At
`0xffffff8002d76c20..0xffffff8002d76c64`, version 0 and version 1 select
different candidate ranges and divisors. Version 1 searches the alternate
divider mode down to a factor of 4, while the legacy path searches the normal
16-based mode. This is the static explanation for reaching a rate that a
24-MHz `/16` configuration cannot produce: iOS uses the UART's version-1
alternate divider/oversampling path, not a magic baud value.

The exact semantic label of the factor-4 mode is not present in the stripped
binary, so this note does not claim whether Apple calls it 8x or 4x sampling.
The register writes and the version-dependent branch are direct evidence; the
sampling-name interpretation is an inference.

## Why the current Linux driver tops out near 1.5 Mbaud

The pinned `drivers/tty/serial/samsung_tty.c` describes Apple S5L as:

```text
num_clks    = 1
clksel_mask = 0
has_divslot = false
```

Its `set_termios()` path computes the ordinary Samsung divisor
`(clock + 8*baud)/(16*baud) - 1`, writes only `UBRDIV` (offset `0x28`), and
does not program the Apple baud registers at `0x34` and `0x38`. The J81 DT
currently points both clock names at the same 24-MHz `clkref`; with
`num_clks = 1`, the second clock is ignored anyway.

Therefore a DT-only change cannot reproduce iOS behavior with the current
driver. The smallest principled Linux change is an Apple S5L `uart-version=1`
baud path that mirrors the alternate candidate search and writes the three
Apple baud registers. A faster clock source may still improve margin, but it is
not required by the iOS evidence: iOS explicitly consumes `nclk` and selects a
different UART divider mode.

## 32.768-kHz result

The target `AppleBluetooth` and `AppleSamsungSerial` images contain no
Bluetooth-specific LPO/TCXO or 32-kHz clock lookup. The serial driver consumes
`nclk` only. Kernelcache strings for `clk32-clock-enable-addr` and
`clk32-clock-enable-val` belong to the multitouch SPI personalities, not the
Bluetooth node. This is negative evidence, not proof that the BCM module has no
external sleep clock; it does mean iOS does not enable one through the
Bluetooth UART path identified here.

## Consequence and test proposal

The next software/hardware gate is a minimal Apple S5L UART patch implementing
the version-1 divider/register sequence, then repeating the existing bulk
transmit timing and the 3-Mbaud HCI Reset probe. Success criterion: a 600,000
byte transmit requested at 3,000,000 takes about 2 seconds, and the controller
returns an HCI event. No firmware or HCD change should be mixed into that test.
