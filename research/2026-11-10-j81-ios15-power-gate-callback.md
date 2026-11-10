# J81 iOS 15 power-gate callback: static resolution

Offline review of the locally extracted J81 iOS 15.8.8-associated kernelcache
SHA-256 `832cd980f257e6205b8ec131abea2a8470f3a3455f2c7039c890a091149c7389`.
This is static evidence, not proof of the runtime class. No device access.
The 60-byte callback, 352-byte action, and 832-byte read helper each have
exactly one byte-identical match in the separately extracted 19H394 kernel;
this does not prove that the live object dispatches to them.

## Candidate callback and data flow

The `ApplePMGRFunctionPowerGate` class name resolves to `0xfffffff005a5cb64`;
registration at `0xfffffff006bdd438` passes that name and instance size
`0x30`. The allocator at `0xfffffff006bdd53c` installs instance vtable
`0xfffffff006fd09e8`. Its `+0x80` entry is `0xfffffff006bdd5d4`. The previously
recovered `AppleT7001IO` power wrapper invokes `+0x80` on a cached object, but
the cached object's runtime class has not been independently established.

The candidate `bdd5d4` obtains the parent PMGR object's command gate at
`+0x160`, invokes gate method `+0xe8` with action `0xfffffff006bd8984`,
passes the gate identifier and the original output pointer, and returns zero.
It does not forward the incoming requested-state argument to this action.
The action returns immediately if the output pointer is null. Otherwise it
looks up the device record by the low 16 bits of the identifier, checks
record flag bit 4, and, when that flag is clear, calls `bd1dec` with the
record's `+0xb` and `+0xa` fields and selector `0`, then (if necessary) `4`.
It stores 1 if either helper reports true, otherwise 0. A separate conditional
logging/filter path follows; no direct register write is present in the
candidate action or `bd1dec`.

`bd1dec` calls the PMGR virtual read `+0x980` for the record's PS word, then
tests bit 8 for selector 0 or bit 9 for selector 4. Its other branches contain
diagnostic helper calls, so this is a bounded instruction-level finding, not
an exhaustive proof of every indirect or diagnostic side effect.

For context, the captured Pongo GFX record `0x7c` has flag byte zero, PS
block/index bytes `03/04`; see the [record decode](2026-11-08-j81-ios15-gfx-dependencies-and-bridge-apply.md).
The separate 19H394 capture observed PMGR `0x3ff` during the clock provider
call, which has both bits 8 and 9 set. **If** the same record, same word, and
value persisted to this power callback, this action would produce output 1.
That output has not been captured at this boundary; the poll and callback
are distinct moments. The flag is used by the G4G caller in post-identity
cleanup, not shown to be a prerequisite for its first identity read.

## Implication

This supports investigating callback provenance and the exact post-callback
state instead of assuming that the power request necessarily performs a
second GFX power-on write. It does not establish the bound object's actual
class on the 19H394 device, prove what happened in the instrumented boot,
or establish why Linux's GPU read stalls. The runtime object and indirect
call path remain unverified.

Private static evidence: `artifacts/live/private/gpu-offline/j81-powergate-20261110/`; the source kernel is under `artifacts/live/private/gpu-offline/`.
