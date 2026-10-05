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

## Hardware result, 2026-10-04: in-kernel REG_ON assert makes the BCM4350 enumerate

Payload `m1n1-hoolock-pcie-reg-on-test` (patch `0050`, commit `15d8267`), booted
over the standard DFU path with the user's explicit go-ahead; read-only checks
over a recorded session (private manifest under ignored `artifacts/live/sessions/`).

- Boot log: `t7000-pcie reg-on-test: 0x0403 0x09 -> 0x0b (readback 0x0b, ret 0)` at
  0.13 s, ahead of PCIe probe (0.24 s onward). Register `0x0402` (Bluetooth
  `power_enable`) stayed `0x09`, untouched.
- **The root port now has an endpoint behind it:** `0000:01:00.0`, vendor/device
  **`14e4:43a3`** (Broadcom BCM4350 family), class `0x028000` (network/other),
  **revision `0x05`**, subsystem `106b:10fe`. BAR0 32 KB and BAR2 4 MB were assigned
  (`0x7c0400000` and `0x7c0000000`), IOMMU group assigned, ASPM L1 default.
- `lspci` shows `00:01.0 106b:1002` and `01:00.0 14e4:43a3`. Sysfs reports the
  link as 2.5 GT/s x1.
- The controller's own `link_up` poll still printed `link_up=0` (0x088 = `0x5`)
  at 0.856 s, yet generic enumeration found the device immediately afterwards.
  The earlier wait-for-link logic is therefore a poor success signal on this
  controller; the real test is config-space read. Do not treat "link_up=0" as
  failure without a config read.
- The kernel also logged `retraining failed` for the root port and an
  `iommu-map` warning for id `0x8`. Neither blocked enumeration; both need
  follow-up before relying on the link.

**Gates this closes:** radio power (REG_ON) and PCIe enumeration, including the
core revision read (`0x05`). **Not crossed:** no BCM4350 OTP/NVRAM access, no
firmware upload, no BAR writes were issued. The remaining gates in the standing
rules (private-capture evidence) still apply before any chip access beyond
config-space reads.

This confirms the corrected register map end to end: the earlier non-persistent
writes targeted the wrong registers, and `0x0403` is the real Wi-Fi power
enable. The PMU resets it on every reboot, so the assert must stay in-kernel
before the PCIe probe, exactly as implemented.

## PCIe warnings explained, 2026-10-04 (read-only, same REG_ON payload)

Recorded session (private), config space read through sysfs and decoded on the
host; nothing written. Both devices expose a PCIe capability:

| | Root port `106b:1002` | Endpoint `14e4:43a3` |
| --- | --- | --- |
| LnkCap max speed / width | **5.0 GT/s** x1 | **2.5 GT/s** x1 |
| LnkCap DLL-active reporting | yes | no |
| LnkSta current | 2.5 GT/s x1 | 2.5 GT/s x1 |
| LnkSta DLL link active (bit 13) | **1 (link is up)** | n/a |
| LnkSta training (bit 11) / bandwidth-mgmt seen (bit 14) | 0 / 1 | 0 / 0 |
| LnkCtl2 target speed | 2.5 GT/s | 2.5 GT/s |

- **`retraining failed` is benign.** The kernel's failed-link-retrain quirk saw a
  2.5 GT/s target on a port that advertises 5.0 GT/s, tried to lift it and retrain.
  The BCM4350 is a 2.5 GT/s device, so it cannot reach 5.0; the retrain fails and the
  kernel restores 2.5 GT/s. The link stays up and correct at Gen1 x1, which is also
  what the chip supports. Nothing to fix; it costs only a retrain attempt at boot.
- **`iommu-map ... id 0x8` is benign.** `0x8` is the root port's own requester ID
  (`00:01.0`); the controller's `iommu-map` covers the endpoint range from `0x100`,
  and the endpoint did join IOMMU group 0 with the DART initialized. The root port
  does no DMA.
- **`link_up=0` was the wrong signal.** The controller register bit the test
  stages polled (`+0x88` bit 6) is not the link indicator on this hardware: the
  root port's own **Data Link Layer Link Active** bit is set, and enumeration and
  config reads succeed. `+0x88` reads `0xc` with the chip unpowered and `0x5`
  with it powered, so its low bits do track the endpoint, but the exact encoding
  is undecoded (U). The production driver should wait on the root port's DLLLA,
  not `+0x88` bit 6.

