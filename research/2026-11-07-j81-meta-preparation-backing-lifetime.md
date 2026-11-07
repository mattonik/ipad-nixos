# J81 META preparation-buffer backing lifetime

The J81 LDR copy destination is a retained mapped preparation allocation, not
the original packed firmware image. `FUN_ffffff800329e63c` allocates an aligned
descriptor, maps it with selector `0x70007`, stores the returned mapping object
at AGX object offset `+0x570`, and copies/verifies LDR payload bytes through the
host pointer returned by that mapping. The raw descriptor local is released
after mapping, but the mapping object remains in the AGX instance. Its
destructor, `FUN_ffffff800329d72c`, releases the `+0x570` mapping. The cached
success bit at `+0x5c8` prevents the prepare/copy routine from running again
until the instance is reinitialized.

This establishes a host-side backing lifetime: after preparation, the buffer
and its copied segment-2 bytes remain owned by the AGX instance through the
subsequent startup/alive path, and are released on instance teardown. It does
not establish which physical pages back the mapping, whether the GPU can
address them, or whether segment 2 is copied onward into a distinct hardware
boot window. `FUN_ffffff800329fbe8` performs CPU copy/compare only; the later
device-visible consumer of the preparation buffer is still unresolved.

The private G4G LDR image's only type-3 start record has two entries: thread
ID 1 at `0x8000b288` with field `0x20000000`, and thread ID 0 at `0x8000a288`
with field `0x10000000`. Neither entry is the META segment-2 address. Segment
2 is instead one 56-byte load at raw LDR address `0xc0000000`; Apple's parser
masks the global-alias bit, yielding normalized slot address `0x40000000`.
Therefore the LDR start record
does not supply a META PC; the J81 META entry is selected by a separate fixed
boot path or runtime handoff. This is the next boundary to resolve, since
there is no parsed META thread-start record to connect to the retained map.

The preparation routine also builds a separate command/config area beginning
at mapping offset `+0x200`: parsed LDR Config pairs, terminators, and translated
descriptor values are appended there. The adjacent GPC startup path writes
through its own mapped GPC register object and performs META responsiveness
polls; the observed GPC setup write of `0x40000000` is not a transfer from the
preparation buffer and is not evidence of slot-2 segment provisioning.

Actionable offline next step: resolve the later owner/consumer of the retained
`+0x570` mapping and its `+0x200` command area, then follow the META slave-port
PC-start transaction. That boundary can determine whether the buffer itself
is made META-visible or whether another boot-owned segment backing is used.

Evidence: `artifacts/live/private/gpu-offline/firmware-prepare.c`
(`FUN_...329e63c`), `firmware-layout.c` (`FUN_...329fbe8`),
`j81-near-start.c` (`FUN_...329d72c`), and `ios81-postldr.c` for the following
start/alive sequence; `g4g81-image.bin` and `tools/gpu_ldr_inspect.py` for the
LDR record structure. The record addresses and lengths were extracted offline;
no firmware payload bytes are reproduced. Static disassembly only; no hardware
or firmware execution.
