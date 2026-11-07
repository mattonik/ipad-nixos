# J81 SoC-busy display action before the first RGX read

Offline source trace, 2026-11-07. No live device or MMIO was used.

## Finding

The iOS 8.1 GFX clock path has a real, J81-configured SoC-busy side action
before G4G's first core-window access. It is conditional at runtime. The
source and device tree prove the path is applicable to J81; test4 does not
prove that the action ran, nor that it explains the stalled read.

The ordering is: G4G `FUN_ffffff80032935a0` requests provider clock-on,
provider dispatch reaches the GFX record's special handler
`FUN_ffffff80031ea58c`, its flag bit 1 applies selectors 9 and 10, and flag
bit 2 calls `FUN_ffffff80031eb7c0`. G4G then configures GPC and eventually
dispatches its identity matcher, whose first core read is `0x201000020`.
Thus any display/cache callback taken by the busy handler precedes that read.
The clock and bridge setup is not itself the entire Apple provider call.

## Exact SoC-busy transition

For GFX record flags `0x06`, the special handler calls the busy routine only
on clock enable; this routine increments its reference count. The routine
returns after the count update unless runtime field `+0x980` is nonzero and
setup field `+0x98c` is enabled. It only dispatches a transition on busy-count
edges 0→1 and 1→0. On 0→1 it passes boolean 0; on 1→0 it passes boolean 1.

Setup `FUN_ffffff80031e8e54` initializes `+0x98c` false, then requires
`fb-caching` to be nonzero, a readable `mcc-config-fb-caching`, a resolved
`function-dispidle_ctrl`, and a readable `disp-fb-mcache-id` before returning
enabled. J81's matching iOS 8.1 PMGR record has `fb-caching=1`, configured
cache mode 4, display cache ID `0x75` (`DISP-FB-MCACHE`), and
`function-dispidle_ctrl` targeting `disp0`. These values establish that the
feature is described for J81. They do not establish the result of setup in
the test boot: boot arguments and failed/missing provider resolution can
disable it.

When enabled, the busy-edge handler first sends PMGR action/event
`0x2700c001` for cache ID `0x75` with the edge boolean. It calls the display
idle function with the same boolean. If that call returns success, the
selected MCC configuration is `+0x95c` on 0→1 and the configured value 4 on
1→0. If that differs from the cached mode at `+0x12d`, Apple calls
`FUN_ffffff80031eb6a0`, which invokes the cached `function-mcc_ctrl`
function object only when internal flag `+0x958` is set and object pointer
`+0x978` exists. It passes `(enable=1, requested_mode)` and records the
returned mode at `+0x968` only on success. The caller then updates provider
cache state with `+0x690` and clears the pending bit. Completion sends
`0x2700c002`. The 8.1 helper itself contains no direct MCC MMIO; the operation
is delegated through that function object. iPadOS 15's separate MCC driver
shows an analogous apply path that writes the selected row into its mapped
MCC register block (notably `+0x794` and adjacent configuration/status
registers), but this later implementation is not proof of the exact 8.1
controller-side register writes. The callback's low-level effect and the 8.1
MCC function object's runtime guards remain unresolved. The low-level
meaning of the display callback boolean and all its hardware effects remain
partly opaque, so it should be recorded as 0/1 rather than relabeled
"active" or "idle".

The other runtime gate `+0x980` is set by a separate special flag bit 3.
J81's `DISP0` clock record is the only record with that bit. Therefore the
GFX busy edge can coordinate with display caching only if DISP0 has put the
provider in that mode and the setup above succeeded.

## What can be observed, and what test4 observed

The Apple software state to capture is: `+0x12a` busy reference count,
`+0x980` DISP0 mode, `+0x98c` feature-enabled flag, `+0x132` resolved display
function, and `+0x12d` last-applied cache mode. At the call boundary, record
whether `0x2700c001`/`0x2700c002` were dispatched, the display callback return,
and whether MCC apply ran. Relevant hardware-side evidence would include the
provider/MCC state changes, but reading those undocumented registers is not
qualified as safe by this static analysis.

