# Bluetooth: remaining power/clock hypotheses

Date: 2026-10-11. Static analysis plus one bounded test on the already-running
iPad. No kernel build, DFU cycle, reboot, unknown-register write, or
backplane access was performed.

This pass combines the J81 ADT, the iOS 8.1 AppleBluetooth and D2207 paths,
the latest hardware record through `9609b9f`, and the public CYW4354 data
sheet as the closest documented member of the BCM4350 Bluetooth family. The
family comparison is supporting evidence, not proof that every timing value
is identical on Apple's BCM4350C2 module.

## Conclusions

| Question | Result | Confidence |
| --- | --- | --- |
| Missing software-controlled 32.768-kHz clock? | No such J81 control path exists, and this chip family can use an internal LPO. Do not add a guessed clock. | High for software; medium for the board wiring |
| Wrong reset delay? | Existing waits are already much longer than the documented family requirements. | High |
| Wrong power/wake ordering? | Closed by the live Apple-order test: UART first, then BT_REG_ON, then BT_WAKE was still silent, and controller RTS/host CTS never asserted. | High |
| D2207 `0x0063` bit 6 Bluetooth power-good? | No. It is PMU GPIO6, named `battery` by the J81 ADT and configured as an input. | High |
| Missing host-controlled rail or pin? | None is described or used by iOS. Shared input rails are strongly evidenced alive by working Wi-Fi. | High for software-visible controls |

## 1. 32.768-kHz LPO

The previous Apple-driver result stands: J81's Bluetooth node has no clock
resource, and `AppleBluetooth`, `AppleSamsungSerial`, and `AppleD2207PMU`
contain no Bluetooth LPO/clock-output enable path. The only J81 `KLCT`
32.768-kHz function belongs to the touch controller. The D2207 kext exports
RTC clock handling but no clock-output function consumed by Bluetooth.

The family data sheet makes the negative result less mysterious. CYW4354
uses either its internal, low-precision approximately-33-kHz LPO **or** an
external precision 32.768-kHz oscillator. External LPO is preferred for
accurate low-power timing, but is not required for the ROM to exist or for
basic HCI operation. The same document shows the LPO as a shared chip-level
clock and lists one `LPO_IN`, not a separately gated Bluetooth clock.

J81's working Wi-Fi supplies two additional constraints: the combo chip's
shared power and 37.4-MHz reference path are alive, and no Linux clock action
was needed to make them so. This cannot electrically prove a waveform on
`LPO_IN`, but it rules out a missing Bluetooth-driver clock enable. If the
board uses an external LPO, the evidence says it is fixed/always-on or set up
before the AppleBluetooth kext, not switched by that driver.

**Disposition:** close the software LPO branch. Only a scope measurement at
the module could answer whether the physical LPO is present; no safe register
write follows from the current evidence.

