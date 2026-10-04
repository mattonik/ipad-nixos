# D2207 PMU GPIO register map correction: GPIO2/GPIO3 are at `0x0402`/`0x0403`

Date: 2026-10-04. Static analysis only (no device access). Supersedes the
"runtime ownership/lock" explanation for the non-persistent GPIO2 write and
the "byte-exact transaction already known" claims in earlier notes.

## Claim

Apple's `AppleD2207PMU` maps GPIO index `i` to its configuration register
with `_index2GPIOAddress`:

```text
i > 0x14        -> 0xffff            (invalid)
i < 0x11        -> 0x0400 | i        (one-byte register)
0x11 <= i <= 0x14 -> 3*i + 0x3e0     (three-byte registers, 0x413...)
```

Earlier project notes used `0x3e0 + 3*i` for **every** GPIO, giving `0x03e6`
for GPIO2 and `0x03e9` for GPIO3. That formula applies only to indices
17-20. The corrected configuration registers are:

| Function | ADT descriptor | PMU pin | **Config register** | Previously assumed |
| --- | --- | ---: | --- | --- |
| Bluetooth `function-power_enable` | `OIPG`, pin 2 | 2 | **`0x0402`** | `0x03e6` |
| Wi-Fi `function-reg_on` | `OIPG`, pin 3 | 3 | **`0x0403`** | `0x03e9` |

The data register used for reads is separate and the earlier notes already had
it right: `0x0063 + (pin >> 3)`, bit `pin & 7` (decompiled in `FUN_ffffff8002b4a010`),
so pins 2 and 3 are bits 2 and 3 of `0x0063`.

## Evidence

- **E1, named symbol, two builds.** Unstripped iOS 10.0 (T8010) and iOS 10.3
  (s8000) `AppleD2207PMU` both export `_index2GPIOAddress(unsigned char)`.
  Disassembly of both is identical: `cmp w1,#0x11; orr w9,w1,#0x400;
  w10 = 3*w1 + 0x3e0; csel lo; cmp w1,#0x14; csel hi -> 0xffff`.
- **E2, the target firmware.** The same branch structure is present, inlined,
  in the iPad5,3 iOS 8.1 (12B410) kernelcache (SHA-256
  `19c277d6...cc28bf`) in at least seven accessors:
  `FUN_ffffff8002b49a60/b49b40` (bulk config read/write),
  `b49c20` (masked config RMW), `b49d44` (set direction),
  `b49e88` (`_setGPIOFunction`), `b4a010` (data read) and `b466b8`.
  Each computes `0x400 | i` for `i <= 0x10` and `3*i + 0x3e0` above.
- **E3, descriptor to index.** `AppleD2207PMUGPIOFunction::initWithTargetData`
  reads the dword at descriptor offset 8 as the index and rejects `> 0x14`;
  `callFunction` passes it unchanged to `_setGPIOFunction`/`_setGPIODirection`.
  The private J81 ADT descriptors are: `function-reg_on` = PMU, `OIPG`, pin 3,
  flag bytes `01 01 00 00`; `function-power_enable` = PMU, `OIPG`, pin 2, flag
  bytes `01 01 00 00`.

## What `_setGPIOFunction` writes (iOS 8.1, from the decompile)

For a requested level the function reads the one config byte at
`_index2GPIOAddress(pin)`, optionally applies a per-pin table entry
(`clear`/`set` bytes from the PMU configuration structure), then:

```text
b = b & 0x1d
level high : b |= 0x02          (descriptor value non-zero, polarity flag set)
mode 2     : b |= 0x40
write b back to the same register (one byte, 16-bit register address)
```

So asserting `WLAN_REG_ON` is, up to the unread per-pin table, the transaction
`04 03 02` (register `0x0403`, data `0x02`), not `03 e9 02`.
**The per-pin table and the current byte at `0x0403` are not yet known**; read
the register first and derive the byte rather than assuming `0x02`.

## Consequences

- **The earlier "ACK but no persistence" result is explained without a
  hidden interlock.** The 2026-09-13/21 GPIO2 attempts wrote `0x02` to
  `0x03e6`. By Apple's own map that is not a GPIO configuration register
  (the region at `0x0300-0x03a0` was already noted as a rail-like table).
  Nothing in those tests exercised `0x0402`.
- **The `0x0400-0x0414` bank has never been read.** Earlier full dumps ended
  at `0x03ff`.
- **Both radios may be powerable from software.** `reg_on` (Wi-Fi, pin 3) and
  `power_enable` (Bluetooth, pin 2) use the same mechanism.
