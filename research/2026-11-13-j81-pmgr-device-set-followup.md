# J81 GFX transition: device-set callback follow-up

Offline multi-agent review of existing 19H394 captures and 19H422 disassembly,
13 November 2026. No device access. The corresponding prelinked executable
ranges were previously found byte-identical across those two builds; runtime
object binding and data may still differ. This follows the early-DWI-hold
[GPC result](2026-11-13-j81-dwi-hold-gpc-result.md): DWI was on at sampled
boundaries, but page-5 bit 30 remained clear after GPC state 1.

## A specific pre-identity candidate

In the static `bd81a8` PMGR transition, instructions `bd865c`–`bd86e8`
check a nonzero record byte at `+0x19` and its enabled bit in PMGR `+0x714`;
when that branch is taken, the function calls the PMGR object's virtual
slot `+0x848` with `(pmgr, set_index, 1, 0, instance)`. This call is in the
provider transition before its return to G4G; it **could** run before GPC and
GPU identity. The GFX runtime membership, enable mask, instance and actual
branch execution are not established by the static code. The call operates on
transition entries, so another entry could matter even if GFX's own record
does not satisfy the guard.

The `bc7624` lookup returns a separately based runtime table at PMGR
`+0x4028` with a `0x30`-byte stride, indexed through the ID map at `+0x44f4`.
The initializer assigns that ID map using the raw ADT `devices` row index,
but the raw property is separately stored at `+0x8050`. A captured raw GFX
row has byte `+0x19 = 0`; we have not established that this byte is copied
unchanged into, or aliases, the runtime table. Therefore the raw zero does
**not** prove the call is skipped. A prior inference that it did was too
strong.

Reading the 19H394 Mach-O `__PLK_DATA_CONST` directly gives the static T7001
PMGR vtable entry at `0xfffffff006fe5e28 + 0x848 = 0xfffffff006fe6670`:
the stored pointer is `0xfffffff006bd2c30` (file offset `0x2492670`). This
is evidence for a **candidate static target**, not proof the live PMGR object
has that vptr. Independent instructions show `bd2c30` begins with a new
function prologue; Ghidra had merged it into a preceding function that
returns at `bd2c20`. The split analysis is consequently necessary.

In the split function, the apparent set ID is checked below 32 and used
with an instance to find a state record. Calls through slots `+0x850`,
`+0x980` and `+0x988` resolve a state index, read a PMGR state word and
request target nibble `0xf` or `0`; an additional wait/status path depends
on another argument, and a conditional `+0x6a8` dependency callback can run.
At the inspected enable call the enable argument is 1 and wait argument is 0,
so the target's explicit wait/status path is skipped; the instance comes from
a transition entry and is not resolved to a single value.
Argument roles, record meaning, physical register, and which dependency, if
any, is relevant to GFX are not yet proven. This is more than pure software
accounting, but it does **not** identify a missing Linux write, explain page-5
bit 30, or justify replaying the candidate sequence.

## Avoid repeating the tuner observation

A separate Nub per-set callback `be3b20` sends message 11 through an object
at Nub `+0x90`, vtable slot `+0x420`. The candidate tuner wrapper `cd8ab0`
accepts message 10, not 11; there is no demonstrated link between that
message-11 receiver and the tuner. In the inspected transition, the visible
`+0x100` event-source signal is conditional on the state being **not** 15;
do not treat it as a demonstrated state-15 signal. Earlier U/V tuner probes
had zero entry/exit observations and zero global positive controls. Their
negative result does not validate coverage of this newly identified edge.

Another unobserved G4G power-gate callback output may be useful for runtime
binding, but the inspected caller uses that output for cleanup after the
identity read. It is therefore a weak discriminator for the initial hang.

## Decision and next offline check

First resolve the static `bd2c30` state-record-to-register and `+0x6a8`
dispatch paths for the candidate T7001 class, and determine from captured
19H394 data whether the GFX record satisfies the call's guards. Separate
inferences from runtime evidence; account for all possible instance values
and aliases. Only if this produces a specific potentially missing prerequisite
and measurable result should we design a bounded iPadOS observation with a
positive control and before/after checkpoints. Do not assume a different
memory mapping caused the stall: the inspected Linux non-RAM and iOS initial
mapping paths both indicate Device-nGnRnE, although the exact live PTEs,
aliases and the test boot's classification are not established.

Private evidence includes `ios15pmgr-ascending-insn.log`,
`ios15pmgr-device-calls.c`, `ios15pmgr-nub-device-sets.c` and
`ios15pmgr-tuner-link.c` under `artifacts/live/private/gpu-offline/`, and a
split-function analysis on a temporary project copy. The 19H394 kernel SHA-256
is `c3507666766775dc854d5bcf6c375e6651ac8b2d1adb13d06331c60deb6a0008`.
Do not publish Apple binaries or private device logs.