Test4 has no observations of these fields or callbacks. It directly replayed
selector stores, then set GPC state/control and polled GPC state before the
first RGX read. Its initial PMGR history word was changed by the generic
Linux off/on cycle; it cannot reconstruct the Apple callback's software
history. The test4 result therefore leaves the display action unresolved.
Even a proven omission would only establish a sequence difference, not that
the omission caused the RGX transaction to stall.

Saved GPU/PMGR captures do not close this gap. The Linux probe logs read only
`0x20e020320`; the Nov. 5 inventory lists DT reset-controller nodes at
`0x20290` and `0x20298` but contains no values from those registers. No
captured sample reads either offset, and no captured callback trace exposes
Apple's `+0x980`, `+0x98c`, or MCC cached state. The existing PMGR `0x3ff`
readback cannot distinguish the conditional display path.

## Linux comparison and next experiment

The pinned Linux PMGR driver at
`artifacts/live/private/gpu-offline/linux-src/drivers/pmdomain/apple/pmgr-pwrstate.c`
implements generic power-state and reset operations. It does not parse the
Apple `device-clocks` provider records, track the provider busy edge, dispatch
these events, or call the display/MCC functions. The current J81 test path
therefore cannot express this Apple side action. The iPadOS 15 J81 tuner is a
related later policy implementation, but it is not evidence that Linux has
reproduced the iOS 8.1 provider sequence or that its policy can be substituted
for the older clock callback.

The smallest offline trace model is now in `tools/gpu_apple_clock_model.py`
as `model_soc_busy_transition`; its assert-based test covers disabled and
unknown gates, first-busy and last-idle edges, same-mode no-op, unknown
callback/mode, and unbalanced release. It emits abstract callback/MCC
requests only and never emits MMIO. Applying it to the current capture still
requires unknown runtime inputs, so it cannot declare whether test4 would
have taken the branch. This
is the defensible next experiment: trace the required software inputs and
outcomes in a faithful provider model while keeping every runtime value that
isn't captured explicitly unknown. If a live follow-up is later considered,
first add passive software
checkpoints around a faithful provider implementation and obtain explicit
review of every added MMIO write; do not treat another RGX read as the
experiment. Current evidence does not justify a new hardware sequence or
claim that display/cache coordination will fix the hang.

## Callback follow-up: concrete static facts

The matching iOS 8.1 PMGR device-tree `mcc` node has compatible
`mcc,t7000` and `function-mcc_ctrl` points to its MCC service. The
prelinked iOS 8.1 `AppleS5L8960X` kext metadata identifies
`AppleS5L8960XMemCacheController` as the `mcc,s5l8960x` provider; its
strings name `function-mcc_ctrl` and `_mccEnableCache`. Its startup
diagnostics show it maps registers, loads `config-data`, and reports a
maximum config count. It checks boot argument `-disable_mcc`; its message
says it will skip switching the MCC into cache modes. This is a concrete
disable condition, but neither that boot argument nor the selected runtime
config is captured for test4. The 8.1 controller method body and exact
register writes remain untraced here; iPadOS 15's `+0x794` behavior does
not prove those writes.

The iOS 8.1 `AppleH7GADBE0` prelink record matches class
`AppleMobileADBE0` to compatible `adbe0,t7000`, supporting the identity of
the `disp0` callback provider. It does not expose the callback's 8.1
implementation in the saved decompilations. The 15.8 display-pipe callback
stores the passed boolean and calls display-controller methods, but that
remains a later implementation, not proof of the 8.1 callback's effects.

