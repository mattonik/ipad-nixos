# J81 iOS 15 PMGR `bcc56c`: per-device timing accounting

Date: 2026-11-08. Offline trace of the local iOS 15 kernelcache's extracted
`com.apple.driver.ApplePMGR` text (`ios15-ApplePMGR.raw`). No device access or
MMIO performed. The cache has embedded `DTPlatformBuild=19H402`; its source
IPSW association with 19H422 is verified by the manifest digest and matching
raw and decoded caches. This does not establish which binary was running on a
device (see `2026-11-08-j81-ios15-kernelcache-provenance.md`).

## Finding

`FUN_fffffff006bcc56c` returns a time-like value used by the PMGR
state-transition bookkeeping loop, not a power-state or bridge operation. Its
callers iterate over up to eight associated records after a device reaches
state 15 and during its state-15 exit. At state 15, the caller stores the
returned value in `+0x40` when record byte `+0x56` is clear; when set, it stores
the value in `+0x58` and adds it to `+0x40`. On the state-15 exit path, the
caller obtains a value only for records with `+0x56` set, then subtracts the
saved `+0x58` from `+0x40` when `+0x58 <= returned value`. This is timing
bookkeeping around a device state transition; the exact units and interpretation
of the accumulated `+0x40` are not established here.

## Body and dispatch

In the raw ApplePMGR slice, VA `0xfffffff006bcc56c` is file offset `0x1356c`.
Its 196-byte AArch64 body (`0x...bcc56c`–`0x...bcc62f`) takes two arguments,
`(pmgr, record)`. The earlier one-argument decompilation was caused by
Ghidra's guessed prototype. At `0xfffffff006bd830c`, the transition caller
loads the associated-record pointer into `x1`; it sets `x0` to PMGR at
`0xfffffff006bd8320` and calls at `0xfffffff006bd8324`. Other xrefs are
`0xfffffff006bd7224`, `0xfffffff006bd73dc`, `0xfffffff006bd73f0`, and
`0xfffffff006bd87ec`.

The body has two time-value sources:

- When `record+0x57` is nonzero, it builds a stack argument block from the
  low/high 32-bit halves of `record+0x30` and calls the object at
  `pmgr+0x160`, through that object's vtable slot `+0xe8`. The call also gets
  a constant string at VA `0xfffffff006bd6328`, selector `1`, pointer to the
  stack output block, and two zero arguments. It returns the first 64-bit
  output value.
- Otherwise it reads through `record+0x28`. If `record+0x54` is clear, it
  reads a 64-bit value directly. If set, it retries a sequence-counter read
  using the 32-bit value at pointer offset 4 around the 64-bit load.

The record is PMGR's per-device/state configuration object, not a GFX bridge
or clock-provider record. Init (`FUN_fffffff006bbf7a4`) parses 0x1c-byte
state-config rows and builds per-entry objects at
`this+0x2fba8 + entry*0x108`. When a row's state mask selects the current state,
it registers the object pointer in the per-state/per-device table at
`this+0x49b8 + state*0x9800 + device*0x40 + slot*8`; the slot comes from row
byte `+0x17` (`0xfffffff006bc4850`–`0xfffffff006bc4868`). The generic transition
caller visits up to eight pointers from that table and passes each selected
pointer as `record` (`bd830c`–`bd8324`). The available inputs do not identify
the constructor values for `record+0x28`, `+0x30`, `+0x54`, or `+0x57`, or
establish whether records are populated for GFX in the runtime configuration.

The indirect target is runtime-selected: the body loads the vptr from the
object stored at `pmgr+0x160`, then loads slot `+0xe8`. Static code proves the
object/slot/calling convention, but does not identify the runtime object's
class or final function address. The PMGR constructor initializes this field
to null; the later assignment/binding of the runtime object was not found in
the extracted code reviewed here. Other PMGR code also uses the `+0x160`
object's virtual methods, so a gate-mediated action is a candidate, not a
resolved target. The callback gets a constant string key, selector `1`, and a
pointer to the stack result block populated from the record's `+0x30` data;
the key and callback semantics remain unresolved. Since its implementation is
unknown, the callback's MMIO side effects cannot be classified.

### Caller eligibility and observed effects

