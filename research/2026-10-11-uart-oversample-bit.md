# Full AppleSamsungSerial register audit and the version-1 bit

Static audit of the iOS 8.1 `AppleSamsungSerial` image at
`0xffffff8002d75000`. Addresses below are the driver’s MMIO base plus an
offset; stores to the driver object itself are omitted.

## All MMIO stores found

| UART offset | operation in the driver | value/mask |
|---|---|---|
| `+0x00` ULCON | line-control routine (`0x2d76aa8`) computes word length, stop and parity; baud/config completion stores it (`0x2d76b88`) | whole-register store; 8-N-1 is `0x03` |
| `+0x04` UCON | line-control setup (`0x2d76988`) clears low mode bits and builds the mode word; later completion stores it (`0x2d76b94`) | whole-register stores; baseline contribution `old | 0x405` |
| `+0x04` UCON | flow-control/RTS helper (`0x2d769f8`) | RMW bit 4 (`0x10`) |
| `+0x04` UCON | helper (`0x2d76a58`) | RMW bit 17 (`0x20000`) |
| `+0x04` UCON | temporary break/disable path (`0x2d76700`, `0x2d76708`; also `0x2d7733c`, `0x2d77344`) | RMW clear mask `~0x881`, then restore original word |
| `+0x04` UCON | **version-1 path (`0x2d76a8c`)** | if `uart-version != 0`, RMW `UCON |= 0x00100000` (bit 20) |
| `+0x04` UCON | interrupt/mode helper (`0x2d77218`, `0x2d77240`) | clears low four bits, then writes `old-low-cleared | 0x5 | ((arg<<1)&2) | ((arg<<2)&8)` |
| `+0x08` UFCON | baud routine (`0x2d76c00`) | whole-register `0xc1` for version 0, `0x1c1` for version 1 |
| `+0x08` UFCON | FIFO/flow helpers (`0x2d769c4`, `0x2d769d8`) | RMW OR bit 1 (`0x02`) or bit 2 (`0x04`) |
| `+0x08` UFCON | DMA/port helper (`0x2d76714`, `0x2d767cc`) | whole-register store of the saved byte at `this+0x119` (the baud-selected `0xc1`/`0x1c1`, optionally ORed with `0x30`) |
| `+0x0c` UMCON | flow-control routine (`0x2d76e74`) | whole-register computed from old value; toggles bits 0 and 4 according to `function-rts`/`function-tx` |
| `+0x10` UTRSTAT | status/interrupt helper (`0x2d76748`) | whole-register `old & this->status-mask`; not a baud setting |
| `+0x20` UTXH | transmit helper (`0x2d76a44`) | whole-register data argument |
| `+0x28` UBRDIV-like | baud routine (`0x2d76da0`) | whole-register candidate divisor/selector word |
| `+0x34` Apple baud/slot register | baud routine (`0x2d76da8`) | whole-register slot-correction word |
| `+0x38` Apple baud/mode register | baud routine (`0x2d76dd0`) | whole-register slot word; version 0 adds the frame-dependent mode bits |

There are reads from `+0x14`, `+0x18`, `+0x24`, `+0x2c`, and other status
registers, but no stores to those offsets in this driver.

## The version-1-only bit

The unambiguous candidate is **UCON bit 20 (`0x00100000`)**:

```c
if (this->uart_version != 0) {
        ucon = readl(base + 0x04);
        writel(ucon | 0x00100000, base + 0x04);
}
```

The guard is explicit at `0x2d76a8c`; no requested baud comparison is
involved. None of the Linux Apple S5L definitions names this bit, and the
pinned driver never sets it. This is the strongest static explanation for the
divide-by-8 base mode. UFCON bit 8 is **not** sufficient: iOS writes `0x1c1`
for version 1, but the live experiment showed `0x131`/`0x1c1` do not change
the baud rate.

The other version-conditioned register write is the UFCON value itself. The
`+0x38` extra OR is version-0-only, not the version-1 enable.

## iOS versus Linux final state

For an 8-N-1 UART at 115,200, the meaningful baseline is:

| register | iOS version 1 (static sequence) | Linux Apple S5L capture/path |
|---|---:|---:|
| ULCON `+0x00` | `0x03` | `0x03` |
| UCON `+0x04` | baseline `old | 0x405`, then bit 20; expected distinctive bit `0x00100000` | captured `0x85` on UART3; Linux default is bits 7, 2, 0 and Apple timeout bits are added later |
| UFCON `+0x08` | `0x1c1` | `0x31` |
| UMCON `+0x0c` | function-dependent RTS/TX bits | `0x01` in the capture |
| UBRDIV `+0x28` | Apple candidate word (`0x19` at 115,200) | legacy `12` at 24 MHz |
| `+0x34`, `+0x38` | Apple slot words | `0x00`, `0x00` |

The UCON comparison is intentionally expressed as a mask rather than a
single claimed final constant: iOS's interrupt/flow-control helpers run after
the line setup and change low mode/enable bits. The invariant difference is
that iOS sets bit 20 for `uart-version=1`; Linux does not.

## Asahi/Hoolock comparison

The pinned `include/linux/serial_s3c.h` defines Apple S5L timeout/threshold
bits 9, 11, 12 and 13, but no bit-20 divide-by-8 control. The S5L termios path
writes only the legacy `UBRDIV` (and generic DIVSLOT where applicable), so the
divide-by-8 feature is currently omitted. No Asahi/Hoolock S5L code in the
pinned tree adds this bit.

## Implementation implication

The smallest software-only experiment is a guarded UCON RMW setting bit 20
only for `TYPE_APPLE_S5L`/`uart-version=1`, with the existing legacy divider
left unchanged. It should first be tested at 115,200 with a read-back and
drained timing check, then at 3,000,000. Do not infer that UFCON `0x1c1` or
the PMGR gate history bits select this mode; the full iOS audit points to
UCON bit 20 instead.