Sources: [CYW4354 frequency references, section 3.3](https://www.infineon.com/assets/row/public/documents/30/49/infineon-cyw4354-single-chip-5g-wi-fi-ieee-802.11ac-2x2-mac-baseband-radio-with-integrated-bluetooth-4.1-and-fm-receiver-datasheet-en.pdf?fileId=8ac78c8c7d0d8da4017d0ee1f570681c),
`research/2026-10-11-bluetooth-lpo-wifi-dependency.md`, and
`research/2026-10-11-uart-3mbaud-static-analysis.md`.

## 2. Power-up reset timing and ordering

There is no separate J81 reset line. iOS 8.1 `BTReset::start()` resolves the
optional reset/wake/power functions, immediately calls only
`function-power_enable(1)`, publishes `btwake`, and performs no delay or
second power step. On J81 `function-bt_reset` is absent. BT_WAKE is asserted
later only while a client has `btwake` open.

The family data sheet agrees with that model:

- `BT_REG_ON` is the Bluetooth reset/power control; the Bluetooth POR is held
  in reset while it is low and releases after it goes high.
- With `WL_REG_ON` high, taking `BT_REG_ON` low resets only the Bluetooth
  section; the shared internal regulators remain enabled.
- The at-least-10-ms discharge interval applies after **both** REG_ON signals
  have been low. The recorded tests left working Wi-Fi/WL_REG_ON high.
- The documented family POR maximum is 110 ms; 150 ms is the conservative
  post-supply wait. Existing tests waited one to four seconds.

Therefore the duration hypothesis is closed. The remaining detail was order.
The recorded tools drive BT_WAKE high first and then BT_REG_ON. Stock iOS
does the opposite: power at kext start, then BT_WAKE when userspace opens the
wake device. The public startup diagram also requires host UART I/Os to be
configured before BT_REG_ON and identifies the handshake: host RTS drives
the controller's active-low CTS; the controller then drives its active-low
RTS, seen as host CTS.

That order was tested on the running T2 payload after this static pass (see
section 5). It did not wake the transport: the documented UART `UMSTAT.CTS`
bit stayed clear and zero bytes came back. Timing and ordering are therefore
not the remaining fault.

## 3. What D2207 GPIO6 means

The observed `0x0063: 0x20 -> 0x60` is unambiguously bit 6 of the D2207 GPIO
data bank. The corresponding GPIO6 configuration byte is `0xba`. The named
D2207 implementation classifies configuration values at or above `0x60` as
input mode, so GPIO6 is an input.

Most importantly, the J81 PMU node labels its event inputs directly:

```text
event_name-gpio6 = battery
event_name-gpio7 = bluetooth
event_name-gpio8 = wlan
```

Thus bit 6 is a battery-related PMU input, not Bluetooth GPIO2 readback and
not evidence of a Bluetooth power-good signal. Its repeatable transition may
be a load/charger-side consequence of enabling the radio, but static analysis
does not identify the upstream circuit. That causal detail is irrelevant to
Bluetooth bring-up and should not motivate a write.

## 4. Unidentified rail or control pin

An exhaustive J81 ADT consumer check finds exactly two Bluetooth controls:

- D2207 GPIO2: `function-power_enable` / BT_REG_ON;
- AP GPIO164: `function-bt_wake` / BT_DEV_WAKE.

There is no Bluetooth `Lump` rail, supply property, reset, host-wake,
clock-output, or second PMU GPIO consumer. The public family power topology
uses shared VBAT/VDDIO and internal regulators controlled by the OR of
WL_REG_ON and BT_REG_ON. Since Wi-Fi now scans, associates, and transfers
traffic, those shared external rails and the main reference clock are not a
credible missing resource.

Two physical signals remain outside the ADT control list: `LPO_IN` and the
Bluetooth UART handshake/transport-detect pins. They are board wiring, not
evidence for another software-controlled rail. The family device selects
UART versus SPI from the BT_HOST_WAKE strap during power-up; J81 has no
host-wake consumer, so this is most likely a fixed pull on the board. A wrong
electrical strap or missing LPO would require measurement hardware to prove.

## 5. Apple-order live test

The one useful no-new-hardware test was run against the already-running iPad
with Wi-Fi still associated. The test used only controls already exercised
and approved in earlier rounds, plus read-only access to documented UART
status. Initial state was:

```text
D2207 0x0402 = 0x09                 BT_REG_ON low
AP GPIO164 = 0x00072602             BT_WAKE low
UART +04/+08/+28/+34/+38 = 85/31/0c/0/0
```

The exact active sequence was:

```sh
exec 3<>/dev/ttySAC1
stty -F /dev/ttySAC1 raw -echo crtscts clocal cs8 -parenb -cstopb 115200
./uartpoke set 0x80000 0 0          # proven true 3 Mbaud
./i2ctransfer -f -y 0 w3@0x3c 0x04 0x02 0x0b
sleep 0.2
./uartpeek 3                        # read-only UART registers
./pinpoke read 32; ./pinpoke read 33
sleep 0.8
./uartpeek 3; ./pinpoke read 32; ./pinpoke read 33
./pinpoke high 164
sleep 0.1
./uartpeek 3; ./pinpoke read 32; ./pinpoke read 33
printf '\001\003\014\000' >&3    # one standard HCI Reset
```

The result was identical at UART-ready/power-low, 200 ms after BT_REG_ON,
one second after BT_REG_ON, and 100 ms after BT_WAKE:

| observation | all four samples |
| --- | --- |
| UART3 `UMCON +0x0c` | `0x00000011` (RTS low requested and automatic flow control enabled) |
| UART3 `UMSTAT +0x1c` | `0x00000000` (`CTS` bit 0 clear) |
| AP GPIO32 register | `0x00072643`, unchanged |
| AP GPIO33 register | `0x00070221`, unchanged |
| bytes received after HCI Reset | `0` |

`UMSTAT.CTS` is the Samsung UART's documented host-CTS sample. Together with
unchanged GPIO33 and no received byte, it says the controller never asserted
its active-low RTS/transport-ready handshake. This is stronger than another
silent HCI probe: failure is below HCI framing and firmware download.

The test restored and read back D2207 `0x0402 = 0x09`, GPIO164
`0x00072602`, and the complete saved UART state
`+04/+08/+28/+34/+38 = 85/31/0c/0/0`. The iPad remained up and Wi-Fi was not
disturbed.

## Practical disposition

Software-only analysis has now closed the guessed LPO-enable, reset-delay,
power/wake-order, GPIO6, Wi-Fi-dependency, and hidden-rail branches. The
remaining fault boundary is physical startup: the BCM4350C2 Bluetooth core
does not raise its UART-ready handshake after the known BT_REG_ON sequence.
The unresolved candidates are board-level LPO presence, the fixed transport
strap, an undocumented module-local reset condition, or a hardware fault.

There is no evidence-backed additional PMU, PMGR, GPIO, or backplane write to
try. The next discriminating work needs physical observation of `LPO_IN`,
`BT_REG_ON`, and controller `UART_RTS_N` at the module during the sequence.
Without that hardware access, stop rather than sweep unknown registers.

Reference: [CYW4354 startup and power-up sequencing](https://www.infineon.com/assets/row/public/documents/30/49/infineon-cyw4354-single-chip-5g-wi-fi-ieee-802.11ac-2x2-mac-baseband-radio-with-integrated-bluetooth-4.1-and-fm-receiver-datasheet-en.pdf?fileId=8ac78c8c7d0d8da4017d0ee1f570681c).
