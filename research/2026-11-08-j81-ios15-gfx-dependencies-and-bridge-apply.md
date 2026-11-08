# J81 iOS 15: GFX power dependencies and where bridge settings are applied

Date: 2026-11-08. Offline static review of the iPadOS 15.8.8 J81
kernelcache (`com.apple.driver.ApplePMGR`, same slice as
`ios15-ApplePMGR.raw`) and of the earlier private Pongo ADT capture
(`gpu-observations/20261106T060741Z-pongo-adt.adt`, kept out of Git). No
device access. Follows
`2026-11-08-j81-ios15-clock-gate-to-pmgr-state.md`.

## Result

On iOS 15, GFX power-up has no parent power domain to bring up first, and the
bridge settings are applied inside the same state change, straight after the
PMGR state reaches 15. Test4 did these two things in the same order: a power
cycle to `0x3ff`, then the 66 bridge stores. This trace finds no Apple step
on this path that test4 skipped.

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
- parent IDs `+4..+7` are all 0, so the recursion adds nothing. iOS 15 does
  not power any other domain first because of GFX.
- PS block/index at `+0xa`/`+0xb` = `04`/`03`.
- 2 bridges at `+0x18`, selectors 9 and 10 at `+0x1c`/`+0x1d`.

This rules out the idea that the RGX read hangs because a parent domain was
left off.

## 2. Order inside the state change (`0x...bd81a8`)

On the power-up branch, per device:

| Address | Call | Meaning |
|---|---|---|
| `bd82a0` | `bd785c(pmgr, id, 0)` | probably looks up a related device object (inferred) |
| `bd82bc` | `bd9628(pmgr, rec, state)` | pre-state step |
| `bd82d4` | `bc6c20(pmgr, rec[+0xb], rec[+0xa], state)` | PMGR state helper. Returns the reached state |
| `bd82f0` | **`bd91a8(pmgr, rec, state)`**, only if the helper returned 15 | **bridge apply loop** |
| `bd830c`–`bd8350` | `bcc56c` over 8 slots | likely timing accounting: the results are stored to memory (bcc56c itself not traced) |
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

So GFX's selectors 9 and 10 are written right after state 15 is reached, in
the same transition. They are not written at init and not on a later wake.
This matches and pins down the 2026-11-05 summary in
`2026-11-04-j81-gpu-offline-trace.md`.

The iOS 15 ADT `bridge-settings-9` and `-10` are the same 264 bytes as the
8.1 tables test4 replayed (hash recorded in the 2026-11-04 note).

## What this leaves open

- The cause of the RGX core-ID read stall is still unknown. On this path,
  dependencies, state, bridge content and bridge order all match test4.
- Not traced: `bd9628`/`bd96e8` (pre/post steps), and the related-device
  `bd9798` branch. These are the only parts of `bd81a8`'s power-up branch
  not yet compared with test4.
- The legacy writer also builds `DEVRD`/`DEVWR`-like name keys for an object
  at `pmgr+0x2d18`/`+0x2d20`. That looks like statistics or reporting, not
  hardware. Not confirmed.

No new hardware test is justified by this note. The stop rules in
`2026-11-08-j81-next-mcc-experiment-decision.md` still apply.