One concrete 8.1 output is visible in `t7000-map.c`: DISP0's special flag
sets provider `+0x980` to 1 on enable and 0 on disable, and performs
read-modify-write operations on mapped offsets `0x20290` and `0x20298`.
It sets bit `0x40000` in both on enable and clears mask `0x000f0000` on
disable. It then requests an MCC mode. These offsets are relative to
Apple's mapped PMGR block; no live value or register semantic has been
measured. A successful MCC callback is recorded in software at `+0x968`;
the helper requires internal flag `+0x958` and a non-null object at
`+0x978`.

The discriminating observation for test4 is an Apple-compatible software
trace at GFX clock-on that records DISP0's `+0x980` change and writes, the
GFX busy-edge gate (`+0x98c`, `+0x12a`), display callback return, MCC
guard/call/result (`+0x958`, `+0x978`, `+0x968`), and the following first
RGX core read. Existing Linux captures contain none of this state. The 8.1
MCC and display-controller callback bodies still need focused
disassembly/xref work before register-level equivalence can be claimed.

## Focused iOS 8.1 controller disassembly

The kernelcache `__PRELINK_TEXT` was carved using its Mach-O section mapping
and the `AppleS5L8960X` / `AppleH7GADBE0` executable load addresses from
prelink metadata, then analyzed as AArch64 in Ghidra. This is static
disassembly, not a runtime trace. The MCC mode apply routine is
`FUN_ffffff8002e53924`; Ghidra xrefs show it called from controller startup
(`0x2e53754`) and from both arms of the controller's
`callPlatformFunction` dispatcher (`0x2e53ca4`, `0x2e53d48`). That dispatcher
checks the `-disable_mcc` field (`self+0xb4`) before calling mode 1 or mode 0.
The startup path at `0x2e53400` reads `config-data`, derives the maximum
configuration count, reads `-disable_mcc`, and calls the enable path only if
the flag is zero. The performance-controller setup at `0x2e55c5c` reads
`soc-tuning`; if enabled it resolves `function-mcc_ctrl` into `+0x8d0` and
loads `mcc-config-disp-on` / `mcc-config-disp-off` into `+0x8c0` / `+0x8c4`.

The mode apply routine uses the controller's mapped base at `self+0x98` and
selected row at `self+0xa8`. For mode 1 it writes `0x1110` to mapped offset
`0x850`, composes offsets `0x838` and `0x83c` from row fields, reads the
current five-bit mode from `0x834`, replaces the five-bit mode in `0x830`
with row field 0, sets bit 0 in `0x800`, and sets or clears bit 8 in `0x830`
according to row field 4. The routine reads `0x834` but does not write it.
It then calls helper `0x2e54128`. For mode 0 it clears bit 0 in `0x800`,
clears the five-bit mode field and sets bit 8 in `0x830`, then calls helper
`0x2e54090(self,0,0)`. The helpers perform read-modify-write operations with
the controller's serialized MMIO access guard at `self+0xf8`. This pins the
8.1 MCC side effect to actual controller register writes; the offsets are
relative to Apple's mapped block and their undocumented hardware semantics
are not inferred here. The start-time `-disable_mcc` value and all runtime
mode selections remain unknown for test4.

The `AppleH7GADBE0` image contains the `AppleMobileADBE0` and
`AppleDisplayPipeSetSystemIdleStateFunction::callFunction` diagnostic/name
strings, confirming the likely display-side implementation family, but
their method-name strings have no direct code xrefs in the isolated Ghidra
import. I have not yet tied the 8.1 display-idle function object to a specific
method body or proved what its boolean changes. Do not substitute the iOS 15
display-pipe implementation for this missing 8.1 trace.

For a single future software trace, the highest-value fields remain the
boot-argument result for `-disable_mcc`, resolution and return values for
`function-mcc_ctrl` / `function-dispidle_ctrl`, provider fields `+0x980`,
`+0x98c`, `+0x12a`, `+0x12d`, MCC guard/object/result `+0x958`, `+0x978`,
`+0x968`, plus passive before/after observations of mapped MCC offsets
`0x800`, `0x830`, `0x834`, `0x838`, `0x83c`, and `0x850` around DISP0 and
GFX clock events. These observations would distinguish callback omission,
disable gates, and successful apply; static evidence does not show whether
any branch ran on test4. No hardware was accessed during this investigation.

