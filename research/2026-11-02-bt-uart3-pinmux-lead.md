# Bluetooth: UART3 TX/RTS may be on the wrong pad function (2026-11-02)

Found while checking OrchardLinux for new Bluetooth work. Static evidence only;
nothing has run on the iPad yet.

## Evidence

| Pad | Our DT | Live register | Function |
| --- | --- | --- | --- |
| GPIO14 UART3 TX | `APPLE_PINMUX(14, 2)` | not captured | 2 (from DT) |
| GPIO15 UART3 RX | not muxed (iBoot state) | `0x00070221` | 1 |
| GPIO32 UART3 RTS | `APPLE_PINMUX(32, 2)` | `0x00072643` (2026-10-11 Apple-order test) | 2 |
| GPIO33 UART3 CTS | not muxed (iBoot state) | `0x00070221` | 1 |

- Function 2 for 14/32 came from the ADT OIPG flags byte (`0x102`), the same
  rule that gave GPIO34 function 2 for UART5. BAT-4 proved that rule wrong:
  GPIO34 at function 2 (`0x00072641`) gave total RX silence; function 1
  (`0x00072621`) made HDQ work at once (`research/j81-battery-hdq.md`).
- The plan doc's "function 2 remains valid because UART3 probed" is not
  evidence: the UART block probes regardless of pad routing, and the TX byte
  counter counts bytes leaving the FIFO, not the pad.
- The working console UART0 and UART4 pads read function 1.
- Orchard's J81 DT (`kernel/patches/devices/t7001/0005`, 2026-10-30) muxes
  14/15/32/33 to function 1. Their J81 run still got no HCI reset, but their
  `hci_bcm` starts at 115,200 baud; iOS uses 3 Mbaud from the first byte.
  Function 1 plus a true 3 Mbaud has never been tried.

If TX/RTS never reached the controller, every earlier probe (all rates,
frames, power orders, Wi-Fi up/down) was blind. The controller's own RTS
(our CTS, pad 33, already function 1) never asserting is also consistent with
it waiting for host RTS.

## Not relevant now

Hoolock `tests/bluetooth` (`83cfde7b`, 2026-07-01) uploads a "Taurus"
calibration blob (HCI `0xfd97`, 0xe6-byte chunks, DT `brcm,taurus-cal-blob`)
for the BCM4349B1 on T8015. It runs inside `bcm_setup()` after HCI already
works, and the J81 ADT Bluetooth node has no calibration property.
Orchard's only new Bluetooth code since 2026-11-01 is the Cascadia iPad mini 1
BCM4334 fix (Apple default address, LE advertising-type bits): useful once
our controller answers.

## Live A/B (prepared, not run)

`boot/bt_pinmux_ab.py`: checks 14/32 are on function 2, sets their PERIPH
field to 1 (`pinpoke func`, new), then the already-approved sequence (BT_WAKE
high, PMU `0x0402` 0x09 -> 0x0b), reads UART3 status, and sends one HCI Reset
at 3 Mbaud and 115,200, with and without RTS/CTS. A finally block restores
`0x0402`, GPIO164, UART3 registers and the original pad functions, and
verifies each.

Steps: build `nix build .#packages.x86_64-linux.pinpoke-static` (or
cross-compile `boot/pinpoke.c` statically), push to `/tmp/bt/pinpoke`, stop
`btattach`, run `boot/bt_pinmux_ab.py`.

Reading the result: any received byte (an HCI Command Complete starts
`04 0e`) confirms the mux bug; then fix `0001`/`0005` to function 1 for all
four pads and continue with firmware. Still zero bytes means the mux is not
the only fault; keep function 1 anyway (it matches Orchard and the other
UARTs) and return to the physical hypotheses in
`research/2026-10-11-bluetooth-remaining-hypotheses.md`.
