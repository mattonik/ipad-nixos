# J81 GPC and first core-read caller boundary

Offline follow-up to the J81 RGX-read hang. No device access or firmware
execution was performed.

## Apple iOS 8.1 order from original instructions

`FUN_ffffff80032935a0` is the G4G accelerator start path. Its disassembly at
`0xffffff80032936fc..0xffffff80032937e8` confirms this order:

1. It fetches the GPC resource and calls accelerator vtable `+0x790` with the
   provider object.
2. It invokes provider vtable `+0x560(1, 0)` and `+0x568(1, &local, 0)`.
3. It maps the selected GPC resource, writes `+0x10000=0xffff0000`,
   `+0=0x40000000`, and `+0x1000=0x11`, then polls bit 4 clear when the
   device flag requests polling.
4. It calls accelerator vtable `+0x800` with a result byte. The recovered
   function body does not resolve that virtual target or prove exactly which
   instruction inside it performs the first core-register read.
5. It then requests GPC state zero (`+0x1000=0x10`) and releases the provider
   state if the local flag was set.

This makes the missing *caller-level* precondition concrete: the successful
Linux experiments reproduce the PMGR runtime-power lease and the three GPC
writes, but do not reproduce or identify the two provider calls immediately
before them. The related iOS 8.1 clock-table analysis identifies GFX device
`0x7c`, power index 100, and selectors 9/10; iOS 15's PMGR reconstruction
shows a separate clock-provider action and bridge-table writes. Together these
are consistent with the provider calls supplying clock/performance setup, but
the exact iOS 8.1 `+0x790`, `+0x560`, and `+0x568` semantics are still
unresolved. Do not map them to the iOS 15 routines solely by matching offsets.

The `+0x790` lead is weaker after checking the static data: three pointer tables
contain `FUN_...32935a0` at relative `+0x240` (candidate bases
`0xffffff80032af000`, `0xffffff80032b3810`, and `0xffffff80032b4c50`). Their
`+0x790` entries respectively point to `0xffffff800328fb24`,
`0xffffff80032a3aa8`, and `0xffffff80032a5cbc`; all three bodies reduce to
`return 0x60000`, and the start routine ignores the return. This is not evidence
of a clock write. Their `+0x800` entries point to object serialization/refcount
methods in the static data, which likewise does not identify the active runtime
override. These tables' ownership by the live `param_1` object is not proven.
Thus `+0x560/+0x568` remain the strongest unresolved pre-GPC provider calls;
the `+0x800` call's active target and role also remain open.

## Separate post-LDR path

`FUN_ffffff800329eb28` is a firmware-object vtable method, not a prerequisite
proven to run before the first ID read. Its instructions at
`0xffffff800329eb44..0xffffff800329eb8c` set hold, poll hold `0x20`, poll GPC
state zero, then write the GPC base control word. It continues with META-slave
status/control handshakes and waits for controller/SLC idle. The static table
entry is at `0xffffff80032b30f8`; a cross-reference search found only this
table reference and did not establish which runtime/subclass vtable is active.
The event-0 callback at `FUN_ffffff800329f6cc` latches firmware-alive and
signals the provider event source. These are later firmware control-plane
steps; they cannot be assumed to repair the pre-firmware core-read path.

## Comparison with Orchard and Cascadia

Orchard's A9/G5P wake path runs runtime PM, a bounded PMGR off/on reset
generation, bridge preparation, then the three GPC writes and a bit-4 poll.
Its ID read follows that wake. This differs from J81: repeating a PMGR cycle
and reaching GPC state 1 still left J81's first `0x201000020` read hanging.
The A9 path is useful as an ordering precedent, not evidence that its transport,
bridge setup, register semantics, or read gates fit A8X/G4G.

Cascadia's A5/SGX543 bring-up gives a second-generation-specific warning: its
master bank is readable after power-on, but its per-core banks hang until the
iOS clock/reset initialization runs. Its driver forbids broadcast-bank reads
and nonexistent core-bank reads in the accessor. This supports keeping J81's
core window distinct from the known-good Fender/GPC window and deriving
readability gates from the exact A8X source. A5's SGX register values, banking,
and clock sequence do not transfer to J81.

## Next offline target and stop condition

Resolve the J81 call targets and data dependencies for `+0x790`, PMGR `+0x560`
and `+0x568`, and accelerator `+0x800` from the iOS 8.1 original instructions,
kernel symbol data, and runtime-vtable construction. Only then can the
pre-core-read initialization order be compared against the Linux PMGR/GPC
probe. The existing hardware evidence does not isolate which omitted step
caused the hang. `+0x790` is currently a low-confidence lead; `+0x560/+0x568`
are unclassified provider dispatches, not yet proven to be clocks. No RGX read,
firmware upload, or GPC experiment follows from this note.

