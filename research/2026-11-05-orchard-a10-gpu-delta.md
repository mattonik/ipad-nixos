# Orchard A10 GPU delta (2026-11-05)

The local Orchard checkout tracks `origin/main` at `d214e53` (the latest
local fetch). Its useful GPU history is:

* `b5e3769` adds the tested A10/T8010 Rogue driver, an explicit GPU node, the
  Fender and A7-IOP mailbox ranges, and an empty Linux OPP table;
* Orchard's m1n1 patch `0011-kboot-Fill-the-A7-A11-GPU-s-performance-states-from-.patch`
  fills that table from `/arm-io/sgx` `perf-states` when the Apple device tree
  supplies them;
* `6d248ce` removes the temporary A10 `always-on` workaround after suspend
  testing, but the driver still owns the firmware/power restore sequence.

## J81 comparison

The captured J81 Apple device tree has an `sgx` node, but it reports:

```
gpu-num-perf-states = 0
perf-state-count    = 0
perf-states         = 0
clock-gates         = [124]
power-gates         = [124]
```

That means Orchard's OPP importer correctly does nothing on this hardware.
The seven-entry OPP table observed in the Linux RAM boot is therefore not an
Apple GPU performance table; it is an unrelated generic table in the current
J81 DT. Copying the A10 importer or its driver without a J81 performance-state
source would request invented levels.

The A10 code also confirms the architectural split already found in the iOS
trace: A10 has an explicit `gfx-kf`/A7-IOP firmware mailbox and a Fender power
state register, while J81 has neither a GPU node nor that coprocessor in its
Linux/Apple descriptions. The reusable part is the sequencing discipline
(power domain, firmware/host layout, then RGX access), not the A10 firmware
path or its performance-state numbers.

## Consequence

The next J81 milestone is still a static/offline one: identify the A8X Rogue
core's host-visible initialization contract and any Apple-provided boot clock
state. Until that exists, the current PMGR-only consumer is the highest safe
hardware test; the Orchard A10 render driver is not a drop-in candidate.

## Open upstream work checked

The GitHub API was checked on 2026-11-05. `OrchardLinux/gpu` has only PR #2,
an A9 merge discussion; `OrchardLinux/orchard` has no GPU bring-up PR beyond
the already-landed A10 work (open PR #74 is A9 G5P render support); and
`OrchardLinux/linux` PR #1 only fixes reset handling when a power reference
fails. `OrchardLinux/mesa` has A9 G5P and A10 G9P work, but nothing targeting
A8X/A7X. None supplies the missing J81 firmware or clock-state contract.

