# J81 iOS 8.1 DISP0 record consumer trace

Offline static follow-up to `2026-11-07-j81-core-read-missing-apple-dispatch.md`.
No device or hardware was accessed.

## Exact iOS 8.1 display provider recovered

The original 12B410 `kernelcache` is present at
`artifacts/live/private/gpu-offline/kernelcache`. Its `__PRELINK_TEXT` has VM
base `0xffffff8002593000` and file offset `5,414,912`. The prelink info entry
for `AppleH7GADBE0` gives executable load address `0xffffff80032c9000` and
executable size `0x28000`. The embedded image was therefore carved at file
offset `19,267,584` (`5,414,912 + (0x32c9000 - 0x2593000)`) for `0x28000`
bytes and identified by `otool -l` as an arm64 Mach-O with `__TEXT` and
`__DATA` segments. This independently confirms the split noted in the prior
research.

The image contains the class `AppleMobileADBE0`, matching the prelink
personality `IOClass=AppleMobileADBE0`, `IOProviderClass=AppleARMIODevice`,
and `IONameMatch=adbe0,t7000` / `adbe0,t7001`. Its embedded method-name strings
include:

* `AppleMobileADBE0::start_hardware(IOService *)`
* `AppleMobileADBE0::do_power_state_change_gated()`
* `AppleMobileADBE0::updateDisplayIsIdleToPowerGateADP_gated()`

The latter two names make this kext the strongest concrete consumer candidate
for the display-idle / display power-gating policy associated with the `disp0`
node. It is a meaningful narrowing from the prior state, where the consumer
for `DISP0` was entirely unknown.

## What is and is not resolved

The source tree's `device-clocks` record 28 remains the unique `DISP0` record
with flag bit 3; its PMGR state index is 86. Its bit-3 handler sets PMGR
provider field `+0x980`, as documented in the prior report. The display
controller's `disp0` service is a separate entity from the `DISP0` clock
record: its direct clock gate IDs are 112, 118, and 116, with power gate 112.

The display-idle callback itself is now resolved from code and its vtable. The
`AppleDisplayPipeSetSystemIdleStateFunction` constructor
(`FUN_ffffff80032ce0f4`) installs instance vptr `0xffffff80032e7da0`; slot
`+0x78` (`0xffffff80032e7e18`) points to `FUN_ffffff80032ce13c`, its
`callFunction`. That method passes the boolean to its parent pipe's
`FUN_ffffff80032cc914`, which schedules `thread_call_enter1` using the pipe's
`+0x8e8` thread-call object. This callback is asynchronous display-idle
coordination; it does not directly request PMGR clock ID 28.

The transitive record path is nevertheless established. `AppleMobileADBE0`
reads the `disp0` provider's `clock-gates` array `[112, 118, 116]` and invokes
provider vtable slot `+0x560` with gate-array indexes 0, 1, and 2 at its
clock-on/off callsites. The iOS 8.1 PMGR `device-clocks` table maps ID 112 to
record `DISP0-V`; its record's first dependency byte at offset `+8` is ID 28.
The T7000 transition routine `FUN_ffffff80031ea140` walks the record's
four-byte dependency list at `record+8` and dispatches each nonzero ID and the
requested state through its internal `+0x690` method. Thus enabling
AppleMobileADBE0 gate-array index 0 (ID 112 / `DISP0-V`) requests the dependent
`DISP0` record ID 28, whose bit-3 action sets provider `+0x980`.

The exact live path is conditional on the ID-112 transition edge and its
provider callback being reached. Static evidence establishes the dependency
and dispatch, but does not establish that index 0 was enabled in test4 or
whether its edge occurred before G4G's busy transition. Apple H7's other
`+0x560` calls observed here use direct indexes 0–2; none supplies literal 28.

## iOS 8.1 display startup callsite and ordering boundary

The split 12B410 `AppleH7GADBE0` image was imported into Ghidra as AArch64
using its prelink load address `0xffffff80032c9000`. The string reference for
`virtual bool AppleMobileADBE0::start_hardware(IOService *)` is inside
`FUN_ffffff80032d5c3c`. Its normal (non-FPGA) branch enters
`FUN_ffffff80032d6540`; the alternate FPGA branch enters
`FUN_ffffff80032d6050`. Both helpers make the same provider requests on the
`AppleARMIODevice` provider stored at `this+0x750`:

