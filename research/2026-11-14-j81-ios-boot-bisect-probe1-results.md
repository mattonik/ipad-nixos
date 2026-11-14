# J81 iPadOS boot bisection, probe 1: results

Design: [probe 1 design](2026-11-14-j81-ios-boot-bisect-probe1-design.md).
The private logs are under `artifacts/live/private/ios-logarchive-j81-pmgr-bisect-0{1,2}/`.

## Run 1 (module `34059aad…`): panic, no data

The first register read caused an SError at physical `0x208020320`. That is GFX PS `+0x20320` on
PMGR ADT region 2 (`0x208000000`) instead of region 0. The ApplePMGR
region-table entry the probe used was not the `0x20e000000` mapping. The
panic happened before any write. The device rebooted into normal iPadOS (red flash).

## Run 2 (module `e2b39de0…`, own `ml_io_map` of all blocks), boot 20:13

```
J81_BOOT P0 S=00000300 F=00000000 P=80000000 V0=00000001 V1=00000000
J81_BOOT STOP C=00000007 V=00000011
```

- At ApplePMGR `start()` success, GFX PS is `0x300` and page 5 `+4` is `0`. Perf
  `0x1c200` is `0x80000000`, the same as Linux before the request. **The voltage
  manager is already enabled (`0x23000 = 1`)**, whereas PongoOS read `0xf01`. So
  ApplePMGR's own start enables it, which matches the static trace. The GFX
  code `0x2300c` is still `0`.
- GFX power-on and all 66 bridge stores passed (no stop codes 2-4).
- **The GPC poll hit its limit (code 7) with the state still `0x11`** (request
  pending, bit 4 busy). This is **inconclusive**. The 64-poll limit came from the
  user-space Linux tool, where each poll is a slow separate access. The
  in-kernel Linux measurement reached state 1 only at about 291 µs. 64 back-to-back
  MMIO reads take far less time. Page 5 and the core were not read.
- iPadOS then booted normally. AGX probed and its firmware started ("GPU firmware
  booted successfully"), even though the probe had left GFX on and the GPC
  request pending.

## Next

Rerun with a time-based GPC poll limit instead of a count, for example up to
5 ms measured with `CNTVCT_EL0` (24 MHz), and log the elapsed ticks at exit.
Nothing else needs to change.
