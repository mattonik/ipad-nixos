# J81 GFX clock-ordering research

The static evidence now points to a missing clock-state operation rather than
an incomplete bridge table alone.

- J81 GFX is device ID `0x7c`, power-state index 100, with special-action
  flags `0x06` and bridge selectors 9/10.
- Apple invokes the bridge pair loop from the conditional clock-state action
  while raising GFX to state `0xf`; it does not simply replay the table after
  an already-active PMGR observation.
- The first-provider path performs provider clock/power operations, GPC
  setup, a bit-4 poll, and a 10-us delay before the early GPU match path.
- Our Linux test consumer only takes a genpd runtime-PM reference. It does
  not expose or invoke the Apple clock-state action, so successful raw bridge
  stores do not prove that the clock/fabric state is valid.

The hardware sequence matches this distinction: two clean boots accepted
small selector-9 segments, while a later same-boot attempt hung at the GPC
state read before its next bridge write. That is consistent with cumulative
fabric state, not evidence that the next table value is defective.

## Decision

Do not run a larger table segment or GPC initialization yet. The next useful
implementation task is a read-only Linux inventory of available clock/reset
providers and their GFX-related IDs, followed by static matching against the
Apple PMGR clock record. A hardware test becomes justified only after that
inventory identifies a concrete, non-MMIO prerequisite to verify.
