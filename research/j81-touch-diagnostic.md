# J81 touch power-up diagnostic payload

Date: 2026-10-04. **Built and statically verified; not run on hardware.**
Payload `.#packages.x86_64-linux.m1n1-hoolock-touch-diag` (tablet payload plus
`/usr/bin/touch-diag`, source [`boot/touch-diag.c`](../boot/touch-diag.c)). No
kernel change, no touch child, no SPI transfer, no firmware.

## What it tests

One question, from the plan in
[`j81-touchscreen-bringup-offline.md`](j81-touchscreen-bringup-offline.md): after
Apple's power order and a single reset release, does the controller raise its
boot interrupt on GPIO84? The inputs now all come from Apple's iOS 8.1 driver:

| Step | Source |
| --- | --- |
| reset line GPIO82, **active low** | [GPIO polarity](j81-touch-gpio-polarity-a8x.md) |
| touch clock at PMGR+`0x1e000`, divider `0x2dc`, settle 8/100 | [KLCT decode](j81-touch-clock-kclt-a8x.md) |
| LDO14 enable `0x0084` bit 2, then GPIO95 (active high) | earlier D2207 decode; voltage `0x0398` read, never written |
| reset-deassert delay 15 ms | AppleMultitouchSPIJ82 personality |

## Commands

- `touch-diag` / `touch-diag plan`: prints the sequence, touches nothing.
- `touch-diag status`: read-only snapshot (PMU `0x0084`/`0x0398`, the clock
  register, GPIO config words) through `/dev/i2c-0` and read-only `/dev/mem`.
- `touch-diag run --execute --approve-pmu-write`: the sequence. Without both flags
  it only prints the plan and exits non-zero.

## Safety design

- Refuses to start unless LDO14 is off and its voltage register is `0x14`.
- Order: reset asserted -> touch clock -> LDO14 -> GPIO95 high (10 ms) -> reset
  released (15 ms) -> watch GPIO84 up to 2 s. Each PMU write is read back.
- **Unwinds on success, error or SIGINT/SIGTERM**, in reverse: reset asserted,
  GPIO95 low, LDO14 enable restored to its original byte, clock disabled with
  Apple's disable sequence, and it prints the restored values.
- Deliberately omitted: the dummy SPI transfer Apple does before reset release
  ("ensuring S_CLK is high") and `display_sync` (GPIO55). Both are logged as
  unknowns; their absence could make a negative result inconclusive.
- GPIO51 (SPI3 chip select) is never requested; the SPI3 pinmux owns it.
- The 10 ms rail delay is conservative; Apple's value is unknown.

## Reading the result

`RESULT irq_edge=<0|1> level_before=<..> level_after=<..>` is printed before the
unwind. An edge on GPIO84 within 2 s of reset release is the success signal; the
trigger polarity is unknown, so both edges are watched. **No edge is not proof of
failure**: the omitted SPI dummy transfer and display sync, the unknown rail delay
and the unverified inter-rail ordering all remain possible causes. A hard failure
(abort lines, a clock busy timeout, an unreadable LDO14) is a more useful negative.

## Approval

`run` writes the D2207 PMU (LDO14 enable) and the PMGR touch-clock register,
neither previously written live. Per the project's standing rules it needs the
user's explicit go-ahead at run time; this build does not grant it.

## Hardware result 1, 2026-10-04: read-only `plan` and `status`

Booted `m1n1-hoolock-touch-diag` (cold boot, recorded session, private). Only
`plan` and `status` were run; nothing was written. Output of `status`:

| Item | Value | Reading |
| --- | --- | --- |
| PMU `0x0084` LDO14 enable | `0x00` | rail off (bit 2 clear), as expected |
| PMU `0x0398` LDO14 voltage | `0x14` | the expected 6.0 V setting is already programmed |
| PMGR+`0x1e000` touch clock | `0x800002ee` | **gate off, busy 0, divider 750 (`0x2ee`)** |
| GPIO82 (reset) config word | `0x00072602` | output, data bit 0 = low (iBoot leaves reset electrically low) |
| GPIO95 (power_ldo) config word | `0x00072602` | output, low |
| GPIO55 (display_sync) config word | `0x00072a82` | output, low |
| GPIO51 (SPI3 CS) config word | `0x00072623` | output, high (SPI3 pinmux, idle high) |
| GPIO84 (touch IRQ) config word | `0x00070381` | input, bit 0 = 1: the line idles high |

