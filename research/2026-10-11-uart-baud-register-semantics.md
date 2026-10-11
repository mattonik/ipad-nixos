# Apple UART baud-register semantics (iOS 8.1, UART3)

This is a static reconstruction of `AppleSamsungSerial` at
`0xffffff8002d76bb8`. It is sufficient to avoid treating the Apple block as
the older Samsung interrupt layout, but it is not a substitute for a named
Apple register specification.

## Candidate search

The following is C-like pseudocode with the ARM integer operations made
explicit. `frame` is the value built at `this+0x110`; for the usual 8-N-1
configuration it is 10. `nclk` is `this+0x120`, and `version` is
`this+0x11c`.

```c
scaled = ((uint64_t)nclk << 17) / requested_baud;
initial = scaled / (2 * frame);
max_iter = version ? 3 : 13;
min_factor = version ? 4 : 8;

for (i = 0; i < max_iter; i++) {
        factor = version ? (16 - i) : (1u << (4 - i));
        q = scaled / factor;
        whole = q >> 16;
        unit = factor << 16;
        low_product = whole * unit;
        low_error = scaled - low_product;
        high_product = low_product + unit;
        high_error = high_product - scaled;

        /* `hi` is the unsigned ARM condition from cmp low_error,high_error. */
        use_high = low_error > high_error;
        chosen_product = use_high ? high_product : low_product;
        error = use_high ? high_error : low_error;
        chosen = chosen_product / factor;

        /* The high half is the candidate divisor; the low half is rounded. */
        reg28 = (i << 16) | ((whole + use_high + 0xffff) & 0xffff);

        correction = fractional_slot_search(scaled, chosen, initial, frame);
        tolerance = (chosen >> (factor > min_factor)) + initial;
        if (error <= tolerance || factor == 4)
                break;
}

write32(UART + 0x28, reg28);
write32(UART + 0x34, correction);
if (!version)
        correction |= 3u << ((frame - 2) & ~1u);
write32(UART + 0x38, correction);
```

`fractional_slot_search` is the literal bounded Bresenham/slot loop in the
binary: it accumulates `scaled` and `chosen`, compares each difference with
`chosen/2`, and selects a bit at positions 0, 2, 4, ... from masks `1` and
`3`. It is not a floating-point fraction. Version 1 tries factors 16, 15,
14 in that order. Version 0 tries `1 << (4-i)` for up to 13 iterations (the
later shifts use ARM's 32-bit shift semantics); this is direct disassembly,
not an interpretation of a datasheet.

## Registers and fields

| offset | direct static evidence | safe field description |
|---|---|---|
| `+0x08` | whole-register store of `0xc1` (version 0) or `0x1c1` (version 1) before the search | FIFO/control setup; not a baud divisor; no bits are preserved |
| `+0x28` | whole-register store of `reg28` | bits 31:16 carry candidate index; bits 15:0 carry the adjusted fixed-point divisor. On version 1 this is Apple’s packed/doubled divisor encoding, not Linux's legacy UBRDIV integer. |
| `+0x34` | whole-register store of the slot-search result | 32-bit fractional/slot correction pattern; no read-modify-write and no preserved fields |
| `+0x38` | whole-register store of the same value on version 1; version 0 additionally ORs a frame-dependent `3 << ((frame-2)&~1)` | Apple baud/mode register, not a preserved interrupt register; exact named subfields are not recoverable from this stripped binary |
| `+0x04` | not touched by this baud routine | UCON is programmed by separate line-control routines using read-modify-write; do not change it as part of the baud calculation |

The stores are ordered `+0x08`, then `+0x28`, `+0x34`, then `+0x38`.
There is no FIFO flush, disable, or read-back in this routine itself.

## Worked version-1 values (`nclk = 24,000,000`, `frame = 10`)

These are the exact 32-bit results of the above integer reconstruction
(including the bounded slot loop). The `0x38` value equals `0x34` for version
1. A value in `0x28` with bit 16 set is the candidate-index packing, not a
large UBRDIV.

| requested | factor selected | `+0x28` | `+0x34` | `+0x38` |
|---:|---:|---:|---:|---:|
| 115,200 | 16 | `0x00000019` | `0x55555555` | `0x55555555` |
| 921,600 | 16 | `0x00000002` | `0x00000000` | `0x00000000` |
| 1,500,000 | 16 | `0x00000001` | `0x55555555` | `0x55555555` |
| 2,000,000 | 14 (fallback) | `0x00020000` | `0x00000000` | `0x00000000` |
| 3,000,000 | 16 | `0x00000000` | `0x55555555` | `0x55555555` |

The Linux S5L path writes legacy `UBRDIV = 12` for 115,200. That remains
valid because the power-on Apple mode is the factor-16/no-correction mode and
the legacy value is interpreted by that mode. Apple’s version-1 routine writes
the equivalent packed value `0x19`; treating `0x19` as a legacy UBRDIV would
be wrong.

## Collision check

Linux's generic Samsung header calls `0x30/0x34/0x38` UINTP/UINTSP/UINTM,
but the pinned `TYPE_APPLE_S5L` path uses UTRSTAT/UCON interrupt bits and does
not rely on those generic interrupt registers. iOS directly writes `0x34` and
`0x38` in its baud routine. Therefore they are baud/mode registers on this
Apple block, not the older generic interrupt layout.

## Runtime changes and clock

The function at `0xffffff8002d7787c` extracts a requested speed and tail-branches
to the baud routine. This is the serial termios/set-speed path, so iOS reruns
the calculation after open; a later HCI speed change is expected to program
the divider again. The baud routine itself performs no disable/flush sequence;
any quiescing is supplied by the surrounding serial state machine. The only
ordering proven here is the four MMIO stores listed above.

`nclk = 24 MHz` is the strongest value for UART3: the ADT clock reference and
the Linux measurement both identify a 24-MHz input. The stripped iOS kext
loads the `nclk` property but does not expose the property value, so 24 MHz is
an inference, not a directly recovered iOS literal.

## What remains hardware-verifiable

A read-only register dump while changing speed would settle the unresolved
field names. Capture UART3 offsets `0x28`, `0x34`, `0x38` before and after
115,200 -> 3,000,000; do not write them. The predicted version-1 values are
the table above. No build or hardware access was used for this note.
