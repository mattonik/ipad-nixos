# J81 GFX clock-provider reconstruction (offline)

Date: 2026-11-06

## Result

The iPadOS 15 ApplePMGR decompilation confirms that the GPU power-domain
transition is not the whole bring-up path. Apple resolves a `device-clocks`
provider during PMGR device initialization, parses fixed 0x2c-byte clock
records, and stores the provider's per-clock table and dependency bitmaps.
The GFX state action then consumes that parsed record before the GPC start
sequence.

Evidence from `artifacts/live/private/gpu-offline/`:

- `FUN_ffffff80031e9af4` in `clock-table.c` looks up the `device-clocks`
  provider by name, obtains its record count through vtable `+0x98`, obtains
  the table through `+0xd0`, and divides the byte count by `0x2c`. Each record
  carries a clock id at byte 3, flags at byte 2/4, up to four dependency ids
  at bytes `0xc..0xf`, and a state/action byte at byte 5/6.
- `FUN_ffffff80031ea58c` in `gfx-clock-special.c` applies those record flags.
  Flag bit 3 toggles PMGR SoC offsets `0x20290` and `0x20298` with mask
  `0x40000`, then selects a power-state value and calls the provider-state
  helper. Flag bit 2 enters the provider busy-count transition.
- `FUN_ffffff80031eb7c0` performs the provider busy transition. On the first
  acquire/release it calls the provider vtable at `+0x78`, then invokes the
  clock action at the PMGR vtable `+0x740` with action ids `0x2700c001` and
  `0x2700c002`, and finally updates the provider's clock bitmap.
- `FUN_ffffff80031eb648` copies the selected clock record's offset/value pairs
  into the provider's mapped clock regions. This is the missing class of work
  from the current Linux path: the existing J81 driver only reaches the PMGR
  power-state register and never parses or applies the Apple clock provider.

The existing `tools/audit_gpu_bridge_plan.py` now provides an independent
parser/validator for the private iOS 8.1 tree and captured J81 ADT. The real
inputs pass with this exact GFX record:

```
record index: 79 / 82
raw:         0000007c06090a00000000006400000000000000000000000000000047465800000000000000000000000000
device id:   0x7c (GFX)
flags:       0x06
selectors:   9, 10
dependencies: none
power index: 100 (0x64)
bridge tables: 33 pairs each; SHA-256 b3818d986ab8a731bd769f56473970db58ae531f41b17b7dd316cfb2465140d4
```

## Interpretation for the current hardware result

The successful PMGR transition (`0x300 -> 0x3ff`) followed by a persistent GPC
state of zero is consistent with the GPU domain being powered without the
Apple clock-provider action. The J81 record metadata itself is already
recovered in the earlier clock-ordering and bridge-plan notes; what is missing
from the Linux DT/runtime path is the provider object and its state-machine
execution, not the 44-byte record description.

## Next offline step

The parser/validator is therefore complete, and the execution-disabled model
now accepts `--tree=...` to decode and cross-check the raw record directly.
The full offline suite passes (85 passed, 7 environment-dependent skips).

The Linux provider inventory is also now closed for the current tree: the
only Apple PMGR provider is `drivers/pmdomain/apple/pmgr-pwrstate.c`, which
exposes one generic power domain and one reset controller per node. It has no
`device-clocks` parser, clock-provider registration, bridge-selector handling,
or provider busy-count action. The J81 GFX node consequently has only the
PMGR `power-controller@20320` resource and the test marker; there is no Linux
clock consumer/provider edge to invoke Apple's record.

This narrows the implementation boundary: a future bring-up patch must add a
separate Apple clock-state/provider layer rather than extending the existing
one-register PMGR power-domain callback. Only after that mapping is
independently checked should a hardware test be considered. That test would be
an explicit MMIO-write approval point and is therefore deferred here.

