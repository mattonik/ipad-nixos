# D2207 GPIO2 public static analysis (2026-10-10)

Software-only review of the public unstripped-kext repository
`userlandkernel/ios-unstripped-kexts` at commit `96ca2b7f012ab20cf0274ea593d0e9a03f576764`.
No device access or build was used.

## New evidence

Both public `AppleD2207PMU` binaries (`10.0/T8010` and `10.3/s8000`) export the
same GPIO startup helper:

```text
AppleD2207PMU::setGPIODefaults(unsigned char *)
```

The helper:

1. reads 21 GPIO configuration bytes beginning at GPIO index 0;
2. merges a 42-byte mask/value table supplied by the caller (two bytes per GPIO);
3. writes the resulting 21-byte configuration bank back;
4. is called from `AppleD2207PMU::start` before the PMU finishes initialization.

The public kext also contains the expected `gpio-activate-defaults`,
`gpio-suspend-defaults`, `gpio-quiesce-defaults`, and `gpio-pin-config` property
names. This is not an unlock sequence: it is a board-data-driven GPIO default
initialization path.

The 10.0 and 10.3 implementations are materially identical. The public
`AppleBluetooth` binaries also contain `function-power_enable`,
`function-bt_wake`, and `function-bt_reset` symbols/strings, confirming that
Bluetooth power is driven through the Apple ARM-function provider rather than
through the UART driver itself.

## Relevance to J81

The J81 ADT dump contains the Bluetooth `function-power_enable` descriptor
(PMU GPIO2) but does not show the four GPIO-default property names. Therefore
the next static question is whether those properties are stored in a different
ADT node, synthesized by an earlier Apple driver, or absent on this board.

A complete-text search of the captured J81 ADT confirms that absence: the dump
contains `function-power_enable`, the `pmu,d2207` node, and the GPIO controller
metadata, but no `gpio-activate-defaults`, `gpio-suspend-defaults`,
`gpio-quiesce-defaults`, or `gpio-pin-config` property. This makes a hidden
42-byte table in the captured ADT unlikely, though it cannot rule out a table
created by an earlier boot-stage component.

This does **not** justify a whole-bank write from Linux. The target iOS 8.1
kernelcache still needs to be checked for the exact property lookup and the
per-pin table. GPIO2 remains `0x0402`; the old `0x03e6` write was unrelated.

## Next minimum-cost analysis

1. Locate the iOS 8.1 `AppleD2207PMU::start` equivalent and identify the exact
   property passed to `setGPIODefaults`.
2. Search the complete J81 ADT, not only the PMU node, for that property or its
   raw 42-byte table.
3. Compare the target's `gpio-pin-config` handling with the public 10.x helper.
4. Only if this reveals a GPIO2 default byte should a narrowly scoped hardware
   test be considered.

The public binaries expose an initialization dependency, but they do not yet
prove that missing defaults explain the Linux Bluetooth failure.
