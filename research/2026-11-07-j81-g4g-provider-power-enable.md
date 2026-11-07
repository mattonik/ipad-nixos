# J81 G4G provider power-enable (`+0x568`)

Offline trace from the local 12B410 disassembly and saved test4 captures. No
device access or build was performed.

## What Apple calls

In `artifacts/live/private/gpu-offline/ios81-agx-disasm.txt`,
`FUN_ffffff80032935a0` calls the retained provider's vtable slot `+0x568`
with `(enable=1, out=&local, index=0)` at `0xffffff80032936cc..36e0`.
It follows provider `+0x560(1,0)` (clock enable) and precedes Fender/GPC
mapping and all three GPC writes. The preceding `+0x560` return is ignored;
the power call's output is inspected after the identity attempt.

The resolved provider implementation is
`AppleARMIODevice::enableDevicePower` at `0xffffff8002665788`; it selects
`power-gates[0]` and forwards the gate ID through the attached
`AppleT7001IO` power callback. J81 `sgx` has `power-gates = <0x7c>`, so the
ID passed onward is decimal 124. The T7000 PMGR callback installed at
`0xffffff80031e7bbc` initializes the output to zero, checks the
`WAS_PWRGATED` bitmap at controller offset `+0x7b0` for bit 124, reports 1
through the output only if that bit was set, clears that bit, and returns
success. Its body contains no MMIO access and requests no power-state
transition. This is historical-gating bookkeeping, not an enable register
write or a readback of current power.

The three identifiers must not be conflated: provider gate ID 124 indexes
the callback bitmap; the PMGR device record maps ID 124 to power-state index
100; the index-100 state register is `0x20320`. This `+0x568` callback does
not write that register. The separate clock-enable path can reach the PMGR
state-transition machinery and request state 15, subject to the clock
reference-count transition. See
`2026-11-07-j81-gpc-provider-object-binding.md` for the full slot chain and
clock path.

## Conditional unwind in the original G4G probe

The local output is initialized to zero before the provider call. After
identity returns, `32937b8..37c0` stores the identity result and only if it
is zero selects the provider pointer for cleanup. The routine always writes
GPC `+0x1000 = 0x10` after the identity call (and polls bit 4 clear only when
its poll flag is enabled). It then tests the power-history output at
`32937f0..37f4`. Only when nonzero does it call provider `+0x568(0,0,0)`
first and `+0x560(0,0)` second. Thus a previously recorded power-gated bit
controls a post-identity release pair; it is not a condition for the
initial enable call. The successful power callback consumes that history
bit, so a repeated probe can see a different output. The code does not
establish the bit's live test4 value.

## Difference from Linux test4

The test4 Linux phases recorded PMGR state `0x3ff`, GPC state 1 and control
`0x40000000`, then stalled at the first RGX identity read (`0x201000020`).
The Linux PMGR/genpd path had brought the domain to state 15, while separate
test4 stages manually applied the bridge-table prefix/full table and GPC
initialization. They did not invoke Apple's provider `+0x568` wrapper,
consume `WAS_PWRGATED[124]`, run Apple's `+0x560` reference-count transition,
or perform the post-identity state-zero and conditional provider-release
sequence. The test4 register observations therefore do not demonstrate
equivalent Apple provider bookkeeping; conversely, the static power callback
does not identify a missing power-enable MMIO write that would explain the
blocked read.

## Mapping limits

Static evidence resolves the G4G receiver's required `AppleARMIODevice`
provider contract, its inherited slot meaning, the J81 gate-array value,
the AppleT7001IO forwarding route, and the T7000 bitmap callback. It does
not resolve the concrete runtime class/IORegistry instance selected for the
`gpu,t7001` provider, the live bitmap value before or after test4, or whether
the test4 Linux domain transition had any equivalent prior-history state.
Nor does the callback reveal a physical rail/register corresponding to
`WAS_PWRGATED`; its recovered effect is only a software bitmap test and clear.

Sources: original disassembly in `ios81-agx-disasm.txt` at
`32935a0` and `2665788`; decompilation of the original
`31e7bbc` instructions in `t7000-power-gate.c`; and the slot, DT and
provider chain notes in `2026-11-07-j81-gpc-provider-object-binding.md`.
Test4 observations: `artifacts/live/gpu/core-revision-20261107-test4.log`,
`gpc-init-20261107-test4.log`, `clock-table-20261107-test4.log`, and
`postgpc-bridge-20261107-test4.log`.
