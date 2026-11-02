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

## Live A/B result, 2026-11-02

Run 06:29 UTC, on the iPad as it was running (no reboot, no DFU; the touch
thread's payload was left in place, no SPI/touch pin touched). Approved by the
project owner for this one run.

Running payload: `wifi-touch-kmod-K1` (run id `ea04e00d82b46e61351a9610ebdb6ab3`, see
`docs/kmod-reload.md`), up 55 min.

    uname -a: Linux (none) 7.3.0-rc1 #1-NixOS SMP PREEMPT Tue Jan  1 00:00:00 UTC 1980 aarch64 Linux
    /proc/cmdline: console=tty0 loglevel=8 ignore_loglevel rdinit=/init PMOS_NO_OUTPUT_REDIRECT pd_ignore_unused clk_ignore_unused pcie_aspm=off pcie_apple_t7000.device_wake=1 fbcon=font:TER16x32 spidev.bufsiz=65536 j81.run_id=ea04e00d82b46e61351a9610ebdb6ab3

Tools: `/tmp/bt/{pinpoke,uartpoke,i2ctransfer}` were absent (RAM, earlier
boot) and were pushed fresh over the USB link from a short-lived HTTP server,
built at commit 421e658 (`pinpoke-static`, `uartpoke-static`,
`bt-userland-static`; all static aarch64; pinpoke has the `func` command).
sha256: pinpoke `f2667f1d…1fb1262`, uartpoke `490d17ea…1cc012`, i2ctransfer
`4d030c81…f3326ac70`. `btattach` was not running.

`boot/bt_pinmux_ab.py` full output (exit 0):

```
baseline pads: 14=0x00072641(f2) 15=0x00070221(f1) 32=0x00072643(f2) 33=0x00070221(f1); pin164 0x00072602; 0x0402 0x09; 0x0010 0x00; uart: +0x04=0x00000085 +0x08=0x00000011 +0x28=0x0000000c +0x34=0x00000000 +0x38=0x00000000
pin 14 reg now 0x00072621
pin 32 reg now 0x00072622
pads after func 1: 14=0x00072621(f1) 15=0x00070221(f1) 32=0x00072622(f1) 33=0x00070221(f1)
pin 164 reg now 0x00072603
0x0402 readback: 0x0b
3,000,000 (i=8 div 0)      no-fc : rx_bytes=0
3,000,000 (i=8 div 0)      rtscts: rx_bytes=0
115,200 (legacy div 12)    no-fc : rx_bytes=11  04 10 01 00 04 0e 04 01 03 0c 00
115,200 (legacy div 12)    rtscts: rx_bytes=7  04 0e 04 01 03 0c 00
--- RESTORE
final pads: 14=0x00072641(f2) 15=0x00070221(f1) 32=0x00072643(f2) 33=0x00070221(f1); 0x0402 0x09 (want 0x09); 0x0010 0x00; uart: +0x04=0x00000085 +0x08=0x00000011 +0x28=0x0000000c +0x34=0x00000000 +0x38=0x00000000
restored OK
```

**Reading: the mux bug is confirmed.** With UART3 TX/RTS (AP GPIO 14, 32)
moved from function 2 to function 1, the controller answered for the first
time ever: at 115,200 baud the standard HCI Reset got a Command Complete,
`04 0e 04 01 03 0c 00` (event 0x0e, 1 credit, opcode 0x0c03 = HCI_Reset,
status 0x00 success), both without and with RTS/CTS. Without flow control it
was preceded by `04 10 01 00`, a Hardware Error event (code 0x00), most
likely the controller reporting the line noise or the half-sent bytes from
the 3 Mbaud attempt just before. Nothing came back at 3 Mbaud: the controller
boots at its ROM default 115,200, so this is expected (3 Mbaud needs the
vendor baud-change command first). Every earlier silence at every rate is
explained by TX/RTS never having been routed to UART3. The script restored
everything and verified it (pads back to f2, 0x0402 0x09, BT_WAKE and UART3
registers at baseline). Side note: pin 32's readback in function 1 was
`0x...22` vs `0x...43` before, i.e. bit 0 also read 0; it came back to
`0x00072643` on restore, so bit 0 is a level/readback bit, not something
the `func` write changed. Next: DT `0001`/`0005` to function 1 for all four
UART3 pads, then hci_uart/btattach at 115,200 and the Broadcom firmware load.

## 0101 off-hardware checks, 2026-11-02

- `j81-dtbs-check` with 0101: pass, 9 warnings, 0 new, 0 fixed.
- `m1n1-hoolock-wifi-touch-kmod` with 0101: built
  (`/nix/store/lc8j0n4gnsf222vdi6z36qck3pd2ym78-ipad-air2-m1n1-hoolock-wifi-touch-kmod`,
  GC root `artifacts/live/gcroot-wifi-touch-kmod-uart3f1`). Its
  `t7001-j81.dtb` has `uart3-pins { pinmux = <0x1000e 0x1000f 0x10020 0x10021>; }`.
  Not booted.

## Live bring-up on W1, 2026-11-02: prepared, not yet run

The project owner approved a full live bring-up on the running W1 NixOS
payload (no reboot). What happened so far:

- Capability check (read-only, over ssh): kernel 7.3.0-rc1, run id
  `27070e503241158c1c4ff4fe17176305`; `/dev/mem`, `/dev/i2c-0` present;
  `ttySAC1` = UART3 `0x20a0cc000`; `bluetooth`, `hci_uart` and `btbcm` are
  built in and the serdev driver `hci_uart_bcm` is registered (UART3 has no
  serdev child, so the line-discipline path via `btattach -P bcm` is used).
  No `/proc/config.gz`, no BlueZ userland, no python on the iPad.
- Pushed to `/tmp/bt`: pinpoke (421e658, with `func`), uartpoke,
  i2ctransfer, btattach (static), hciscan (new). Baseline unchanged from
  the morning A/B: 14=0x00072641 15=0x00070221 32=0x00072643
  33=0x00070221 164=0x00072602, 0x0402 0x09, 0x0010 0x00, UART3 +0x28 0xc.
- Patchram: `BCM.apple,j81.hcd` (Orchard `devices/j81/firmware.json`,
  `bluetool-hcd@1` from iPadOS 15.8.8 `usr/sbin/BlueTool`), extracted from
  the local IPSW on the NAS through Orchard's reader with a local-file
  shim; 72,360 bytes, sha256 matches Orchard's pin. Kept outside Git.
- The first register write (pinmux/BT_WAKE/PMU) was refused by Claude's
  auto-mode tool classifier, so nothing was written. Same situation as
  2026-10-10: the owner runs the self-restoring script instead.

`boot/bt_live_bringup.py --fw <private hcd>` does the whole sequence and
restores it: GPIO 14/32 -> function 1, BT_WAKE high, PMU `0x0402` 0x0b;
`btattach -P bcm -S 115200` once to learn the patchram name the kernel
asks for; pushes the hcd under that name to `/tmp/fw` (RAM) and points
`firmware_class.path` there; re-attaches; runs `hciscan 0 20` (counts
only); then restores every register, the firmware path, deletes
`/tmp/fw`, and verifies. `boot/hciscan.c` (flake `hciscan-static`) brings
hciN up and prints only the classic-inquiry and LE-advertiser counts.
