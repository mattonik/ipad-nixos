# J81 GPIO55 display-sync run: preserved reported transcript

Status: **reported output, not an original raw terminal capture**.

This preserves the exact run output committed in
[`research/j81-touch-diagnostic.md`](../j81-touch-diagnostic.md) at commit
`ebe603a9290e9d434b28384cd12da6dcc4ed4154`. It is deliberately kept separate
from `artifacts/live`: a workspace-wide search on 2026-10-05 found no raw
`commands.jsonl`, terminal spool, or other first-party capture for this command.
Do not describe this file as an original session transcript or use it to
establish payload identity.

Reported command:

```text
touch-diag run --execute --approve-pmu-write --spi-dev /dev/spidev0.0 \
  --display-sync-pinmux --approve-display-sync-pinmux
```

Reported output:

```text
step 4b: saved word 0x00072a82; requested field 0x220, wrote 0x00072aa2, readback 0x00072aa3
step 5 dummy: rx 00 x 16
step 6: IRQ edge (falling) after ~0 ms
wake      rx f0 01 f1 01 f1 01 f1 01 f1 01 f1 01 f1 01 f1 01
atn-short rx f0 01
atn-long  rx f0 01 f1 01 f1 01 f1 01
unwind: GPIO55 word restored 0x00072a82 (saved 0x00072a82)  ... LDO14 0x00, clock gated
```

The reported interpretation is limited to what this output supports:

- GPIO55 changed from peripheral-function 0 to function 1 and the saved word
  was restored exactly.
- The extra readback bit (`0x...aa3` rather than `0x...aa2`) is bit 0, an input
  level, not a failed pinmux write.
- The four existing handshake frames produced the already-known mode-2 idle
  response; no firmware, controller register command, or Bluetooth action is
  represented here.

## Recovery rule

If the original terminal output, session spool, or host-side command recorder
is recovered, store it unchanged under `artifacts/live/sessions/<session-id>/`
with its manifest and replace this file's status with a link to that raw
artifact. Do not overwrite this preserved reported version.

