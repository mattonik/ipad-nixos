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

## Run 3 (module `0a20ead8…`, time-based GPC poll), boot 20:57: **the core answers**

```
J81_BOOT P0 S=00000300 F=00000000 P=80000000 V0=00000001 V1=00000000
J81_BOOT GPC TICKS=00003929
J81_BOOT P1 F=40000000/40000000/40000000 P=80110100 V0=00000001 V1=00000164 G=30303000
J81_BOOT BEFORE CORE READ
J81_BOOT CORE=00070500
```

- GPC reached state 1 after `0x3929` ticks, about 610 µs at 24 MHz.
- **Page-5 bit 30 is set on all three reads**, perf goes to `0x80110100` and the GFX
  voltage code to `0x164`. That is exactly the iPadOS pattern.
- **The RGX core-ID read at `0x201000020` returned `0x00070500`**, the same value
  Apple's own driver logs (`I=00070500`). It is the first time the Linux recipe has
  produced a core response on J81.
- `G` (the GPC `+0` readback) is `0x30303000`, not the `0x40000000` that was
  written. Its meaning is not known, and it does not affect the result.

**Conclusion.** The same recipe hangs in PongoOS and on Linux, but works at the
end of `ApplePMGR::start()` on iPadOS. The missing step therefore lies in XNU boot
up to and including `ApplePMGR::start()`, before any CLPC, SOCTuner or AGX code.
The known difference inside that window is that ApplePMGR's ADT init
(`0x6bbf7a4`) runs: the voltage manager is already enabled at this point (`0x23000
= 1` vs PongoOS `0xf01`). Linux gets `0x23000 = 1` from m1n1, so the remaining
suspects are the other writes in that init and in XNU early platform setup.

Next bisection point: the **entry** of `ApplePMGR::start()`, or just before the
ADT-init call at `0x6bb9804`. If the recipe works there, the step is in XNU or
platform setup before PMGR. If it fails, the step is inside ApplePMGR start,
and the list of its PMGR writes becomes small enough to diff against Linux.
