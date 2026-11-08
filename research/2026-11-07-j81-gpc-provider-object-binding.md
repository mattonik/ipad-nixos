# J81 GPC provider object binding

Offline follow-up to `2026-11-07-j81-gpc-core-read-caller-boundary.md`.
No device access or firmware execution was performed.

## New object-flow result

The iOS 8.1 `AGXG4G_A0` personality in the matching `12B410` prelink data
matches both `gpu,t7001` and `sgx,t7001`, and declares
`IOProviderClass = AppleARMIODevice`. In `ios81-agx-disasm.txt`,
`FUN_ffffff8003299584` stores its second argument (`param_2`, the provider
passed into AGX setup) at `param_1 + 0x58` (`param_1[0xb]`) at
`0xffffff8003299650`. It subsequently reads fields from that same provider
object, confirming that this field is the retained provider pointer rather
than an unrelated AGX-owned object.

The G4G probe `FUN_ffffff80032935a0` receives that provider as its second
argument. At `0xffffff80032936fc..0xffffff8003293718`, after the base probe
and the G4G property hook, it directly dispatches `+0x560(1, 0)` and
`+0x568(1, &local, 0)` on `param_2`, before mapping GPC and issuing the
three GPC writes. Therefore the GPC-start calls use the actual provider
object selected by the matching AGX personality; they are not calls on the
PMGR subprovider reached by the distinct nested `provider + 0x2c8` expression
in transition wrappers.

This closes the object-flow ambiguity, but not the runtime class identity:
`AppleARMIODevice` is a superclass constraint and a personality provider
class. Static evidence here does not reveal whether the live J81 instance is
exactly that class or a subclass, nor does it provide a runtime IORegistry
tree. The previously resolved AppleARMIODevice implementations remain the
best-supported slot interpretation, while the selected gate IDs (`0x7c`)
and downstream PMGR routing are established separately by the matching
device tree and platform analysis.

## Actionable next step

Trace the AppleARMIODevice metaclass/vtable construction and the 12B410
prelink matching chain for the `gpu,t7001` provider to identify the class
that instantiates the `sgx` node. The useful boundary is the service that
owns the provider object passed at `FUN_ffffff8003299584`, not the unrelated
`+0x2c8` nested transition wrapper. If the match chain only proves an
AppleARMIODevice subclass, treat `+0x560/+0x568` as the inherited gate
wrappers and use the exact J81 `clock-gates`/`power-gates` arrays to continue
into `AppleT7000PerformanceController`; no hardware experiment is needed.

## Follow-up: inherited slot chain resolved from the original 12B410 image

The full static dispatch path is now established in the local 12B410
artifacts:

1. The `AppleT7001IO` personality matches `arm-io,t7001`. Its `start()` at
   `0xffffff8003181414` resolves `function-clock_gate` and
   `function-power_gate` from the `arm-io` node and registers
   `FUN_ffffff8003181b64` / `FUN_ffffff8003181bf0` as the corresponding
   platform-function callbacks. Both J81 properties point to the `pmgr`
   node. The T7001IO instance vtable at `0xffffff80031820f0` puts these
   callbacks at the `AppleARMIODevice` controller slots `+0x558` and
   `+0x560`.
2. `AppleARMIO`'s child-publishing path passes its controller object through
   `FUN_ffffff8002665074` to `AppleARMIODevice` initialization
   (`FUN_ffffff8002665ab0`), which stores it at the device object `+0x88`.
   Thus the GPU provider remains the generic `AppleARMIODevice` service;
   its gate methods forward to the attached `AppleT7001IO` controller.
3. The two T7001IO callbacks resolve the registered platform-function
   objects and call their `+0x78` method. In the matching 12B410
   `AppleT7000` personality (`pmgr,t7000`), those function methods target
   `AppleARMPerformanceController` vtable slots `+0x680` (clock) and
   `+0x688` (power).
