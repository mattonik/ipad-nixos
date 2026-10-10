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

## Exact iOS 8.1 decode

The matching iPad5,3 12B410 kernelcache was re-extracted with `ipsw`'s public
key lookup (SHA-256
`19c277d60e0a1185b1e4a1b72cda4f1f550c0b0bf670791542234a6dbbcc28bf`). The
standalone `AppleD2207PMU` image begins at `0xffffff8002b44000`.

In `AppleD2207PMU::start` (`0xffffff8002b45254` onward), the target does the
following through the provider's `getProperty` virtual call:

```text
gpio-activate-defaults  -> this + 0x168
gpio-suspend-defaults   -> this + 0x170
gpio-quiesce-defaults   -> this + 0x178
gpio-pin-config         -> this + 0x180
```

It then checks `gpio-pin-config`'s byte length against `0x54` (84 bytes). If
valid, it passes the activate-defaults buffer at `this + 0x168` to
`0xffffff8002b45d8c`, which:

1. reads 21 GPIO config bytes with `readGPIOConfig(0, ..., 21)`;
2. merges 21 mask/value pairs;
3. writes the 21-byte result with `writeGPIOConfig(0, ..., 21)`.

This closes the property-path question. The complete J81 ADT contains none of
these four properties, so this default-table path is skipped for J81. The
Bluetooth `function-power_enable` descriptor remains a separate later
`AppleARMFunction` call; the missing defaults do not explain the failed GPIO2
write by themselves.

## Exact iOS 8.1 AppleBluetooth startup sequence

The embedded `AppleBluetooth` Mach-O was extracted from the same decoded
kernelcache (load address `0xffffff8002c4b000`, SHA-256 above) and disassembled
directly. The `BTReset::start(IOService *)` body begins at
`0xffffff8002c4b930`.

The relevant order is:

```text
0x2c4b948  lookup("function-bt_reset")
0x2c4b97c  lookup("function-bt_wake")
0x2c4b9b0  lookup("function-power_enable")
0x2c4b9c8  call the returned power-enable function
0x2c4b9e4  register the btreset/btwake/btpoweroff character devices
0x2c4bb74  call the superclass start path
```

There is no delay, second rail/clock lookup, UART configuration, transport
encoding handling, or reset/wake assertion in this startup body. The reset and
wake function handles are only used by the character-device callbacks; on J81
the reset handle is absent. The power callback is the only automatic radio
enable action at driver start.

This closes the highest-value static question: `transport-encoding = 3`,
3-Mbaud setup, and any HCI-side sequencing are outside this GPIO helper (in the
Bluetooth transport/userland path), not hidden in `AppleBluetooth.kext`.
