# J81 iOS 15 performance buffer and GPC state calls

Offline analysis, 2026-11-09. This follows
[iOS 15 GFX performance handoff](2026-11-09-j81-ios15-gfx-perf-state-handoff.md)
in the local 19H422-associated kernelcache. It is static analysis, not a
capture of a running iPad.

## Allocation and the host-side reader

At `0xfffffff006688620`, the setup routine supplies an allocation descriptor
whose output fields are receiver `+0x220` and `+0x270`, and whose size is
`0x318` bytes. It passes a group of nine descriptors through receiver vtable
`+0x130`; for the constructor-installed vtable recovered in the preceding
note this resolves to `0xfffffff00668a398`. That function aligns and combines
the descriptors into an allocation, obtains a second mapping, writes the two
base-plus-offset views into the descriptor outputs, and zeroes the first view.
Thus the `+0x220` frequency table belongs to a larger allocated region, with a
second address view at `+0x270`. These observations do not establish the
address type of that view or prove GPU or firmware access to it.

Function `0xfffffff00668d700` is a CPU-side reader of the MHz values. The
handoff routine `0xfffffff006689cc0` calls it with selectors 0, 1 and 2;
execution of each selected case is conditional on its corresponding enable
byte at receiver `+0x580 + 12*selector`. For selectors 1 and 2, the reader
uses the limit at buffer `+0x29c` to index the array at `+0x2a4`, applies the
input parameter and searches/interpolates among entries. The computed results
are stored through receiver `+0x2a8` at offsets `+0x102c` and `+0x1030`,
respectively. This is calculation and a memory update; it does not by itself
identify a GPU clock selector or a hardware write.

The selector dispatch was checked against the full cache: the five bytes at
`0xfffffff0057c3181` are `00 1d 31 45 4b`, giving case targets
`0xfffffff00668d78c`, `...d800`, `...d850`, `...d8a0` and `...d8b8`.
This matters because the AGX-only disassembly lacks the jump table and its
Ghidra decompilation alone misses the two array-reading cases.

## A GPC setter call and its limits

The routine beginning `0xfffffff006690328` has a conditional path which calls
receiver `+0x160` vtable `+0x10` with argument 1 at `0xfffffff006690384`.
That path requires a global flag bit and a non-null object. If the constructor
and Fender vtable binding from the preceding note apply, the target is
`0xfffffff006698d94`: after polling GPC `+0x1000` bit 4 clear, it writes
`argument | 0x10` there, reads it back, and stores the argument in its object.
For argument 1 this gives `0x11`, the same command value used by the direct
pre-ID iOS path and already exercised in the Linux campaign. The setter also
has a polling failure path; this summary is its successful path.

We have not established that `690328` runs before the first RGX identity read,
or that its conditional path is taken in the target boot. It is a separate
routine from the directly traced G4G pre-ID probe. Likewise, the MHz-buffer
reader is reached from a later handoff routine but its ordering relative to
probe is not proved here. The iOS 15 pre-ID code and the Linux outcome remain
as documented in [the pre-ID audit](2026-11-08-j81-ios15-g4g-pre-id-clock-power.md)
and [the campaign summary](2026-11-09-j81-gpc-state-vs-gfx-perf-selector.md).

## Next discriminating work

Trace the lifecycle and callers of `690328` and the performance handoff, and
resolve the mapping's use before assuming either is involved in initial GPU
access. In parallel, look for a concrete provider-side or boot-stage operation
that differs before the first ID read. The table and setter observations do not
justify a new guessed register write or establish a working GPU clock.

Evidence: decoded iOS 15 cache SHA-256
`832cd980f257e6205b8ec131abea2a8470f3a3455f2c7039c890a091149c7389`;
private artifacts `ios15-agx-disasm.txt`, `ios15-perf-consumers.c` and
`rea-ios15-perf-buffer-20261109.json` under `artifacts/live/private/gpu-offline/`.

Follow-up: [firmware-controller lifecycle and probe order](2026-11-09-j81-ios15-firmware-lifecycle-order.md) traces the handoff and setter through the accelerator's start-created object.
