# J81 iOS 15: GFX power dependencies and where bridge settings are applied

Date: 2026-11-08. Offline static review of the iPadOS 15.8.8 J81
kernelcache (`com.apple.driver.ApplePMGR`, same slice as
`ios15-ApplePMGR.raw`) and of the earlier private Pongo ADT capture
(`gpu-observations/20261106T060741Z-pongo-adt.adt`, kept out of Git). No
device access. Follows
`2026-11-08-j81-ios15-clock-gate-to-pmgr-state.md`.

> **Correction, 2026-11-09:** The `bd82xx` sequence described below is the
> non-increasing branch, not the power-up branch, and `bc6c20` returns the
> requested-state nibble rather than the actual-state nibble. The power-up
> bridge writer is `bd90a8 → bd3dc8`. See the
> [corrected instruction trace](2026-11-09-j81-pmgr-clock-reset-path-correction.md).
> Assertions below about `bd91a8` applying the 33-pair table after power-up
> and about a complete match with test4 are superseded.

## Result

On iOS 15, the captured GFX record has no parent IDs, so its dependency walk
adds no parent transition. On the traced state-15 transition, GFX bridge
settings are applied after the PMGR state reaches 15. Test4 did these in the
same order: a power cycle to `0x3ff`, then the 66 bridge stores. This comparison
covers the traced GFX dependency and state-change path; it does not exclude
other Apple bridge writers or setup paths outside that path.

## 1. Dependency list (`0x...bc8de4`)

`bc8de4` builds the dependency list for a device. It keeps per-device
reference counts at PMGR object `+0x18598` (requests for state 15) and
`+0x18bd4` (requests for state 4), and recurses over the parent IDs in the
device's 48-byte `devices` record (bytes `+4..+7`).

The GFX record in the captured ADT (record 80, ID `0x7c`):

```
00 00 00 7c 00 00 00 00 00 00 04 03 00 00 00 00
00 00 00 00 00 00 00 00 02 00 00 00 09 0a 00 00   name "GFX"
```

- flags byte 0 = 0, so the record-flag platform actions (`0xe`/`0xf` via
  `0x...bd523c`) do not run for GFX.
- parent IDs `+4..+7` are all 0, so this dependency recursion adds no parent
  transition for GFX.
- PS block/index at `+0xa`/`+0xb` = `04`/`03`.
- 2 bridges at `+0x18`, selectors 9 and 10 at `+0x1c`/`+0x1d`.

This rules out a missing parent transition in this GFX dependency walk as the
cause; it does not establish that no other subsystem or earlier boot stage
must power a related domain.

## 2. Order inside the state change (`0x...bd81a8`)

On the power-up branch, per device:

| Address | Call | Meaning |
|---|---|---|
| `bd82a0` | `bd785c(pmgr, id, 0)` | probably looks up a related device object (inferred) |
| `bd82bc` | `bd9628(pmgr, rec, state)` | pre-state step |
| `bd82d4` | `bc6c20(pmgr, rec[+0xb], rec[+0xa], state)` | PMGR state helper. Returns the reached state |
| `bd82f0` | **`bd91a8(pmgr, rec, state)`**, only if the helper returned 15 | **bridge apply loop** |
| `bd830c`–`bd8350` | `bcc56c` over 8 slots | timing-bookkeeping values are stored to memory; indirect callback target/effects and one pointer's mapping remain unresolved (see follow-up) |
| `bd837c` | `bd9798`, only if the related device has flag bit 4 and the state is 15 | not taken for GFX unless that device has the flag |
| `bd83a0` | `bc6ed8(...)` | the state helper already traced in the previous note |
| `bd83b4` | `bd96e8(...)` | post-state step |

## 3. Bridge apply loop (`0x...bd91a8`)

For `i` in `0 .. rec[+0x18]-1`:

- the selector is `rec[+0x1c+i]`. An alternate table is used only when the
  PMGR mode word `+0x2684 == 1`.
- the table entry is `[[pmgr+0x2668][selector] + state*64]`. If its `+0x20`
  pointer is non-null, it calls `bd4da8(pmgr, selector, state)`.
- `bd4da8` picks the writer from the table-format word `+0x2680`: below 2 it
  is the legacy offset/value writer `bd40bc`, otherwise `bd49d0`. The capture
  has no `bridge-settings-version` property. Both writers send each entry
  through the generic register-write virtual (`+0x988`/`+0x998`).

So GFX's selectors 9 and 10 are written right after state 15 is reached in
this state-change path. This does not rule out other writers or application
paths at init or wake.
This matches and pins down the 2026-11-05 summary in
`2026-11-04-j81-gpu-offline-trace.md`.