4. The original ARMPlatform bytes place `0xffffff800266aaa8` and
   `0xffffff800266aae4` at `0xffffff8002695ef0` and `0xffffff8002695ef8`.
   The same table base, `0xffffff8002695870`, has the base controller
   callbacks `+0x558 = 0xffffff800266c17c` and `+0x560 =
   0xffffff800266c404`. Direct disassembly of `+0x680` and `+0x688` shows
   each loads its cached callback pointer (`this+0x2a0` / `this+0x2a8`),
   then tail-dispatches through the controller workloop at
   `workloop+0xe0`. Missing function boundaries in Ghidra were a
   disassembly-boundary issue; the original instructions and raw vtable
   words resolve the targets.
5. `AppleT7000PerformanceController::start()` at
   `0xffffff80031e6fc8` installs its power callback
   `0xffffff80031e7bbc` in the `+0x2a8` field before parent start. That
   callback reads and consumes the controller's `WAS_PWRGATED` bitmap for
   the passed device ID (124 on the GFX gate path); it returns success and
   reports the prior gated indication through the output parameter. The
   clock callback is inherited from
   `AppleARMPerformanceController` at `0xffffff800266c17c`; it tracks the
   device reference count and invokes the controller's state-application
   path on a transition.

This is a high-confidence static call chain from the GPC probe's receiver to
the J81 PMGR controller. It still does not reveal the device's live power
state or whether GFX's callback output is nonzero at probe time. In practical
terms, the Apple probe's clock request can reach the controller's managed
clock/dependency path, while its power request only consumes an already
recorded power-gating indication; neither should be modeled as a simple raw
gate toggle. The stored callback's return value does not report whether a
clock or power transition just occurred.

### Keep the two provider slots and the controller slots separate

For the G4G probe receiver (`AppleARMIODevice`), the slot resolution is
distinct and direct: provider `+0x560` is
`AppleARMIODevice::enableDeviceClock` (`0xffffff80026656d8`); provider
`+0x568` is `AppleARMIODevice::enableDevicePower`
(`0xffffff8002665788`). In the G4G call, these are
`enableDeviceClock(true, index 0)` and
`enableDevicePower(true, &local, index 0)`. The wrappers independently
select `clock-gates[0]` and `power-gates[0]`, then call the attached
`AppleT7001IO` controller's slots `+0x558` and `+0x560`, respectively. J81
`sgx` supplies `0x7c` for both arrays.

Those controller slots then reach different platform functions:
`function-clock_gate` and `function-power_gate`. Their `+0x78` methods
dispatch to PMGR slots `+0x680` (clock) and `+0x688` (power). Both PMGR
slots use the controller's workloop and cached callback; they are not the
provider slots `+0x560/+0x568`. The clock callback is the inherited
reference-count/dependency path (`0xffffff800266c17c`). The T7000 power
callback installed at `+0x2a8` is `0xffffff80031e7bbc`; it consumes a
previously recorded power-gated bitmap bit and returns that indication via
the output pointer. It does not itself gate power.

Keep the three identifiers separate: the `sgx` gate selector is `0x7c`
(decimal 124); the PMGR device table maps that device ID to power-state index
100; and the PMGR power-state register is at `0x20320` (`0x20000 + 100 * 8`).
The provider wrapper selects `power-gates[0]` (therefore passes 124),
`AppleT7001IO` forwards its callback arguments unchanged to the platform
function object's `+0x78`, and the PMGR controller's `+0x688` workloop thunk
forwards the device ID to the installed T7000 power callback. That callback
indexes the `WAS_PWRGATED` bitmap by its argument, so this path tests and
consumes the bit for device ID 124, not bit 100. It does not itself request a
power-state transition or report current power. The 100 value is the separate
state-register index used by the clock/dependency transition path.

For clock enable, the parallel provider path selects `clock-gates[0]` and
passes device ID 124 through controller slot `+0x680`. The inherited PMGR
clock callback maintains per-device reference counts; on a transition edge,
the T7000 application path looks up ID 124's device-clock record, which maps
to PS index 100. That J81 record lists no nonzero dependent-device IDs, but
has special-action flags `0x06` and selectors 9 and 10. Apple's state change
first applies the PMGR state transition for index 100, then the clock special
action for the two bridge tables. The empty dependent-ID list does not
remove those special actions or prove other platform prerequisites are
unneeded. See `2026-11-04-j81-gpu-offline-trace.md` and
`2026-11-06-j81-clock-state-model-result.md` for the decoded record and
execution-disabled action model.