Observations:
- The preconditions of `touch-diag run` hold: LDO14 off, voltage `0x14`.
- iBoot leaves the clock **gated off with a pre-programmed divider of 750**
  (24 MHz / 750 = 32 kHz), not Apple's runtime `0x2dc` (732). The enable path
  rewrites the divider, so the original value will differ in that field after the
  test even though the gate state is restored; the tool prints both.
- The reset line is already driven low, i.e. already asserted, which matches the
  active-low decode. The IRQ line idles high, so a falling edge is the likely
  boot-interrupt trigger (still **I**).
- The charging policy kept 2400 mA (log: `limit 2400000 uA (temp 321 deciC)`), and
  no `touch-diag` process was running.

## Hardware result 2, 2026-10-04: the controller raises its boot interrupt

The user ran `touch-diag run --execute --approve-pmu-write` over SSH after giving
the go-ahead (the automation permission layer had blocked the agent from issuing
the same command). Output:

```text
snapshot: LDO14 enable 0x00 voltage 0x14 clock 0x800002ee
step 1: reset asserted (logical 1, drives low)
step 2: touch clock enable          -> clock register now 0x000802dc
step 3: LDO14 enable                -> LDO14 enable reads 0x04
step 4: GPIO95 high
step 6: release reset               -> IRQ edge (falling) after ~0 ms
RESULT irq_edge=1 level_before=1 level_after=0
unwind: reset asserted, GPIO95 low, LDO14 enable restored 0x00 (reads 0x00),
        clock disabled -> register 0x800002dc (was 0x800002ee)
```

Read-only `status` afterwards: LDO14 enable `0x00`, voltage `0x14`, clock
`0x800002dc` (gate off, busy 0, divider 732), GPIO82/95 `0x00072602` (driven low),
GPIO51/55 unchanged, charging limit still 2400 mA. No SPI transfer, no firmware.

**What it establishes (E):**
- The inferred power order works on J81: touch clock, D2207 LDO14, GPIO95 high,
  reset release leaves the touch controller powered and **GPIO84 falls** and stays
  low (idle high before, low after). That is the boot interrupt Linux's Z2 driver
  waits for, so the controller is alive and the reset/power polarities decoded
  from Apple's GPIO provider are right.
- The touch-clock enable sequence (new register `0x20e01e000`, divider `0x2dc`)
  completed with the busy bit clearing at once; the D2207 LDO14 enable (`0x0084`
  bit 2) wrote and read back, and was restored byte-exactly.
- The two Apple steps this diagnostic omitted, the dummy SPI transfer and the
  `display_sync` GPIO55 drive, are **not required to raise the boot interrupt**.
  Whether they are required for the later firmware phase remains **U**.
- The falling edge is the trigger direction (the line idles high), matching the
  GPIO84 idle level in result 1.

**Caveats (I/U):**
- The edge arrived before the first poll (`~0 ms`); the kernel buffered it during
  the 15 ms deassert wait, so the exact latency is unknown and it was not
  distinguished from any earlier glitch. The line stayed low through the end of
  the window.
- After the line request was released, GPIO84's config word reads `0x0000038f`,
  not the original `0x00070381`: the kernel's edge-IRQ setup was not undone by
  closing the request. The word is not persistent across reboot, but a later
  Linux driver must not rely on iBoot's original value.
- The clock register ends with the divider rewritten to 732 (iBoot's 750 is not
  restored), gate off as before.
- This shows the controller wakes; it does **not** show that its SPI protocol
  matches the recovered framing. Next evidence needs SPI traffic.

## What this unlocks

The offline gate in the bring-up note ("KLCT index, GPIO polarities, interrupt
trigger, power order") is now met. The next step would be a **separate, explicitly
approved** SPI experiment: add the touch child to the DT, run Apple's recovered
framing (wake, bootloader ATN/ACK, register read) and *only then* consider
firmware. That needs a decision on SPI3 mode/rate (still unknown) and on how to
express LDO14/clock/GPIO ownership in the kernel.
