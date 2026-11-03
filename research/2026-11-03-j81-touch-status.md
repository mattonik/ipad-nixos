# J81 touch: where it stands (2026-11-03)

Summary of the touch work from 2026-11-01 to 2026-11-03. Full run records:
`research/2026-11-01-orchardlinux-org-review.md` (runs C1, D1, C2, F1, P1, S1-S5, F-tx/F-rx, B1,
Z1-Z1j, Z2, Z3), `research/2026-11-02-j81-touch-runtime-gap.md` (Martin's parallel runs), and the
two work-copy diffs below. Touch is **parked** at this point.

## What works

| Step | Status | Where |
|---|---|---|
| SPI3 transfers of any length, full duplex | **Fixed.** iOS 15.8.8 `AppleSamsungSPI` order: TXCNT = RXCNT = length, status clear, CFG base without AUTO_TX and FIFO threshold 0, CTRL = `0xd` in one write, then CFG mode bit 5, then prime | `research/2026-11-02-s5l-bounded-pio-wip.diff` (`spi_apple` module work copy, switch `s5l_bounded_apple_order`) |
| Firmware upload (59,288 B, 12B410 or 19H422) | ACK `4b c1` | runs F-tx, F-rx |
| Calibration upload to `0x10009000` (and prox `0x10009600`) | ACK `4b c1` | B1, Martin's note |
| N1 register calibration (fll-mval 6068, `0x1000305c`=0x20, `0x10003058`=6, const-cal 3, clk32 1) | ACK `4a d1` each; controller `0x434d15c1` | B1 |
| Calibration request `1f 01`, execute `1d 53 0x10003400` | status `0x4969`; firmware runs | B1 |
| Runtime discovery (family 22, sensor 40x30, fw `0x381`/`0x382`, surface 14745x19657) | passes | Z1b+ |
| Linux input device `iPad5,3 Touchscreen` | registers | OrchardLinux `apple_z2` as a module, `research/2026-11-02-apple-z2-j81-wip.diff` |

## What doesn't

The running firmware **does not generate queued contact reports under the tested startup
sequences**: no ATN interrupt on touch, GPIO84 stays high, and forced reads under the driver
lock (with an N1 wake `ee` first; without it the idle firmware returns all zeros) report an
empty queue (`e1 00 00`) for 423 reads during a confirmed touch. It only sends `0x50` status
frames at boot. These observations do not directly measure whether electrode scanning occurs.

## Tested ideas and controls

- iPad 5 order (calibration first), no inter-word delay, 15.8.8 firmware, Apple order with prox
  calibration.
- N61 report-enable writes `9d`/`bf`/`af`; iOS 8.1 `rOPERATING_MODE` `e4 ab 01 00` (accepted).
- Display sync GPIO 55: PINMUX function 2/3 after boot, before boot, and at Apple's
  wake-to-dummy point; driven as a GPIO, where high breaks discovery and low has no effect.
  Function 1 permits firmware execution but returned zero runtime geometry (`0xa1` region
  parameters and `0xd9` surface) in the recorded discovery. The manual spidev diagnostic
  stopped after execution, before these reads. A test-only host-side substitution of the
  known surface descriptor let the driver run with function 1 selected; confirmed touch
  windows with both firmware versions still produced no IRQs, input events or queued contacts.
  A confirmed repeat with periodic polling disabled also produced no IRQs or input events.
  One other function-1 attempt failed earlier at device information (`-74`).
- The examined iOS kext and MultitouchSupport paths show no additional "start reporting"
  command after discovery (`DefaultReports` unset for J81, power state is a kext request).
- PMU `sensor_power` `Lump 0x202` is the Oscar coprocessor, not touch; LDO14 `0x14` is correct.

## How to rerun

Payload `m1n1-hoolock-wifi-touch-z2-kmod` (private assembly as usual), then on the iPad:
load the `spi_apple` work copy, `touch-diag hold --approve-pmu-write`, push the private
z2fw to `/lib/firmware/apple/j81-fwstart.z2fw`, `insmod apple_z2.ko` with optional
`poll_ms`, `poll_wake`, `sync_window`, `j81_init`; afterwards `rmmod`, `touch-diag release`.
Modules must match the payload's kernel (rebuild both after any kernel change), and builds go
through `tools/builder.sh build --wait --who <thread>`.

## Next

The [firmware and GPIO55 follow-up](2026-11-03-j81-touch-geometry-and-sync.md) found that
`0xa1`/`0xd9` read runtime RAM, while GPIO55 function 1 exposes a stable 30 Hz digital
signal in this Linux boot. Determine why that route leaves the runtime reports zero;
the correct iPadOS sync waveform and the firmware's initialization path remain unknown.
An iPadOS trace of GPIO55 (display sync) and ATN during a real touch would help, but needs a
logic analyzer (the no-new-hardware rule applies). Before upstreaming: turn the `spi_apple`
change into a kernel patch (it fixes S5L full duplex in general) and report the findings to
OrchardLinux.