Evidence: `artifacts/live/private/gpu-offline/gfx-clock-special.c`,
`framebuffer-cache-setup.c`, `t7000-flags.c`, `ios81-dt.json`,
`ios81-agx-disasm.txt`, and `g4g-ident.c`; ordering cross-check in
`research/2026-11-07-j81-core-read-missing-apple-dispatch.md`; hardware
result in `research/2026-11-07-j81-core-revision-after-clock-test4.md`.

## DT config-data and the decision before the first RGX read

Decoded the saved iOS 8.1 J81 DT `mcc.config-data` as 220 bytes: five
44-byte rows, each eleven little-endian u32 values. The first three rows are
`[0x10, 0, 0x95f, 1, 10, 10, 1000, 100000, 100, 0x55, 0x11]`; the last
two are identical except word 1 is 1. This is the
DT-provided table; without the 8.1 MCC parser's row-field mapping, do not
assign semantic names to those words. PMGR separately supplies
`fb-caching=1`, `mcc-config-fb-caching=4`, `disp-fb-mcache-id=117`,
`function-dispidle_ctrl={phandle:disp0,function:ADPi}`, and
`function-mcc_ctrl={phandle:mcc,function:Mem$}`. The MCC node is
`compatible=mcc,t7000` and has that config-data property.

Therefore the relevant branch condition is now concrete, even though its
runtime value is not: before the first RGX core read, Apple takes the MCC
busy-edge path only if the GFX special handler is invoked with enable, its
record has flag bit 2, DISP0 has previously set provider `+0x980`, setup
`+0x98c` succeeded (all required properties/function resolution), and the
busy count crosses 0↔1. The display-idle callback must also return success
before the caller updates its selected mode and asks the MCC function
object to apply it. The MCC provider's separate `-disable_mcc` boot-argument
gate can still suppress that mode switch. Thus `mcc-config-fb-caching=4`
is the requested mode on the applicable edge, not evidence that mode 4 was
actually selected or written on test4.

Linux cannot truthfully diagnose Apple's callback decision from the current
test payload: it has no corresponding provider object, display callback,
or MCC service, and reading MCC registers would add unqualified MMIO. The
smallest useful next diagnostic is a software-only trace in a faithful
Apple-provider-compatible model that logs, at GFX clock-on, these branch
inputs/outcomes as known/unknown: DISP0 `+0x980`, setup `+0x98c`, busy
count `+0x12a`, callback return, MCC disable gate, and MCC request/result.
For the current Linux test, the correct exclusion is to label Apple
display/MCC coordination **not reproduced and runtime applicability
unknown**; do not add guessed MCC writes before RGX identification. The DT
decode was performed offline from the saved tree; no device was accessed.

## MCC register window and mode-4 row (offline address audit)

The saved iOS 8.1 tree places `mcc` directly under `arm-io`, with
`reg={addr:0,size:0x200000}`. The `arm-io` node has two `ranges` entries;
the first maps child address `0` to parent address `0x02000000` for a
`0x01000000` window. Under standard DT `ranges` translation, the MCC resource
therefore resolves to `0x02000000..0x021fffff` (2 MiB). This is a static DT
translation, not a measured bus decode; Apple's resource mapping must be
confirmed before any access. The PMGR provider's separate mapping is described
by PMGR `reg` entries; SoC-busy RMWs at provider-base `+0x20290` and `+0x20298`
are not MCC-relative writes.

The MCC `config-data` is 220 bytes, exactly five 44-byte little-endian rows:

```
0: [0x10, 0, 0x95f, 1, 10, 10, 1000, 100000, 100, 0x55, 0x11]
1: [0x10, 0, 0x95f, 1, 10, 10, 1000, 100000, 100, 0x55, 0x11]
2: [0x10, 0, 0x95f, 1, 10, 10, 1000, 100000, 100, 0x55, 0x11]
3: [0x10, 1, 0x95f, 1, 10, 10, 1000, 100000, 100, 0x55, 0x11]
4: [0x10, 1, 0x95f, 1, 10, 10, 1000, 100000, 100, 0x55, 0x11]
```

If requested numeric mode `4` indexes the table directly, the selected row is
the final tuple. The PMGR request value `4` is proven; direct row-index
semantics are not proven by the available 8.1 parser disassembly. The traced
controller apply structure is: enable writes `0x1110` to mapped `+0x850`,
forms `+0x838` and `+0x83c` from selected-row data, RMWs `+0x830` with the
row's 5-bit field and its field-4-controlled bit 8, sets bit 0 at `+0x800`,
reads (but does not write) `+0x834`, then calls serialized helper
`0x2e54128`. Disable clears bit 0 at `+0x800`, clears the 5-bit mode field
and sets bit 8 at `+0x830`, then calls helper `0x2e54090(self,0,0)`.
Because the row-field mapping and helper's write/poll body are absent from the
available 8.1 artifacts, exact numeric values for `+0x838`, `+0x83c`, and the
final `+0x830` word for mode 4 remain unknown.

The analysis establishes code-initialized software state, not power-on
register contents. Controller startup loads the table, checks `-disable_mcc`,
and may invoke its enable path; later tuner setup loads display-on and
display-off selectors. No initial MCC MMIO values, startup-selected row,
boot-argument value, or test4 MCC state were captured. Test4's last known
event before its incomplete core revision read was the host-requested read of
`0x201000020`; it contains no MCC observation, so the stall cannot be
correlated with mode 4 or a specific MCC write sequence.

## iOS 8.1 ADBE0 callback body and queued work

A focused split import of the iOS 8.1 `AppleH7GADBE0` image closes the callback
body. The image was carved from `__PRELINK_TEXT` at load address
`0xffffff80032c9000` through `0xffffff8003304000` and analyzed as AArch64 in
Ghidra; this is static evidence only.

`AppleDisplayPipeSetSystemIdleStateFunction` is instantiated with vptr
`0xffffff80032e7da0`. Its vtable slot `+0x78` is
`0xffffff80032ce13c`. That method takes the callback boolean, reads its
`mpADP` member at `+0x28`, and calls `0xffffff80032cc914`. If `mpADP` is null,
it logs and returns `0xe00002c9`. `0xffffff80032cc914` first checks its
controller's readiness field at `+0x7a8`; zero returns `0xe00002e3`. Otherwise
it calls the kernel import `thread_call_enter1` with the controller's queued
thread-call object at `+0x8e8` and the boolean. A nonzero enqueue result maps
to `0xe00002d5`; success returns zero. The method is therefore asynchronous;
its success is queue acceptance, not proof that the display work completed.

The thread-call object is allocated at display-controller init by
`thread_call_allocate(0xffffff80032ca4c8, controller)`. Its worker casts the
argument back to `AppleDisplayPipe` and calls
`0xffffff80032cc9a4(displayPipe, boolean)`. That routine returns success
without further action if vtable `+0x798` reports not ready. When ready, it
calls the display-controller object's vtable `+0xe0` with worker
`0xffffff80032cca44` and the boolean. The final worker again checks display
readiness; for nonzero boolean it also checks the idle-order predicate
`0xffffff80032cab04(displayPipe, 0)`. If that predicate is false, it
increments the “Caching order when idle count” diagnostic counter and calls
its vtable `+0x28`. When the boolean differs from byte `+0x8c5`, it stores the
new value, publishes `MemCacheState`, maps boolean true to numeric state 1 and
false to state 2, then calls the display-pipe vtable `+0xc0` with that state.