1. Call display driver's own slot `+0x910` with state 1.
2. Call provider slot `+0x560(1, 0)` and `+0x568(1, 0, 0)`.
3. Invoke the parent `AppleDisplayPipe::start_hardware` implementation via
   `PTR_FUN_ffffff80032e91b0`.
4. Continue display setup if the parent start succeeds.

For the matched J81 `disp0` node, its `clock-gates[0]` is ID 112, so the
provider clock request in step 2 selects that entry. This is the concrete
startup callsite behind the earlier provider-array trace. A separate runtime
power-up path `FUN_ffffff80032d74ac` also requests provider `+0x560(1,0)`;
power-down `FUN_ffffff80032d784c` requests state 0. The method body therefore
supports that display startup requests ID112 before the parent display-pipe
startup finishes; it does not establish when that gate's PMGR dependency
handler runs on a particular boot, because transition/reference state is
runtime-dependent.

There is no static call-order edge from this display service's
`start_hardware` to G4G's `FUN_ffffff80032935a0` probe. The latter requests
GFX ID124 later in its own execution, before GPC setup and the first RGX read,
but the available images, J81 ADT, and saved Linux test4 logs do not order the
two services' startup callbacks against each other. Thus the strongest
source-grounded statement is: iOS 8.1 display startup requests gate-array
index 0 / ID112 in its `start_hardware` path, and a completed ID112 transition
would dispatch its ID28 dependency; the relative runtime time of ID112 and
GFX ID124, and whether ID112 actually transitioned before GFX's busy edge,
remain unknown. Do not promote the order of the code paths into a boot-time
ordering claim.

The J81 ADT confirms the configuration side (disp0 gate list `[112,118,116]`,
ID112 record `DISP0-V`, dependency byte ID28, and ID28's DISP0 flag), not
execution. The Nov. 7 test4 capture is a Linux run: it contains PMGR/GFX
checkpoints, no AppleMobileADBE0 startup or callback trace, and no ID112
transition observation. The separate Nov. 7 control-boot inventory reports
simpledrm/simple-framebuffer and no native DCP/KMS service; it is not an
iOS display startup log. Consequently neither artifact supplies a runtime
timestamp or state for ID112. Static import/decompilation establishes code
and configured path; runtime ordering and branch reachability are inference
only and remain unresolved.

Method evidence: Ghidra string xrefs and decompilation of
`FUN_ffffff80032d5c3c`, `FUN_ffffff80032d6050`, `FUN_ffffff80032d6540`,
`FUN_ffffff80032d74ac`, and `FUN_ffffff80032d784c` from
`/tmp/AppleH7GADBE0-12B410.raw`; the corresponding raw image was carved from
the saved 12B410 kernelcache using the prelink `AppleH7GADBE0` load address.
The private carved file and temporary Ghidra project are analysis artifacts,
not committed evidence. J81 configuration and PMGR mechanics are in
`ios81-dt.json`, `t7000-clock.c`, and the evidence above.

## Saved PMGR words and what they can tell us offline

The available captures still do not close the ID-112-before-GFX ordering
question. The Nov. 7 test4 clock-table transcript samples the GFX state word
at `0x20e020320` (PS index 15) as `0x000003ff` (target=15, actual=15). A
separate clock-cycle transcript later reads the same word as `0x00000300`
(target=0, actual=0) immediately before its controlled cycle; the log records
the cycle return code but no post-cycle read. Neither transcript nor the
read-only control-boot inventory samples the display word at
`0x20e0202b0` (PS index 86). These are GFX power observations, not DISP0 state
or Apple display-service ordering.

There is one older, relevant point-in-time sample: the Oct. 11 read-only
`uartpeek pmgr` capture records PS index `0x56` as `0x1f0002ff`. Given the
iOS 8.1 table mapping, `0x56` is DISP0's PMGR state index 86 (the unrelated
UART6 device-clock row maps to PS index 58). The Linux Apple PMGR driver in
`artifacts/live/private/gpu-offline/linux-src/drivers/pmdomain/apple/pmgr-pwrstate.c`
defines target as bits 3:0, actual as bits 7:4, auto-enable as bit 28, and
reset as bit 31. Thus the old word says PS86 had target=15, actual=15,
auto-enable=1, reset=0 at that instant. It is consistent with DISP0 being
active on that earlier boot, but it does not show that Apple gate ID112 had
transitioned in test4, that the software `+0x980` mode was set, or that the
display was active before the test4 GFX edge.