- The "passive logic-analyser capture is the only evidence gate" conclusion in
  the 2026-09-26 PCIe/Bluetooth notes is premature. A software-only read of
  `0x0400-0x0414` comes first.

## Live read-only result, 2026-10-04 (Stage 5H payload, recorded session)

A recorded console session (private manifest under ignored
`artifacts/live/sessions/`; status trailer check `false` = 1, `printf` ok)
read the PMU over `i2ctransfer`. No writes were issued.

```text
0x0400..0x0414 (21 bytes, GPIO 0..20 config):
  09 49 09 09 09 da ba 7b b9 ea fa 7b f8 c8 c8 7b 01 b9 b9 0b b9
0x0060..0x0065 (data registers):  0f 03 42 20 7e 00
0x03e0..0x03ef (the region earlier notes used):  all 00
0x0413..0x041e (indices 17-20 use the 3-byte stride):  0b b9 b9 b9 b9 b9 b9 b9 b9 b9 00 00
```

- The `0x0400` bank is a real, populated GPIO configuration bank. The
  `0x03e0` region is all zero, consistent with it not being GPIO state.
- **GPIO2 (`power_enable`) = `0x09`; GPIO3 (`reg_on`) = `0x09`.** Data bits 2
  and 3 of `0x0063` (`0x20`) are low, so both radios are unpowered.
- Pins that are configured as driven high elsewhere in the bank read `0x0b`
  (for example the first byte of the 3-byte bank). That fits Apple's
  `_setGPIOFunction`: `0x09 & 0x1d = 0x09`, `| 0x02 = 0x0b`. So bit 1 is the
  output level and `0x09` is the output-low configuration.
- **Predicted assert for pin 3: write `0x0b` to register `0x0403`**; restore is
  `0x09`. The per-pin table from `_getPMUConfig` could in principle alter the
  result and is still undecoded, but the observed `0x09`/`0x0b` pair matches
  the formula without it.

## Live write result, 2026-10-04: REG_ON assert persists

With explicit approval, one write was issued in a recorded session:
`i2ctransfer -f -y 0 w3@0x3c 0x04 0x03 0x0b` (register `0x0403`, data `0x0b`).

```text
baseline  0x0403 = 0x09   0x0063 = 0x20
immediate 0x0403 = 0x0b   0x0063 = 0x20
+1 s      0x0403 = 0x0b
+6 s      0x0403 = 0x0b
```

- **The write persisted**, unlike every earlier attempt, which targeted
  `0x03e6`. This confirms the corrected register map and the `0x09`/`0x0b`
  (`b & 0x1d | 0x02`) model. The earlier "runtime ownership/lock" hypothesis
  is withdrawn.
- `0x0063` stays `0x20`. That is expected: Apple's data read first switches the
  pin to input mode (`FUN_ffffff8002b49d44(pin, 1)`), so the data register is
  not a level readback of an output pin. Do not read it as "pin still low".
- A PCIe rescan at +1 s and +6 s found nothing beyond the root port. Expected:
  the host sequence (PERST release and link start) ran at boot with the chip
  unpowered. Apple's order is REG_ON, 100 ms, then PCIe port enable.
- State left asserted (`0x0403 = 0x0b`) for the next step. Restore value is
  `0x09`.

Next evidence step: reboot into the same payload **without** restoring and read
`0x0403` immediately after boot. If the PMU keeps the setting across the AP
reset, the existing PCIe sequence runs with the chip already powered.

## Proposed evidence ladder (step 1 now done)

1. **Read-only, existing payload.** Dump `0x0400-0x0414` (21 bytes) and data
   registers `0x0060-0x0065`. Expect plausible per-pin bytes; record, do not
   write.
2. **Derive the byte** for pin 3 from the observed value, applying
   `& 0x1d | 0x02` and the per-pin table (recover from
   `_getPMUConfig`/`_setGPIODefaults` in the 8.1 kernelcache).
3. **One reviewed write** (needs an explicit go-ahead): config byte for pin 3
   only, verify immediate and delayed readback and data register bit 3; leave
   Bluetooth pin 2 for a separate step. Record before/after.
4. Only if it persists: wait 100 ms, then re-scan PCIe on the existing Stage
   5F/5G test payload.

## Caveats

- The iOS 8.1 per-pin table has not been decoded; the unstripped iOS 10 builds
  are different generations.
- A persisted config byte proves the register map, not that the chip's own
  reset/boot sequence completes; Apple waits 100 ms after REG_ON.
- Whether J81 has additional board interlocks around REG_ON remains unknown.
