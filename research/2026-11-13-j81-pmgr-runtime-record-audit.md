# J81 PMGR device-set follow-up: record mapping correction

Offline analysis on 2026-11-13 of the 19H394 kernel and previously saved iPadOS
IORegistry. No device access. This corrects the earlier version of
[the callback note](2026-11-13-j81-pmgr-device-set-followup.md), which
mistakenly treated the `devices` property's pointer as a separate object at
`+0x8050`.

## Which property the guard uses

The PMGR initializer `bbf7a4` decompiles with `uint *param_1`. Its property
key at `0xfffffff005a5563d` is the string `devices`; the initializer obtains
the property's data pointer and stores it at `param_1 + 0x100a`, meaning
**byte offset `0x4028`**, not `0x8050`. It indexes `0x30`-byte rows and
populates the ID-to-row table at byte `+0x44f4`. The `bc7624` lookup uses
that ID map and returns `*(pmgr+0x4028) + row_index*0x30`. Thus its returned
record is in the `devices` property data used by the initializer; the
`+0x19` byte used by the `bd81a8` guard is from that record.

The key at `0xfffffff005a54028` is the distinct `interrupt-config` property.
Its 0x1c-byte rows populate the separate per-instance runtime map at
`+0x19ac0` and entries at `+0x19ab0`. The earlier `+0x8050` conclusion came
from treating a 32-bit decompiler pointer as an eight-byte pointer; it must
not be used to infer a third table or an interrupt-config device record.

## What the saved iPadOS property says

The private `ios-registry-runtime-20261111/pmgr.plist` contains a 4,704-byte
`devices` property, or 98 records of 48 bytes. Record 80 is GFX, ID `0x7c`,
and its byte `+0x19` is `0`; the row matches the previously captured Pongo
ADT decode. The raw bytes and map are device-specific evidence, not a dump
of the PMGR heap at the time of transition. The saved IORegistry snapshot was
collected after boot; it does not independently prove the same provider
object, pointer contents or binding at the pre-identity call.

For an otherwise matching transition **entry for GFX itself**, the static
`bd81a8` guard `record[0x19] != 0` would skip the virtual `+0x848` call.
The traced GFX request calls `bc8de4` to recursively collect parent
transitions before `bd81a8`. The saved GFX record has zero parent IDs at
`+4..+7`, so under that captured configuration the dependency walk adds no
parent entry; if GFX requires a state change, its own qualifying entry still
has byte `+0x19 = 0`. This substantially weakens the candidate for the
ordinary GFX request. It remains static reasoning from a post-boot property
snapshot, not a trace of the actual pre-identity transition. Other independent
transitions, other calls to the slot, or a different runtime record remain
possible; the GPU-core stall is still unexplained.

## Candidate callback state mapping

For a qualifying entry, the static T7001 `+0x850` vtable target `bd2958`
uses a device-set ID and the instance-0 `interrupt-config` index map to
return a byte from its source row, or `0xff` if absent. The candidate `+0x848`
target `bd2c30` uses the resolved byte to derive an offset from runtime
PMGR fields at `+0x2344/+0x2348`, and calls virtual `+0x980/+0x988` for
state read/write. The actual mapping and dependency callback are still
runtime-dependent; the GFX row above does not supply a physical register
for this guarded call. The enable call's explicit wait argument is zero; the
wait/status update and enable-side dependency callback are inside that branch
and would also be skipped at this call site. The dependency test uses the
`interrupt-config` entry, not the `devices` row; do not transfer flags between
the two structures.

The saved GFX dependency record and caller analysis make a further iPadOS
hook solely for this guarded edge low priority. Look instead for a specific
independent transition or other pre-identity prerequisite that differs between
iPadOS and Linux. A physical register should not be inferred solely from the
virtual slot's selector or from an unverified runtime region mapping.

Evidence: private `ios15pmgr-init.c`, decompilation of `bc7624` and `bd2958`
in temporary analysis copies, the saved PMGR plist, and the 19H394 kernel
with SHA-256 `c3507666766775dc854d5bcf6c375e6651ac8b2d1adb13d06331c60deb6a0008`.
Do not publish device archives or Apple binaries.