The iOS 15 ADT `bridge-settings-9` and `-10` are the same 264 bytes as the
8.1 tables test4 replayed (hash recorded in the 2026-11-04 note).

## 4. The remaining helpers (compared 2026-11-08)

- `bd9628` (pre-state) calls `bed9b0(0)` and keeps the result. Then for up
  to 8 objects in the table at `pmgr+0x49b8 + state*0x9800 + id*64` it
  calls `bed5cc`, and it does the same for the related device's `+0x100`
  object. `bd96e8` (post-state) mirrors this with `bed5d8` and ends by
  passing the saved value back to `bed9b0`. Disassembly of the extracted
  ApplePMGR text shows these addresses are 12-byte indirect-call thunks,
  not helper bodies. In the available `ios15-kernel`, these GOT slots are
  in `__PLK_DATA_CONST` (base VA `0xfffffff006cf4000`, file offset
  `0x21a0000`): `fcd630` contains `0xfffffff00728a318`, `fcd638` contains
  `0xfffffff00728a448`, and `fcd998` contains `0xfffffff00728e374`.
  `nm -m` names those targets `_lck_spin_lock` / `_lck_spin_unlock` and
  `_ml_set_interrupts_enabled`; the lock addresses are also aliases
  `_IOSimpleLockLock` / `_IOSimpleLockUnlock`. Thus the inspected cache
  resolves the sequence to interrupt disable/save, spin-lock acquire,
  spin-lock release, and interrupt-state restore. These are CPU/lock effects,
  not PMGR MMIO. This resolution is for the local cache, whose exact 19H422
  source association is verified; it is not independently confirmed against a
  device's running binary.
- `bd785c` (the related-device lookup) takes byte `+2` of the device record
  as an index into `pmgr+0x2740`. GFX byte `+2` is 0, so it returns NULL for
  GFX. That means the related-device lock in `bd9628`/`bd96e8` is skipped,
  and so is the `bd9798` branch at `bd837c`.
- For devices that do have it, `bd9798` is a real register sequence. It
  waits on bit `0x40000000` (vtable `+0x990`, timeout `0x2ee00`), reads
  (`+0x980`), replaces the low 4 bits and writes back (`+0x988`). This does
  not run for GFX.
- The `bd82a8` check of record flag bit 4 is also clear for GFX (flags 0).

On the inspected GFX power-up path, the identified hardware effects are the
PMGR state change to 15 and selector 9 and 10 bridge writes. Test4 did both,
in the same order. This is not a complete audit of every callee or every
possible bridge path. `bcc56c` is traced as timing bookkeeping, but its
indirect callback target and effects, and the `+0x28` pointer's mapping, remain
unresolved; those effects are not classified here.

## What this leaves open

- The cause of the RGX core-ID read stall is still unknown. On this path,
  dependency IDs, reached state, bridge content and bridge order match
  test4; unresolved callback effects in `bcc56c` and behavior outside this
  path remain open.
- The inspected `bd81a8` power-up operations have been compared with test4.
  Any missing precondition could be outside this path, for example in the
  conditional display/MCC busy callback, state that iBoot/iBEC leaves behind,
  or something AGX does after the ID read.
- The legacy writer also builds `DEVRD`/`DEVWR`-like name keys for an object
  at `pmgr+0x2d18`/`+0x2d20`. That looks like statistics or reporting, not
  hardware. Not confirmed.

No new hardware test is justified by this note. The stop rules in
`2026-11-08-j81-next-mcc-experiment-decision.md` still apply.

### Follow-up on unresolved calls

The `bcc56c` body is present in the extracted ApplePMGR image (196 bytes).
It reads object fields at `+0x28`, `+0x30`, `+0x54`, and `+0x57`; in one
branch it calls a PMGR vtable method at `pmgr+0x160` with a string pointer
and parameters derived from `+0x30`. Its returned value is used for
state-transition timing bookkeeping, while the indirect callback target and
effects remain unresolved. The eight call sites/results do not establish
hardware effects. In contrast, the three GOT-resolved lock/interrupt callees
described above are identified for this local cache and are CPU synchronization
effects, not PMGR MMIO.

The available file `artifacts/live/private/gpu-offline/kernelcache` is the
original 12B410 prelink. The iOS 15 cache used by the other notes is
`artifacts/live/private/gpu-offline/ios15-kernel`; its prelink metadata says
`DTPlatformBuild=19H402`. The matching manifest digest, raw cache, and decoded
Mach-O verify its source association with 19H422 (see [the provenance
check](2026-11-08-j81-ios15-kernelcache-provenance.md)). The GOT and symbol
mapping above is directly verified for that local cache, but does not prove
that this exact cache was the device's running binary. The three resolved
callees do not perform PMGR MMIO in this path; the interrupt-state and
spin-lock operations still affect CPU execution and synchronization.