The two call sites in `FUN_fffffff006bd81a8`'s device-transition routine
bound when the helper runs. On entry to state 15, the caller first runs
`FUN_fffffff006bd91a8`, then visits eight associated-record pointers. For each
non-null record with byte `+0x55 == 0`, it calls `bcc56c`; if byte `+0x56 == 0`,
the result replaces the record's `+0x40`, otherwise the result is saved at
`+0x58` and added to `+0x40`. On exit from state 15, it visits those same
records after the transition work and calls the helper only where the pointer
is non-null, `+0x55 == 0`, and `+0x56 != 0`. It subtracts saved `+0x58` from
`+0x40` only when `+0x58 <= result`. These are the concrete caller conditions
and memory side effects established by the decompilation; the linked records'
runtime values are not available offline.

The raw PMGR project and sibling `AppleT7001PMGR` extraction do not expose a
class name, vtable address, or implementation for the object at `+0x160`.
`FUN_fffffff006be3b0c` independently loads an object at the same relative
offset from the object at `param_1+0x88` and invokes slot `+0xe8` with a callback
function pointer and arguments. That confirms the slot is also used as a
callback-dispatch interface in this codebase, but does not identify its
implementation or prove it shares the exact runtime instance used by
`bcc56c`. Therefore no specific gate class, callback body, register write, or
hardware side effect can be reported from the available static evidence.

### Review addendum, 2026-11-08: the `+0x160` object is the PMGR command gate

ApplePMGR uses the same object and slot on its own clock-enable path. In
`0x...bd7a1c`, the code emits trace code `0x2700c001`, then runs the
power-state change `0x...bd7ad0` through `[pmgr+0x160]` vtable `+0xe8`, and
then emits `0x2700c002`. The action argument there is a code pointer
(`2026-11-08-j81-pmgr-2700c00x-are-trace-codes.md`,
`2026-11-08-j81-ios15-clock-gate-to-pmgr-state.md`). `be3b0c` passes a callback
function pointer through the same slot. Both match
`IOCommandGate::runAction(action, arg0, arg1, arg2, arg3)`.

The value that `bcc56c` passes as the first argument, VA
`0xfffffff006bd6328`, is not in a string section. It lies inside ApplePMGR's
own `__TEXT_EXEC` (`0xfffffff006bb9000` to `0xfffffff006beda4c`). It is
therefore most likely the gated action function, called with `arg0 = 1` and
`arg1 =` the stack block built from `record+0x30`. That makes the `+0x57`
branch "run `bd6328` under the PMGR work-loop lock" rather than an unknown
callback. The class name of the `+0x160` object is still inferred from usage,
not read from a vtable or symbol, and `bd6328` has not been disassembled.
Disassembling it is the next cheap offline step. It is the only
not-yet-classified code on GFX's `bd81a8` power-up path, and it runs only for
`state-config` records with byte `+0x57` set.

In the other branch, the function dereferences the record's `+0x28` pointer,
including a sequence-counter retry when byte `+0x54` is set. The body does not
contain an explicit PMGR register accessor in this branch, but the pointer's
provenance and memory mapping were not recovered. Calling it definitively
normal-memory or MMIO-free would exceed the evidence. It is consistent with a
shared time source, which is an inference from the sequence-counter pattern
and the caller's timing bookkeeping.

## GFX applicability and limits

The GFX state-15 path reaches the generic loop after state transition and
bridge apply. GFX's ADT device record has no parent IDs, but that is separate
from these optional per-device/state timing records. Static code establishes
the caller conditions, but not which entries are populated for GFX or whether
their `+0x57` branch is selected. `bcc56c` returns a time-like value used for
state-transition bookkeeping. Its body has no explicit PMGR register
accessor; this is not evidence of additional hardware clock/bridge writes.
The indirect callback's runtime target/effects and the `+0x28` pointer's
mapping remain unresolved. This path is distinct from T7000's per-device
clock-reference count at controller `+0x308`.

The three relevant extracted artifacts are local and ignored by Git:
`ios15-ApplePMGR.raw`, `ios15pmgr-device-calls.c`, and
`ios15pmgr-bridge-use.c`. These findings apply to the local cache whose source
association with 19H422 is verified; they do not establish which binary was
running on a device.
