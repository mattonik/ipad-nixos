# J81 ANS1 storage: observation-only safety patch

Date: 2026-09-13

Target: iPad Air 2 Wi-Fi, J81/J81AP, A8X/T7001

Base: Hoolock's `ans1` Linux branch, pinned at `ed8528f482a526371e59711645794c91fafb2b42`
(the same commit already compile-verified in isolation, see
`research/j81-long-term-subsystems.md`'s "Internal NAND storage" section and
`kernel/hoolock-ans1-check.nix`).

## What this is for, in plain terms

The upstream `asp.c` driver (Nick Chan's ANS1/ASP storage-controller work)
is real and compiles cleanly, but its default behavior on real hardware is
to unlock writes to the iPad's actual internal storage -- the same NAND
that holds real iOS data -- as an unconditional side effect of a successful
probe, with no config-time way to turn that off. This document's job is to
turn that default off before this driver is ever run against real J81
hardware. It does **not** make storage usable, and nothing in it is tested
against the device -- this is a code-only, compile-verified change, the
same rigor already used for TOUCH-1's controller port.

## Exact changes, matching `research/j81-long-term-subsystems.md`'s
"patch ASP into observation-only mode" list item by item

Status column updated as each lands.

| # | Requirement | Status |
| --- | --- | --- |
| 1 | Remove the `WRITE_UNLOCK` command | pending |
| 2 | Reject all block writes/flushes that could mutate media | pending |
| 3 | Mark the user area and every auxiliary namespace read-only | pending |
| 4 | Replace reachable fatal assertions with errors that offline the disk | pending |
| 5 | Omit any format path from the test build | pending (checking whether one exists to omit) |
| 6 | Cross-build verify (isolated, same as the unmodified compile check) | pending |

## Why each one, specifically -- read directly from `drivers/block/asp.c`

- **`WRITE_UNLOCK`** (~line 816 in the pinned commit): `apple_asp_probe()`
  unconditionally issues `ASP_CMD_WRITE_UNLOCK` for every namespace as part
  of normal probe, immediately followed by the driver's own comment
  admitting "putting the wrong things in some of them could cause
  persistent controller crashes." This is the single most important line
  to remove -- without it, the controller itself should refuse writes at
  the firmware level regardless of what Linux's block layer does above it.
- **Block-layer write rejection**: defense in depth in case (1) alone
  doesn't hold for some reason not yet understood (this is unfamiliar,
  externally-authored code) -- the driver's own request-submission path
  should refuse to even construct a write command.
- **`set_disk_ro()` on every namespace**: currently only the LLB namespace
  gets this after probe; the user-data area and every auxiliary namespace
  (firmware, util-DM, DM, ctrl-bits, efface, NVRAM, syscfg, panic-log) do
  not. A third, independent layer.
- **`BUG()`/`BUG_ON()` -> graceful errors**: three `BUG()` calls sit in
  default-case switch branches on internal enum values (queue type,
  command classification) -- "should be unreachable" assertions, not
  something normal read-only operation would trip, but a real kernel panic
  if ever wrong. Downgrading these to a logged error plus offlining the
  disk means a driver bug degrades to "this disk stopped working," not
  "this kernel is now unusable."
- **No format path**: `apple_asp_probe()` already refuses unformatted media
  with an error (`!identify->util_formatted` check) rather than offering to
  format it, and the only format-related code is a `// TODO support auto
  reformat` comment describing something not yet implemented. Checking
  this is really as inert as it looks, not assuming it from the TODO text
  alone.

## What this explicitly does not include

- No hardware test of any kind. This is compiled, not booted.
- No change to whether ANS1 is wired into any actual boot payload --
  it remains its own isolated check (`kernel/hoolock-ans1-check.nix`,
  `packages.x86_64-linux.hoolock-ans1-check-kernel`), sharing nothing with
  `m1n1-hoolock-control`.
- No decision yet about when/whether to attempt the first real read-only
  hardware test. That is a separate, later, explicit decision -- not
  something this patch being ready implies permission for.