Evidence: `artifacts/live/private/gpu-offline/ios81-agx-disasm.txt` around
`0xffffff80032935a0` and `0xffffff800329eb28`; decompilations in
`gpc-link.c` and `ios81-postldr.c`; Ghidra xrefs checked offline. The A9
comparison is `artifacts/live/private/gpu-offline/orchard-g5p-transport.patch`;
the A5 comparison is the Cascadia `apple_sgx_hw.c` and `sgx-probe.sh` source.

## Follow-up: shared provider dispatch context

An additional iOS 8.1 caller narrows the interpretation of the two methods.
`FUN_ffffff80032871f0` (in `key-functions.c`) obtains the same nested provider
object from `param_1[0xb] + 0x2c8`, then issues `+0x560(state, 0)` followed by
`+0x568(state, &local, 0)`. Its `state` is passed through from the caller and
the wrapper tracks separate nonzero-return counters for these calls. This
strongly indicates a paired provider state request and associated result/query
operation; it does not prove the concrete method names or side effects.

`FUN_ffffff80032a0d44` is a second caller with the same receiver expression
and slots. It invokes the pair using the requested state, then, when a device
flag is set, submits a separate GPU clock/power update (`FUN_ffffff800329b378`
and the clocking helper), and finally updates the GPU's local PM state. Thus
the pair belongs to a PMGR-like state provider interface; the explicit clock
work is a later, separate operation in this wrapper. That makes it unsafe to
describe the pair itself as a proven clock enable. The G4G start path invokes
the pair without this wrapper's subsequent clock update, so this caller does
not prove that its state-1 request establishes the needed GPU clock.

The receiver is loaded from `param_1[0xb] + 0x2c8` in both transition methods.
The parent object is the AGX context (its fields include firmware/GPU runtime
flags and state), but the reviewed constructor artifacts do not assign that
nested field. This evidence therefore narrows the interface role while leaving
the runtime service class and exact vtable implementation unbound.

The same offsets are used in `FUN_ffffff800266c17c` (`pmgr-hooks.c`) as part of
a device power transition. There, `+0x568(device_index, &field)` supplies a
value subsequently compared with the current and target performance-level
values, and `+0x570(device_index)` follows. This supports a PMGR/device-state
or performance-provider role for `+0x568`; it still does not establish the
specific GPC caller's target implementation. In G4G start, the `+0x560(1,0)`
and `+0x568(1,&local,0)` calls immediately precede GPC mapping/control writes,
but an enable/prepare interpretation is only a caller-context inference.

The iOS 15 AGX stop path also invokes the provider's `+0x570(0,0,0)` then
`+0x568(0,0)` before clearing its active flag (`ios15-g4g-preprobe.c:136`);
this is cross-version contextual corroboration only, not identity proof. No
matching offsets are used as a basis for equating iOS 8.1 and iOS 15 classes.

Evidence: `artifacts/live/private/gpu-offline/key-functions.c` around
`FUN_ffffff80032871f0`, `pmgr-hooks.c` around `FUN_ffffff800266c17c`,
`key-functions.c` around `FUN_ffffff80032a0d44`,
`gpc-link.c` around `FUN_ffffff80032935a0`, and
`ios15-g4g-preprobe.c` around the provider teardown. Concrete vtable targets,
provider class ownership, and clock/register side effects remain unresolved.

## Public API cross-check

The public XNU `IOService::setPowerState(unsigned long, IOService *)` signature
is arity-compatible with `+0x560(state, 0)`, so `+0x560` could be that inherited
IOService method. The match is not established: the slot was not resolved to
an IOService vtable entry, and ApplePMGR is a separate proprietary kext. The
paired `+0x568(state, &out, 0)` is not the documented zero-argument
`IOService::getPowerState()`, and so must not be labeled `getPowerState` based
only on the adjacent slot offset. ApplePMGR class inventories for a later
T7000-era kernel list ApplePMGR, ApplePMGRNub, and `ApplePMGRFunction*` classes,
including clock- and power-gate helpers, but provide neither this J81 object's
runtime type nor method offsets. This is contextual evidence, not a target
resolution.

Sources: [Apple `IOService::setPowerState`](https://developer.apple.com/documentation/kernel/ioservice/1532866-setpowerstate),
[XNU `IOService.h`](https://github.com/apple-oss-distributions/xnu/blob/main/iokit/IOKit/IOService.h),
and the later [AppleTV5,3 9.0.1 kernel class inventory](https://raw.githubusercontent.com/stefanesser/ios-kerneldocs/master/classes.AppleTV5%2C3_9.0.1_13T402.pdf).