No code change is needed for the warnings. The one recommended change is to the
link-wait logic in the future production driver (use DLLLA), not to the test
stages.

## Hardware result, 2026-10-05: board-gated `0052` payload enumerates the BCM4350

Payload `m1n1-hoolock-pcie-j81-reg-on` (patch `0052`, commit `d23fb35`), cold boot with
the user's go-ahead for its single PMU write; recorded session (private), read-only
checks over telnet. This payload has no I2C tools and no Bluetooth userland by design.

- Kernel log at 0.135 s, before PCIe probe: `J81 Wi-Fi REG_ON: 0x0403 0x09 -> 0x0b`
  (the board-declared path via `apple,reg-on-pmic`; no `failed to assert`, no deferral
  messages).
- Enumeration identical to the 0050 test: root port `106b:1002`, endpoint
  **`14e4:43a3`**, class `0x028000`, **revision `0x05`**, BAR 0 (32 KB) and BAR 2 (4 MB)
  assigned, IOMMU group 0, `lspci` lists both.
- Link, from config space: root port `LnkCap` 5.0 GT/s x1, `LnkSta` 2.5 GT/s x1,
  **DLLLA = 1**, training 0; endpoint `LnkCap` 2.5 GT/s x1. Same benign
  `retraining failed` and `iommu-map id 0x8` messages as before (explained earlier).
- Bluetooth `0x0402`: the patch contains no reference to it (statically verified), and
  the payload has no `btattach` or I2C tools. The register was **not read** this run
  (no tool in the image), so "untouched" rests on the code, not a readback.
- Nothing beyond config-space reads and the kernel's own `0x0403` write; no chip memory,
  firmware, OTP/NVRAM or Bluetooth action.

This validates the board-gated form as a drop-in for the test-stage assert. The inherited
Stage-5F link wait (`+0x88` bit 6) is unchanged technical debt; DLLLA is the real link
signal.

## Hardware result, 2026-10-05: DLLLA link wait (patch `0053`) works

Payload `m1n1-hoolock-pcie-j81-dllla` (patch `0053` on `0052`, commit `9d0c2c7`), cold
boot with the user's go-ahead (its only PMU write is the same board-gated `0x0403`
assert); recorded session (private), read-only checks over telnet.

- `J81 Wi-Fi REG_ON: 0x0403 0x09 -> 0x0b` at 0.1328 s (a first probe attempt at 0.127 s
  deferred until the PMIC regmap existed, then the second attempt asserted it, as designed).
- **New link wait:** `link-start` write at 0.351 s, then
  `t7000-pcie link-wait: link active=1 lnksta=0x3011 (controller +0x088=0x00000005
  +0x08c=0x00000000, undecoded)` at **0.3574 s**, i.e. the root port's DLL Link Active
  bit was set about **6 ms** after link start. No timeout warning.
- **Boot is about 0.5 s faster to enumeration:** the old fixed 500 ms `+0x88` poll always
  ran to its deadline (init complete at about 0.856 s); now `init complete` is at 0.3575 s
  and the root port enumerates at 0.3586 s.
- Same endpoint result as every earlier REG_ON run: `106b:1002` root port, `14e4:43a3`
  endpoint rev `0x05` (class `0x028000`), `lspci` lists both. Config space afterwards:
  root port `LnkSta = 0x7011` (2.5 GT/s x1, DLLLA = 1, training 0; the extra bit 14 vs.
  the earlier `0x3011` is the kernel's bandwidth-management flag set by its own retrain
  attempt), endpoint `LnkSta = 0x1011`, `LnkCap` 2.5 GT/s x1.
- The same benign `retraining failed` and `iommu-map id 0x8` lines appear. No PCIe error,
  AER or oops lines.
- The controller's `+0x088` still reads `0x5` with the link up, confirming it is a state
  word and not the link-up indicator (its encoding remains undecoded, **U**).
- Nothing was written beyond the kernel's own `0x0403` assert; no chip memory, firmware,
  OTP/NVRAM or Bluetooth action. `0x0402` not read (no I2C tools in this payload).

DLLLA is now the production link-success signal in this staging driver. The inherited
`0040`-`0045` test-stage writes and logs remain (not part of this task).
