# J81 iOS 8.1 MCC configuration stride and startup order

Offline disassembly of the original 12B410 kernelcache. No hardware or live
MMIO was accessed.

## Finding

The earlier 5 x 44-byte grouping of J81 `mcc.config-data` is not the grouping
used by the iOS 8.1 MCC consumer. `AppleS5L8960XMemCacheController::start`
computes the configuration count as `config-data length / 20`; the selector
routine uses a 20-byte stride. The 220-byte property therefore has eleven
20-byte records for this code path. Selector index 4 reads the five words at
byte offsets 80–99:

```
[0x55, 0x11, 0x10, 0x00, 0x95f]
```

This supersedes the prior interpretation that mode 4 selects the final
44-byte tuple. It does not establish names or hardware meanings for these
five fields.

## Instruction evidence

The original 12B410 `AppleS5L8960X` image is embedded in
`artifacts/live/private/gpu-offline/kernelcache`. Prelink metadata gives load
address `0xffffff8002e52000`; with `__PRELINK_TEXT` file offset `0x52a000`
and VM base `0xffffff8002593000`, its carve begins at file offset
14,585,856. `otool -tvV` on that carved arm64 Mach-O shows:

* `start`, `0xffffff8002e53400`, gets `config-data`; a virtual call at
  `0x2e53568` supplies its length, which is multiplied by `0xcccccccd` and
  shifted right 36 (`0x2e53570`–`0x2e53584`), implementing division by 20.
  It stores that count at `self+0xb0` and the data pointer returned by the
  object's `+0xd0` method at `self+0xa8` (`0x2e53588`–`0x2e53598`).
* After PRAM setup, `start` reads `-disable_mcc`. If the flag is clear, it
  calls `FUN_ffffff8002e53924(self, 1)` (`0x2e53744`–`0x2e53754`). Here
  argument 1 is the enable/disable selector: zero takes the disable arm at
  `0x2e53b08`; nonzero takes the enable arm. The enable arm reads the first
  record at `self+0xa8`, uses its fields at offsets 0, 4, 8, 12 and 16, and
  calls `FUN_ffffff8002e54128` (`0x2e53950`–`0x2e53af8`). It then sets
  `self+0xb8` to 1. Timer creation/setup follows this call.
* The separately invoked numeric selector at
  `FUN_ffffff8002e54300` compares the requested index with the count at
  `self+0xb0` and accesses `self+0xa8 + index*0x14` (`0x2e54308`–
  `0x2e54368`). For index 4 this is byte offset 80, confirming the five-word
  record above.
* The helper `FUN_ffffff8002e54128` performs serialized writes through the
  mapped MCC base at `self+0x98`: `+0x10 |= 0x101`, RMW `+0x800` to replace
  bits [7:4] with `0x9`, `+0x83c |= 0x8000`, `+0x854 = 0x28b10000`,
  `+0x870` bit 31 set, `+0x884 = 0x2030`, `+0x888 = +0x88c = 0x80c`,
  zeroes at offsets `0x1000` through `0xf000` in 0x1000 steps, then stores
  `0x66`, `0x61`, and `0x60` at `+0xd000`, `+0xe000`, and `+0xf000`.
  These are observed instruction effects; register meanings are unknown.

The J81 PMGR tree separately sets `mcc-config-fb-caching=4` and binds
`function-mcc_ctrl` to `mcc`/`Mem$`. The startup call above applies the first
record through the enable path; the busy-edge release requests numeric
selector 4 through the PMGR callback path. Those are distinct operations.
This establishes their order within MCC service startup versus its later
runtime selector calls, but not whether MCC's service start completed before
G4G or AppleMobileADBE0 started. The available IOKit matches and saved logs
still provide no cross-service boot timeline or runtime callback evidence.

## Evidence limits

The parsed property is static DT data, and the disassembly establishes how
the original consumer strides it. Keep row field meanings and the runtime
state of `-disable_mcc` unknown. Do not use these offline register writes as
a Linux programming recipe.

Evidence: `artifacts/live/private/gpu-offline/kernelcache`,
`artifacts/live/private/gpu-offline/ios81-dt.json`, and the AppleS5L8960X
prelink load address in `artifacts/live/private/gpu-offline/kexts.json`.
The 220-byte values were decoded as little-endian u32s; instruction addresses
are from `otool -tvV` on the carved 12B410 image.