### Clock-action ordering against the hardware attempts

The original 12B410 instructions establish the enable order. After the clock
request queues its changed device state, deferred apply routine
`FUN_ffffff80031ea424` runs the two-phase loop at `0xffffff80031ea45c`–
`0xffffff80031ea56c`. When `param_3` requests enable, it selects phase 0
then phase 1. This work runs only when the per-device clock state changes;
an enable call while the state is already active does not imply the tables
are replayed. Phase 0 visits queued power-state indices and calls
`FUN_ffffff80031e7c10`; that helper writes the PMGR target and polls actual
state until it matches. For GFX, index 100 is requested at `0xf`. Phase 1
then walks the clock-action queue and calls `FUN_ffffff80031ea58c`. That
helper checks enable and flag bit 1, calls
`FUN_ffffff80031eb648(record[5])`, then, if nonzero,
`FUN_ffffff80031eb648(record[6])`. The captured GFX record supplies selector
9 then 10. `FUN_ffffff80031eb648` iterates each table's offset/value pairs and
writes them to its mapped bridge. The later flag-bit-2 branch adjusts the
SoC-busy count. Thus Apple enable order is PS index 100 to state 15 and wait,
selector 9's 33 pairs, selector 10's 33 pairs, then busy accounting. Disable
reverses the phases (action/busy phase before PS-off), but the bridge helper
does not replay selectors when `param_3` is zero.

The existing hardware runs executed only a prefix of the bridge writes,
manually; none invoked Apple's clock-state callback:

| Hardware observation | What ran | What did not run |
| --- | --- | --- |
| [First clock-state write result](2026-11-06-j81-first-clock-state-write-result.md) | PMGR already reported state 15; with GPC at 0, wrote selector 9 pair 1 (`0x201f00018 <- 0x80010004`). | No clock callback, selector 9 remainder, selector 10, GPC setup, or post-write GPC read. |
| [Selector 9 five-pair repeat](2026-11-06-j81-selector9-five-pair-repeat.md) | PMGR state 15; GPC pre-state 0; manually wrote selector 9 pairs 1–5. | No Apple clock-state callback, selector 9 pairs 6–33, selector 10, GPC post-read or setup. |
| [Guarded bridge run 02](2026-11-06-j81-guarded-test-run-02.md) | Began PMGR-off (`0x300`), used generic Linux PMGR power-on to state 15 (`0x3ff`), then manually wrote the same first five selector 9 pairs with GPC pre-state 0. | No clock reference transition or Apple queue/busy handling, remaining 61 pairs, selector 10, GPC setup or post-write GPC read. |

These runs show the first selector 9 writes are accepted after the Linux PMGR
domain is active. They do not establish the complete Apple sequence or its
effect. Separate GPC-init runs reached state 1 after generic PMGR and Fender
writes, without the full selector 9/10 action; a subsequent RGX revision read
still hung. The concrete missing bring-up step in Linux is therefore the
complete clock-state enable action (including both bridge tables and its
ordering/bookkeeping) before Fender/GPC setup, rather than simply another
`ps_gfx` genpd get. No replay is justified from the current evidence: only
five writes have been exercised and GPC/RGX readiness after the complete
action has not been established.

### Linux gap

