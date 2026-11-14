# J81 iPadOS boot bisection, probe 1: design (offline)

Status: **design only.** Nothing has been built or run. This is direction 2
of the [strategy reset](2026-11-14-j81-gpu-strategy-reset.md), after the
[offline PMGR trace](2026-11-14-j81-ios-voltage-manager-enable.md) found no
missing iPadOS boot step.

## Question

At the moment ApplePMGR `start()` succeeds on iPadOS 19H394, does the plain
Linux recipe (GFX PS on, 66 bridge stores, GPC wake) make page-5 bit 30 set?

- **Bit 30 sets:** the missing step happens before or inside ApplePMGR
  `start()`, so before any GPU or CLPC code runs. Next probe: earlier (start
  of `start()`, then early IOKit).
- **Bit 30 stays clear:** the missing step happens after PMGR start, between
  it and the GPU provider. Next probe: later (after the performance
  controller / SOCTuner start, then just before AGX start).

Bisection reads bit 30 only. The core-ID read is made **only if bit 30 is
set**, because every read with bit 30 clear has hung. That keeps a "clear"
result from hanging iPadOS.

## Hook site (19H394, checked offline)

- `ApplePMGR::start(IOService *)` runs from `0xfffffff006bb93xx` to `0xfffffff006bb9b0c`. It is
  identified by its panic strings (`"virtual bool ApplePMGR::start(IOService *)"`,
  out-of-line asserts at `0x6be4710`+). It calls the ADT init (vtable
  `+0x598`, `0x6bbf7a4`, which reads `ps-regs`, `perf-regs`,
  `perf-domains`, `clocks`, `power-domains`, `events`) at `0x6bb9804`, then
  `+0x5a0`, `+0x5c8`, `+0x5d0` and more.
- Proposed hook: the success return `0x6bb9aec  mov w0, #0x1`, where
  `x19 = this` (ApplePMGR). Everything ApplePMGR does in `start()` has
  happened, and nothing after it has run yet.
- The instruction signature and its uniqueness must be checked with
  `kpf-test` against `ios1585-19H394-kernel`, as for the earlier probes.

## Mappings available at that point

ApplePMGR keeps its region table at `this+0x2668`. Each region has a
`0x40`-byte record, with the VA at `+8` (`0x6bd3d38` writes, `0x6bd3d54` reads). The J81
`pmgr` `reg` list gives these regions, among others:

| Index | Physical | Use |
| --- | --- | --- |
| 0 | `0x20e000000` (0x40000) | GFX PS `+0x20320`, page 5 `+0x5004`, perf `+0x1c200`, VM `+0x2300c` |
| 11 | `0x201f00000` | bridge block 0 |
| 12 | `0x201f80000` | bridge block 1 |

**Gap:** the GPC block `0x201e00000` and the core `0x201000000` belong to
the `sgx` node (`reg` entries 0 and 1). ApplePMGR does not map them. The probe
needs its own device mapping of one page at `0x201e00000` (and one at
`0x201000000` for the gated core read). The 19H394 mapping routine
(`ml_io_map`, or an `IOMemoryDescriptor` path) has not been located yet. That
is the first offline task before any build.

## Probe actions, in order

1. Log `P0`: GFX PS, page 5, perf `0x1c200`, VM `0x23000`/`0x2300c`.
2. If GFX PS is not `0x300`, log and stop.
3. GFX power-on, using the same PS sequence as the PongoOS test. Stop unless PS reads `0x3ff`.
4. 66 bridge stores from the private plan, through regions 11 and 12.
5. GPC: read state (must be `0`), then the three writes, then poll, 64 polls
   at most.
6. Log `P1`: page 5 three times, perf, VM, GPC control.
7. Only if page 5 bit 30 is set: log "before core read", then read
   `0x201000020`.
8. Return to `start()` with `w0 = 1`, as the original instruction does.

The probe leaves GFX on. Apple's own GPU path later finds the domain already
on. That may disturb the later GPU start, which is acceptable for a one-off
boot, but the log must be retrieved before conclusions are drawn from the
rest of the boot.

## Before a boot (GO/NO-GO)

- [ ] Mapping routine located and its call shape verified in 19H394.
- [ ] Hook signature unique, and `kpf-test` accepts the exact kernel and
      rejects altered ones.
- [ ] Host simulation: every stop path, the bit-30 gate, `w0 = 1`
      on every exit, and register preservation.
- [ ] Bridge plan hash `1c7b3839…` checked by the build; plan kept private.
- [ ] Martin is told that the iPadOS boot is temporary, may hang or reboot,
      and recovery is DFU.
