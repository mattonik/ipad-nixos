# J81 touch clock: the iOS 8.1 `KLCT` handler

Date: 2026-10-04 (corrected the same day). Static analysis only (Ghidra on the
iPad5,3 iOS 8.1 12B410 kernelcache, SHA-256 `19c277d6...cc28bf`; kext
`AppleT7000`, class `AppleT7000PerformanceController`). No device access.
Labels: **E** read in the decompilation or ADT, **I** inference, **U** unknown.

**Correction.** The first revision of this note decoded the metaclass vtable
instead of the instance vtable and described a `TCC_pwrctl` state-field routine.
That was a different function and is withdrawn. The decode below uses the
instance vtable (`0xffffff80031f30a0`) and the actual caller in
`AppleMultitouchSPI`. It matches the iOS 10.3 helper layout recorded in
[`j81-klct-resource-audit.md`](j81-klct-resource-audit.md), which this settles.

## Dispatch (E)

- ADT touch property `function-clock_enable` targets phandle `0x1a` (`pmgr`) with
  selector `KLCT` and three words `8, 100, 32768`.
- Class `AppleT7000PerformanceControllerFunctionEnableTouchClock`; its init reads
  the target data at offsets `8`, `0xc`, `0x10`:
  enable-settle delay (**8**), disable-settle delay (**100**), and the divider
  `24000000 / 32768 = 732 = 0x2dc`, rejected if it does not fit ten bits.
- Its `callFunction(value, readback, mode)` enables when `*mode == 3` and
  disables when `*mode != 3` and `*value == 0`; any other value returns an error.
  `AppleMultitouchSPI` enables with `(NULL, NULL, &3)` and disables with `(&0, NULL, NULL)`.

## The register (E)

The routine works on one 32-bit register at **PMGR base + `0x1e000`**
(`0x20e01e000` with the PMGR at `0x20e000000`; the PMGR base is memory-map 0 of
the controller, confirmed in the same start routine). Bit meanings:

| Bit(s) | Meaning |
| --- | --- |
| 31 | gate off (set = clock gated) |
| 19 | apply |
| 18 | busy (hardware clears when the divider has applied) |
| 9:0 | divider |

**Enable** (value `R` read first):
1. write `R & 0x7fffffff` (clear the gate-off bit);
2. delay the enable-settle time (8);
3. write `(R & 0x7ff7fc00) | 0x2dc | 0x80000` (new divider, apply set, bit 31 clear);
4. poll until bit 18 clears.

**Disable:** clear bit 19 (`R & 0xfff7ffff`), poll until bit 18 clears, then write
`(R & 0xfff7ffff) | 0x80000000` and wait the disable-settle time (100).

Delays are in the driver's delay unit (**I**: microseconds, as the ADT tuple was
previously read). The modeled output is `24 MHz / 732 = 32786.9 Hz`, a
+576 ppm offset from 32.768 kHz; whether the hardware divider is exactly an
integer divide is **U**.

## What this changes

- The "missing KLCT index" is a **single register**: PMGR + `0x1e000`. It is not a
  power-state array entry (the earlier warning against ID-indexing stands).
- Linux has no provider for it; a minimal one is the five steps above on one MMIO
  register, plus the settle delays and the busy timeout.
- Still **U**: the register's value before enable on J81 (never read), and whether
  anything else shares bits outside `0x80080000`/`0x3ff`. The read-modify-write
  masks preserve every other bit, as Apple's code does.

## Not done / not safe

No write was issued. A **read** of `0x20e01e000` is the right first step of any
diagnostic and carries no known risk; the write sequence belongs in a separate,
explicitly approved test that restores the saved original value afterwards.