The current Linux diagnostic uses `ps_gfx` as a generic power-domain
consumer via `of_genpd_add_device()` and runtime PM; its one-shot path keeps
the reference held, while the cycle path performs a power-domain
get/put/get sequence. That exercises the PMGR state register at
`+0x20320`, but it does not implement Apple's `AppleARMIODevice` clock
wrapper, the J81 `clock-gates[0] = 0x7c` route, AppleT7001IO's platform
function dispatch, or the T7000 callback's consumable WAS_PWRGATED result.
Consequently, reaching a powered GFX domain in Linux is not evidence that
the Apple clock/dependency setup or probe cleanup behavior has been
reproduced. The safe offline implementation boundary is the existing
`ps_gfx` generic power domain at register `0x20320`: its `power_on` sets target
state `0xf`, polls actual state for up to 100 microseconds, then enables
auto-PM; `power_off` targets state zero with no auto-PM. `of_genpd_add_device()`
does not power the domain during attachment, as confirmed by the pinned genpd
source audit. Use runtime-PM/domain references for diagnostics. Do not implement
`clock-gates = <0x7c>` as a raw PMGR bit toggle or pretend a generic domain
reference reproduces Apple's per-device reference counts, dependency walk,
clock special actions, or consumable `WAS_PWRGATED` callback. The checked-in
GPU PMGR test node is intentionally marked `experimental,j81-gpu-test-no-poweroff`;
that held-on diagnostic remains the minimal safe Linux experiment. No
hardware operation is needed to resolve this call mapping. A dedicated Linux
clock provider is not a justified minimal patch yet: it would need the two
special-action tables, per-device reference transitions, and PMGR-state
ordering, while the current GPC prerequisite/recovery behavior remains
unvalidated on hardware. The static execution-disabled model verifies table
mapping/order constraints but cannot establish that replaying the operations
is safe or that they produce a ready GPC.

Evidence for the completed mapping: `provider.c` (gate-array selection and
controller dispatch), `t7001-gates.c` (unchanged platform-function arguments),
the original controller vtable/thunk notes above, `t7000-power-gate.c`
(bitmap indexed by its device-ID argument), and the matching 12B410 PMGR
device table/`psidx` decode in `2026-11-04-j81-gpu-offline-trace.md`. The
Linux baseline is the pinned `drivers/pmdomain/apple/pmgr-pwrstate.c` copy in
`artifacts/live/private/gpu-offline/linux-src`; its generic domain callbacks
set and poll the `reg` offset but do not implement gate arrays or dependency
recursion. The extant test-node patch is `kernel/patches/0124-j81-gpu-pmgr-test-node.patch`.

The concrete runtime class conclusion needs care. The public XNU
`IOService.h` description for `IOProviderClass` says provider matching uses
`OSDynamicCast`, so the personality admits an `AppleARMIODevice` instance or
subclass; it does not prove the exact dynamic class. This documents the
remaining limit rather than weakening the statically recovered method
dispatch chain. The 12B410 device-tree child-factory and T7001IO controller
path above resolve the effective gate implementation even without an
IORegistry capture.

This resolved chain is specific to the matching iOS 8.1 (12B410) inputs and
must not be projected onto iPadOS 15.8.8. The newer-kernel inspection confirms
the `AppleARMIODevice` base slots and static `AppleT7001IO` subclass overrides,
but not the live `sgx` provider's dynamic class or the backing object's runtime
binding; see [`2026-11-08-j81-ios15-applearmiodevice-vtable-candidates.md`](2026-11-08-j81-ios15-applearmiodevice-vtable-candidates.md).

Public corroboration: [Apple XNU `IOService.h`](https://github.com/apple-oss-distributions/xnu/blob/main/iokit/IOKit/IOService.h),
which documents subclass matching for `IOProviderClass`. This is current
public API documentation, not source for the proprietary iOS 8.1 drivers.

Evidence: `artifacts/live/private/gpu-offline/kexts.json` (the matching AGX
personality), `ios81-agx-disasm.txt` / `gpc-link.c` around
`FUN_ffffff80032935a0`, and the provider assignment in
`ios81-agx-disasm.txt` around `FUN_ffffff8003299584`. The controller path is
in `t7001-start.c`, `t7001-gates.c`, `t7000-flags.c`, and the 12B410
ARMPlatform import. `pmgr-gate-slots.c` contains only comments because
Ghidra did not identify independent function boundaries for the two
tail-dispatch thunks; the raw instructions were recovered with
`PrintRange.java` and the raw vtable words were cross-checked directly.
These private disassembly artifacts are ignored local research inputs.