For offline follow-up, inspect the saved capture at
`research/2026-10-11-uart3-register-capture.md` (table row PS index `0x56`)
alongside `boot/uartpeek.c`, which prints the raw `0x50..0x59` PMGR words. No
new diagnostic or device read is needed to characterize the stored sample.
The Nov. 7 `sysfs_display_controller.txt` value `runtime_status=unsupported`
and `runtime_usage=0` is Linux runtime-PM bookkeeping, not a PMGR raw-word
readback. Linux's `apple-pmgr-pwrstate` driver maps a per-node `reg` and uses
the generic PM domain/reset callbacks; it does not publish PS86's raw word
through sysfs, and the Linux display path remains only simplefb/simpledrm.
The exact Linux mapping and its limits are separately recorded in
`2026-11-07-j81-disp0-ps86-linux-boundary.md` and
`2026-11-07-j81-disp0-linux-gate-observation.md`.

## Does IOKit require DISP0 before the AGX probe?

The 12B387 prelink metadata does not declare such an ordering. `AppleH7GADBE0`
matches `adbe0,t7000` as an `AppleARMIODevice` child; the AGX accelerator
personality matches `gpu,t7000` / `sgx,t7000` as another `AppleARMIODevice`
child. Those match separate J81 DT nodes (`disp0` and `sgx`), so sharing the
provider class does not create a parent-child order between their starts.
`AGXFirmwareKextG4G` has a separate personality matching `IOResources`.
Kext dependency metadata is also one-way: AppleH7GADBE0 links
IOMobileGraphicsFamily, while AGX's listed library dependencies do not include
AppleH7GADBE0 or IOMobileGraphicsFamily. These declarations provide no
`disp0`-before-AGX ordering edge.

The PMGR `function-dispidle_ctrl` reference to `disp0` connects the conditional
GFX busy/cache policy to the display callback once the function resolves; it
is not an AGX personality match and the source traced here does not make G4G
probe wait for `AppleMobileADBE0::start_hardware`. The AGX image contains the
string `AGXFirmwareKextG4G`, but the inspected string reference is in data and
does not establish a display-service dependency. The scan found no explicit
framebuffer or `waitForService` string in that image; this is only a bounded
string check, not proof that no indirect lookup exists.

Therefore the supported conclusion is limited: display startup's own source
requests ID112 before it completes its parent display-pipe start, and G4G's
probe requests GFX ID124 before GPC setup, but neither the available IOKit
matching/dependency declarations nor the examined call paths require ID112
startup/transition to precede the AGX probe. A boot-time order could still
arise from untraced service publication, notification, or boot scheduling;
the saved test4 and control-boot captures do not contain an iOS service-start
timeline to establish it.

## Evidence boundary

This closes the static consumer path through the display provider's direct
gate array and the PMGR record dependency. It does not show runtime reference
counts, test4's ID-112 transition, or the value of `+0x980` before GFX clock-on.
Do not infer that this display coordination was active in test4 or change the
Linux MMIO sequence based on static dependency alone.

Evidence files: `artifacts/live/private/gpu-offline/kernelcache`,
`artifacts/live/private/gpu-offline/ios81-dt.json`, and the extracted image
`/tmp/AppleH7GADBE0-12B410.raw` (temporary analysis file, not committed).
Additional code evidence: `artifacts/live/private/gpu-offline/t7000-clock.c`
(`FUN_ffffff80031ea140`) and Ghidra decompilation of the AppleH7GADBE0 callback
vtable and all `+0x560` provider callsites.
