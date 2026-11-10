# J81 iOS 15 firmware-controller lifecycle and probe

Offline static analysis, 2026-11-09, following
[the buffer and state-call analysis](2026-11-09-j81-ios15-perf-buffer-consumer.md).
The relevant cache and active-vtable assumptions are the same as in that note.

## The object is created in accelerator start

For the G4G accelerator vtable installed at `0xfffffff006f2f2d0`:

| Slot | Target | Observed role |
| --- | --- | --- |
| `+0x2a8` | `0xfffffff00668322c` | G4G probe containing the RGX identity read |
| `+0x2b0` | `0xfffffff0066990ac` | Calls common accelerator start `0xfffffff00666d6e4` |
| `+0x848` | `0xfffffff00669afa8` | Constructs the firmware-controller object and installs vptr `0xfffffff006f2de28` |

Within the common start function, `0xfffffff00666dd54`–`...dd68` calls
accelerator slot `+0x848`, checks the returned pointer and stores it at
accelerator `+0xdd8`. Later, `0xfffffff00666e838`–`...e848` invokes
the object's `+0x78` initializer with the accelerator. Under the recovered
controller vtable, this leads through `0xfffffff00668f2d4` to
`0xfffffff00668735c`, the function that creates and initializes the Fender
object at controller `+0x160`.

Consequently, the Fender object whose virtual setter we traced is created by
the accelerator's start path, while the identity read is in its probe path.
This supports ordering the inspected object-dependent operations after the
probe for the normal probe-then-start lifecycle. This is a lifecycle inference
from static code and normal IOService operation, not a trace of a particular
boot or proof that no other object or provider executes similar writes earlier.

## Controller call sites

Start registers `0xfffffff006673f00` as a callback (see the decompilation of `0xfffffff00666d6e4`). On a branch in this callback, it obtains the controller
from accelerator `+0xdd8` and calls its `+0x98` slot at
`0xfffffff006673fa0`–`...3fac`. Under the recovered controller vtable this is
`0xfffffff00668f770`, which calls `0xfffffff00668911c`; that routine calls
controller `+0xa0` at `0xfffffff006689ca0`–`...9cac`, resolving to the MHz
handoff `0xfffffff006689cc0`.

The same callback later calls controller `+0xc0` at
`0xfffffff006673ff4`–`0xfffffff006674000`. For this vtable the target is
`0xfffffff006690328`, whose conditional state-1 Fender setter call is discussed
in the preceding note. An additional controller `+0xc0` call occurs in
accelerator function `0xfffffff006671f84` at `...1ff4`–`...2000`, after
other controller and accelerator calls. Both are conditional on their callers'
paths and on runtime vtables. Callback registration alone does not establish
exact execution time, and no runtime callback trace is available.

These links make the MHz handoff and object-dependent state setter poor
candidates for a *missing pre-probe operation* on the normal path. They do
not establish the live GPU clock, exclude provider-side work during probe, or
prove that Linux and iOS reach identical hardware states. In particular, the
separate direct GPC write in the probe itself still precedes the ID read and
was already known.

## Next direction

Prioritize differences available before or inside the probe: provider clock
and power side effects, earlier boot-stage state, and observations that can
separate GPC success from RGX accessibility. A new register write still needs
independent evidence; the newly resolved later controller calls do not supply
one. No hardware was accessed in this round.

Evidence: `ios15-agx-disasm.txt`, `ios15-perf-consumers.c`, and
`ios15-fw-objects.c` in `artifacts/live/private/gpu-offline/`, and full-cache
vtable entries in the decoded 19H422-associated kernelcache SHA-256
`832cd980f257e6205b8ec131abea2a8470f3a3455f2c7039c890a091149c7389`.
