# J81 KLCT and PMGR resource audit

Date: 2026-10-04

## Result

The missing touch-clock resource should be tracked as an **unresolved
dedicated KLCT register and dispatch path**, not as an established missing
index in the generic PMGR power-state array. Earlier notes traced a generic
power-state helper and a dedicated touch-clock helper in different Apple
driver generations, then treated them as the same register mechanism. The
public kernel's bit definitions contradict that interpretation.

This audit narrows the next binary analysis and corrects two potentially
misleading shortcuts. It does not discover the KLCT address, enable a driver,
or make any device transaction. The private Apple binaries/ADT were not
available here; their earlier disassembly is treated as recorded evidence,
not independently revalidated source.

## Public sources inspected

All Linux references use the project's exact Hoolock pin
`6831bc701a6ce059e71e5aaa9488c9195bea6927`:

- [PMGR power-state driver](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/drivers/pmdomain/apple/pmgr-pwrstate.c),
  Git blob `82c33cf727a825d2536644d2fe09c0282acd1ef8`.
- [T7001 PMGR nodes](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/arch/arm64/boot/dts/apple/t7001-pmgr.dtsi),
  Git blob `7321cfdcd18965e40edbbdfc5edc91e4b1e8eb16`.
- [m1n1 PMGR implementation](https://github.com/AsahiLinux/m1n1/blob/ce2b8a43cea4220b602af1005dc9dbfc59c9624e/src/pmgr.c),
  Git blob `c74acac2c8e25771e2806ea491d876974b857291`, is an independent
  reference for separating a device ID from its register location. It is
  not substituted for this project's bootloader pin or asserted to decode
  every J81 ADT field without checking that ADT.

The [older touch investigation](../docs/plans/2026-09-09-j81-touch-spi3.md)
records the Apple touch-clock helper layout and the J81 KLCT tuple. The
existing `0008-t7001-add-spi3-node.patch` records SPI3's ADT ID `0x4d`.

## Three register domains must stay separate

| Resource | Evidence | What it does not establish |
| --- | --- | --- |
| SPI3 generic power state | Pinned DTS: `ps_spi3`, PMGR offset `0x20198`, parent `ps_sio_p` at `0x201f8`; Linux uses `apple,pmgr-pwrstate` | Touch reference-clock location or rate |
| Dedicated KLCT clock | Earlier Apple helper trace: gate-off bit 31, apply bit 19, busy bit 18, ten-bit divider; J81 tuple requests 32,768 Hz | A generic PS-array index, physical address, or equivalence across Apple driver generations |
| Touch ASIC clock/calibration registers | Earlier personality/driver trace: `0x1000305c`, `0x10003518`, etc., accessed over SPI | SoC PMGR MMIO mapping or upstream clock state |

The pinned generic power-state driver defines the following conflicting
meanings for the same bit positions:

| Bits | Generic PMGR PS register | Earlier dedicated KLCT helper trace |
| --- | --- | --- |
| 31 | `RESET` | Gate off |
| 28 | `AUTO_ENABLE` | No corresponding meaning established |
| 19 | Part of `PS_MIN[19:16]` | Apply |
| 18 | Part of `PS_MIN[19:16]` | Busy |
| 9:0 | Several status/target fields, including actual state `[7:4]` and target `[3:0]` | Divisor |

In particular, `apple_pmgr_ps_is_active()` checks actual state, or active
target plus auto mode. Bit 28 alone is not the driver's definition of
clock-on status. Reset assertion also sets bit 31 deliberately. The old
phrase "every clock gate ... bit 28 enable/disable control+status" is too
broad, and combining KLCT's bit layout with this PS array could assert a
reset or change minimum power state. The source shows incompatible layouts;
it does not prove where the dedicated layout lives.

The earlier 101-entry bound belongs to one reverse-engineered helper in
one binary. It is not a bound on all PMGR resources: the pinned T7001 DTS
also contains `ps_sep` at `0x20400` and VENC subdomains at `0x21000` and
above. Those observations do not identify the touch register either.

## ADT device IDs are not register-array indices

There is a useful concrete counterexample within already documented J81
resources:

| Calculation | Result |
| --- | --- |
| Existing SPI3 ADT ID | `0x4d` |
| Correct SPI3 PS offset in pinned DTS | `0x20198` |
| Corresponding position within the `0x20000`/8-byte PS array | `0x33` |
| Incorrect shortcut `0x20000 + 0x4d * 8` | `0x20268`, the pinned `ps_usb2host1` node |

Therefore a future investigator must not substitute an ADT gate/device ID
directly into the old helper's array formula. m1n1 makes this distinction
explicit: `pmgr_find_device()` matches an ID, then `pmgr_device_get_addr()`
uses the record's PS-register group and `addr_offset << 3` (or its newer
group/offset format). Resolving ID, group and register index are separate
steps. The counterexample compares the recorded J81 ID with public DTS;
it does not re-decode the private J81 device table.

## Rate and argument precision

Under the previously recorded integer-divider interpretation:

```
requested = 32768 Hz
divisor = floor(24000000 / requested) = 732 = 0x2dc
modeled output = 24000000 / 732 = 32786.8852459... Hz
relative error = +576.331967... ppm
```

So 32.768 kHz is the **requested** rate, not an exact output demonstrated
by the arithmetic. No waveform was measured and no fractional-divider
behavior is established by this calculation.

The historical writeup also describes a disable call passing `8` and `100`
while naming the lower-level parameters `delayUs` and `divider`, then
concludes that 100 is the disable delay. That prose is not sufficient to
resolve register argument order. Preserve the raw tuple `[8, 100, 32768]`
and the recorded delay interpretation, but verify AArch64 argument registers
and branch-specific use before implementing the disable path. This audit
does not change the interpretation to a different guessed sequence.

## Reproducible offline audit

Run against local copies of the two exact Linux files above:

```sh
python3 kernel/test_j81_pmgr_resources.py \
  --driver /path/to/pmgr-pwrstate.c \
  --dts /path/to/t7001-pmgr.dtsi
```

The script verifies Git blob hashes, parses all PS-node unit addresses and
register offsets, checks the SPI3 parent, demonstrates the USB-host
counterexample, checks conflicting power-state bit meanings, and prints
the conditional divider arithmetic. It performs no network, MMIO, GPIO,
PMIC, or kernel operations. This is a source-consistency audit, not native
execution of a clock driver or validation of timing on silicon. It is
standalone; existing default/offline-runner behavior is unchanged.

## Narrowed next investigation on the laptop

1. In the symbol-bearing ApplePMGR build, follow the dedicated
   `enableTouchClock` field back to its initializer; record the register
   group, offset, and original binary hash. A gap at group 3 is a hypothesis,
   not a mapping.
2. In the matching iPad5,3 iOS 8.1 binary, follow the KLCT token's stored
   fields and the call that actually consumes it. Preserve that build's
   class/field meanings rather than transferring offsets from iOS 10.3.
3. Record the effective-address calculation and relevant argument registers
   at the actual clock register read/write, including enable and disable.
   Reconcile that layout with the dedicated helper; only then define a
   clock provider and its timeout/locking behavior.
4. If resolving any generic power-state resource along that trace, decode
   the matching ADT device/group record before calculating an offset.

SPI3 registration proves its existing provider is usable; it does not prove
that the external touch clock is configured. The J81 child remains disabled.