This proves the 8.1 callback schedules display-pipe work and, after additional
readiness and state-change checks, publishes a memory-cache-state property
and passes a mapped numeric state to `0xffffff8002a00cf4`. That imported
target resolves inside the iOS 8.1 `IOMobileGraphicsFamily` image. Its body
checks enable/state guards, asks a vtable `+0x578` method for a value, builds
or fills a swap structure, then calls vtable `+0x580`; it contains no direct
MMIO. This establishes an internal graphics/cache state dispatch, but the
controller-side register effect remains unresolved. It does not prove a
physical panel power transition. The argument stays a boolean: source names include
“SystemIdleState”, but the GPU-side edge value is passed through unchanged,
and the worker applies conditional state changes asynchronously. The inner
controller callback function supplied to vtable `+0xe0`, the semantics of the
idle-order predicate, and the hardware effects of the controller request
remain unresolved.

The matching iOS 8.1 function definition is in the split image's vtable and
constructor, not recoverable from test4's saved captures. Available captures
contain neither the callback enqueue/completion nor `MemCacheState`, the
`+0x7a8` readiness gate, nor the display-pipe worker's state/order calls.
Accordingly, they cannot establish whether test4's callback ran or what state
the display was in. No hardware was accessed.


The boolean mapping and ordering are now explicit. On the first SoC-busy edge
the caller passes `false`, which the display worker maps to `MemCacheState = 2`;
on the last busy release it passes `true`, mapped to `MemCacheState = 1`. The
GPU-side call only invokes `thread_call_enter1`; there is no wait for the
worker's `+0xe0` dispatch or the later `IOMobileGraphicsFamily` state method
before the busy handler returns. The queued work may therefore complete before
or after the first RGX read; this static path does not establish its schedule.

`0xffffff8002a00cf4` is in the `IOMobileGraphicsFamily` prelink image (the
neighboring executable range in the iOS 8.1 prelink metadata is
`0xffffff80029fe000`–`0xffffff8002a13000`). It returns `0xe00002d8` when
field `+0x7e1` is clear. For requested states 1–4, a non-null object at `+0x6b0`
whose byte `+0x278` is clear short-circuits with success. Otherwise it obtains a
value through vtable `+0x578` and invokes `+0x580` with either state-specific
fields or a local swap structure. No direct hardware writes occur in this
method. The meanings of those guards and the downstream `+0x580` operation are
not assigned without resolving the runtime vtable owner.

## Weekend Linux control-boot comparison

The saved read-only control-boot inventory at
`artifacts/live/j81-readonly-20261107T114456Z/` reports `simpledrmdrmfb` on
`/sys/class/graphics/fb0`, `simple-framebuffer` on the chosen framebuffer
platform device, and a connected 1536x2048 `card0-Unknown-1` output. The
recorded DRM/framebuffer owner is therefore Linux simpledrm over the boot
framebuffer; the snapshot does not expose an Apple display-pipe or MCC
controller as the owner. This is an inventory result, not proof that the
hardware block is powered down or that no private service exists elsewhere.
The saved dmesg contains simpledrm initialization and a PMGR `sync_state()`
pending message for SPI, but no display-idle or MCC callback trace.

This sharpens the implementation gap: iOS 8.1's GPU-side display callback
returns after enqueueing `thread_call_enter1`, then its worker may publish
`MemCacheState` and invoke an internal graphics state callback later. Linux's
saved inventory shows only the simple framebuffer path and has no corresponding
captured callback/completion events. A trace of callback acceptance alone would
not establish whether the queued state transition completed before the first
RGX transaction. The discriminating software trace must capture both enqueue
result and worker completion/state dispatch, alongside the PMGR gate, busy-edge,
and MCC apply observations. The weekend capture was read-only; it contains no
MCC MMIO or GPU-read observations and does not change the test4 conclusion.
