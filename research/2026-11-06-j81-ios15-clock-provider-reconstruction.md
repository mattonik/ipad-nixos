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

## Interpretation for the current hardware result

The successful PMGR transition (`0x300 -> 0x3ff`) followed by a persistent GPC
state of zero is consistent with the GPU domain being powered without the
Apple clock-provider action. The static evidence does **not** justify guessing
clock register offsets or issuing writes on the iPad: the J81 `device-clocks`
provider record table is still missing from the Linux DT/runtime path.

## Next offline step

Recover the J81 `device-clocks` record table from the decrypted iOS 8.1
ApplePMGR/AGX image (or a matching Apple device tree), then add a parser-only
fixture that emits the exact clock ids, flags, dependencies, and register
pairs. Only after that table is independently checked should a hardware test
be considered. That test would be an explicit MMIO-write approval point and is
therefore deferred here.

