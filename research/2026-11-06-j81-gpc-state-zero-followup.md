# J81 GPC state-zero follow-up

The hardware result now matches the earlier static clock-ordering hypothesis:
the Linux genpd path reaches PMGR state 15, but GPC state at
`0x201e01000` remains `0`. The existing Linux PMGR provider only performs the
generic power-state transition and optional auto-enable; it does not expose
Apple's separate GFX clock-state action or the GPC setup sequence recovered
from the iOS image.

The available read-only Linux payload has no mounted clock/reset debugfs
inventory, and the J81 DT exposes no GFX clock/reset consumer node. Therefore
there is no safe, concrete non-MMIO prerequisite to verify in the current
boot. The static evidence remains the actionable lead: Apple raises GFX
through its clock-state action (device `0x7c`, power-state index 100, bridge
selectors 9/10), then performs GPC setup and a bit-4 poll before the early GPU
match path.

## Decision

Do not replay bridge tables or run `gpu-gpc-init` from this state. The next
artifact should be an execution-disabled model of the Apple clock-state
transition and its ordering relative to the existing Linux genpd request.
Only after that model identifies a bounded read-only checkpoint should a
fresh hardware boot be used again.

