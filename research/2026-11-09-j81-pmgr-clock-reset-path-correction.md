# J81 platform clock and reset path: power-up correction

Date: 2026-11-09. Offline review of the extracted iPadOS 15.8.8 ApplePMGR
code, the captured J81 Apple device tree, Linux PMGR code, and previous test4
records. No device access or new hardware operations.

## Result

An earlier note assigned a non-increasing-state path to power-up and confused
two bridge writers. The instruction trace instead shows that an increase to
state 15 sets the PMGR state and then calls `bd90a8`; this invokes the
33-pair table writer `bd3dc8` for each GFX selector when bridge mode is 0.
The captured selector 9 and 10 tables match test4's planned 66 stores, but
we have not proven the Apple driver's runtime mode, the persistence of all
Linux writes, or equivalence of every provider action. This correction does
not identify a missing reset or establish a safe new GPU-core read.

## Instruction evidence

All addresses below are in the locally extracted 19H422-associated ApplePMGR
image. They describe that binary, not a verified running iPadOS instance.

- `bc6c20` returns `PMGR_word & 0xf`, the target nibble. It does not return
  the actual-state nibble at bits 7:4. At `bd8598`–`bd859c`, the dispatcher
  compares that target against the desired state: unsigned greater than or
  equal goes to `bd8234`, while a smaller target takes the increasing path.
- On the increasing path, `bd876c` calls `bc6da0` when record flag bit 2 is
  clear; `bd8794` calls the state setter `bc6ed8`; and, if the requested
  state is 15, `bd881c` calls `bd90a8`. The setter includes an actual-state
  poll. The intervening conditional timing/accounting calls are separate;
  the pair writer is not necessarily the immediately following operation.
- On the non-increasing path, `bd82d4` calls `bc6c20`; if the **old target**
  is 15, `bd82f0` calls `bd91a8` before `bd83a0` calls the state setter.
  This branch can include an equal-state request; it is not necessarily a
  power-off operation. It was incorrectly labeled power-up in the 2026-11-08
  dependency note.
- `bd90a8` walks the device's selectors and calls `bd3dc8`. In bridge mode
  `pmgr+0x2684 == 0`, `bd3dc8` reads the pointer at the selected entry's
  `+0x18` and pair count at `+0x10`, forwarding each offset/value pair through
  virtual `+0x998`. Mode 1 uses another operation. This mode is distinct from
  `pmgr+0x2680`, which selects the implementation of a separate optional
  per-bridge operation.
- Both `bd90a8` and `bd91a8` have optional operations gated by an entry's
  `+0x20` pointer (`bd4d94` and `bd4da8`, respectively). The captured J81
  PMGR node lacks the optional `bridge-counters` and
  `bridge-counter-configs` properties; the earlier initializer analysis
  predicts an absent pointer for that captured tree. This is not runtime
  verification. In particular, `bd4da8 → bd40bc` is not evidence that the
  33-pair table is replayed on power-up.

The captured GFX device record has zero dependency IDs, flags byte 0, and
selectors 9 and 10. The matching saved selector tables contain 33 pairs each;
the prior test4 transcript records their planned stores in order after the
PMGR state became `0x3ff`. The `+0x18` pointer's population and mode 0 are
conditions of the static comparison, and the table contents alone cannot
prove which path ran on an iOS boot.

## Additional power-state operation

For the captured GFX record, byte `+0xf` is zero and flag bit 2 is clear.
The increasing branch passes its low nibble, zero, to `bc6da0` before the
state setter. That helper reads the PMGR word and writes it back with bits
16:19 replaced by the supplied nibble and bits 8:9 cleared; other bits are
preserved. Linux's generic PMGR driver names bits 16:19 `PS_MIN` and bits
8:9 historical gating flags. The observed test4 word before power-on was
`0x300`, so its bits 16:19 were already zero; Linux's state transition also
clears the gating flags. This identifies an Apple provider operation, but
these checkpoints do not demonstrate a persistent difference in those
fields or prove the exact intermediate write sequence on either OS.

The test4 PMGR checkpoint `0x3ff` also has bit 31 clear. Linux defines that
bit as reset and bit 10 as device disable; bit 28 is auto-enable. A clear
reset bit in this one word is not proof that all GPU or fabric resets and
clocks are released. No independent J81 reset control has been identified.

## Next bounded work

Trace the initialization of the selector `+0x18` pair pointer and bridge
mode `+0x2684` from the captured ADT to determine precisely how strongly the
captured tables predict the Apple power-up writes. Separately investigate
whether an additional clock or reset operation is actually selected for J81.
Neither uncertainty justifies repeating the previously stalled GPU ID read.

Evidence: private `ios15pmgr-direction-insn.log`,
`ios15pmgr-ascending-insn.log`, `ios15pmgr-state-read.c`,
`ios15pmgr-extra.c`, and `ios15pmgr-bridge-use.c` under
`artifacts/live/private/gpu-offline/`; the captured ADT and test4 transcripts
are also private. The [test4 comparison](2026-11-08-j81-test4-vs-apple-pre-id-sequence.md)
and [GPU status](gpu-status.md) give the public evidence boundaries.

## Follow-up: bridge initialization

The initializer instructions at `bc0998`–`bc0a3c` skip this table-loading
loop when mode `+0x2684` equals 1. Otherwise, for each bridge and instance,
they look up a formatted property, require its byte length to be divisible
by eight, store the length divided by eight at entry `+0x10`, and store the
property-data pointer at `+0x18`. This confirms the writer reads the same
count and pointer fields populated by the initializer. The initializer
assigns `+0x2684` at `bc036c` only if a separate property lookup succeeds;
the property name and resulting runtime value have not been resolved in
this round. The captured tables do not alone prove mode 0 on a live iOS
boot. Evidence: `ios15pmgr-bridge-init-insn.log` in the private artifacts.
