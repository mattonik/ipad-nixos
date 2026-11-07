# J81 core-read hang: missing Apple provider dispatch boundary

Offline follow-up to the 2026-11-07 full selector-table/GPC test. No hardware
was accessed for this analysis.

## What the latest hang establishes

`2026-11-07-j81-core-revision-after-clock-test4.md` records that PMGR reached
`0x3ff`, all 66 selector 9/10 writes completed, GPC state/control read back as
`1` / `0x40000000`, and the first read at `0x201000020` never returned. The
result rules out the simple claim that replaying both bridge tables plus the
tested GPC setup is sufficient to make the core window readable. It does not
identify the fault or establish that a further register read is safe.

The first core read is now unambiguous in the matching iOS 8.1 instructions.
G4G `FUN_ffffff80032935a0` calls its own vtable slot `+0x800` after GPC setup.
The G4G vtable at `0xffffff80032aefa0` resolves that slot to
`FUN_ffffff80032933cc` (`ident.c`); that matcher dispatches slot `+0x810`,
which resolves to `FUN_ffffff800328de68`. The latter reads RGX `+0x20` first
and `+0x18` second. Therefore the failed address is exactly Apple's first
identity-read access, not an earlier hidden read in the GPC setup. The parent
`IOService::probe` is a return-only stub, and G4G slot `+0x790` only reads the
`no-gpc` and `model-slow` properties.

## Concrete sequence still absent from the Linux reproduction

Immediately before mapping GPC and issuing its three writes, Apple's probe
calls provider `+0x560(1, 0)` then `+0x568(1, &local, 0)` on the actual
`AppleARMIODevice` provider. The original 12B410 provider vtable and
`AppleT7001IO`/PMGR dispatch chain resolve these to
`enableDeviceClock(true, index 0)` and
`enableDevicePower(true, &was_gated, index 0)`. J81's two gate arrays pass
device ID `0x7c` (124). The clock route uses PMGR state index 100 and, on a
reference-count transition, applies state 15, selectors 9 and 10, then the
SoC-busy action. The power callback consumes the `WAS_PWRGATED` history bit
for device ID 124 and reports it through the local output; it is not itself a
power-on request.

The latest Linux experiment reproduced the resulting PMGR state, the selector
writes, and GPC state/control values, but did not invoke Apple's provider
clock callback or its reference transition/SoC-busy action. Matching the
register readbacks is not evidence that those software-side steps happened.
The power-history callback is a separate case: its return code is ignored and
its out value is used only after the identity method returns and after G4G
requests GPC state 0. A nonzero out value causes conditional cleanup in this
order: provider power-off, then provider clock-off. It cannot change the
pre-read GPC writes or make the hanging identity read reachable. Therefore
the callback's consumable history value is not a candidate missing
prerequisite for the observed first core read.

Keep the identifiers distinct: selector-array index `0`, gate device ID
`0x7c`/124, PMGR power-state index `100`, and PMGR state register offset
`0x20320`. The clock special action's direct bridge writes are not equivalent
to the full provider call, and a generic PMGR get/put cycle is not equivalent
to the Apple clock reference-count edge.

## Exact callback state and test4 comparison

The 12B410 bitmap path is statically resolved. PMGR startup allocates and
zeros both its state-index-to-device-ID map and the recorded-gated bitmap.
It populates index 100 with GFX ID 124 from the J81 `device-clocks` record.
On an actual Apple transition, `FUN_ffffff80031e7c10` / the related
state-transition helper checks PMGR `WAS_PWRGATED` bit 8; when the observed
state transition is accepted, it sets bitmap bit 124. The T7000 callback at
`FUN_ffffff80031e7bbc` initializes its out parameter to 0, reports 1 only if
bitmap bit 124 was set, clears the bit either way, and returns success. Thus
the callback's out value is a one-shot software history result, not a live
register read. The static source establishes the mapping and behavior, but
cannot tell whether the bit would be set in the test4 boot.

Test4's captured PMGR order is informative: the cycle preflight read was
`0x300` (target/actual 0, with bits 8 and 9 set); the generic Linux off/on
cycle then produced `0x3ff` (target/actual 15, with bits 8 and 9 also set).
In the pinned Linux definitions, those bits are `WAS_PWRGATED` (bit 8) and
`WAS_CLKGATED` (bit 9). `apple_pmgr_ps_set()` masks both bits to zero in its
write value for each target transition, but the later raw readback has both
bits set again. The source shows the values Linux requests and the captures
show the subsequent reads; they do not establish whether zero writes clear
these status bits or when a transition may set them again. Linux also does
not maintain Apple's private software bitmap. Then test4 performed all 33
selector-9 writes, all 33 selector-10 writes, GPC state/control setup and
state-1 poll, the post-GPC bridge reads, and finally attempted the one core
read at `0x201000020`. No Apple `enableDeviceClock` or `enableDevicePower`
callback ran, and no checkpoint exposes the callback's out value. Therefore
the initial PMGR `0x300` cannot be treated as proof of Apple's later local
`was_gated` output: Linux's generic transition and raw PMGR flags do not
populate or reveal Apple's private per-device bitmap. Although test4 later
read both hardware flag bits set in `0x3ff`, that does not establish that
Apple's startup transition logic had recorded device ID 124 in its bitmap.
The test also contains
no evidence of the callback-driven conditional unwind (power-off then
clock-off) after the matcher.

The SoC-busy action is also fully conditional in the source. The GFX record
has special flags `0x06`, so enable runs selector tables (flag bit 1), then
`FUN_ffffff80031eb7c0` (flag bit 2) to increment the busy reference count.
That routine returns after accounting unless both runtime `+0x980` is nonzero
and the initialized `+0x98c` feature flag is true. Setup for `+0x98c` reads
J81 `fb-caching=1`, `mcc-config-fb-caching=4`, resolves
`function-dispidle_ctrl`, and reads `disp-fb-mcache-id=0x75`; it can still
leave the feature off if setup/overrides prevent activation. The `+0x980`
mode is the runtime enable state maintained by this same special action for
records with flag bit 3: it is set to 1 on enable and 0 on disable. The J81
`DISP0` record is the sole record with bit 3. On 0→1 busy, the routine sets
`bVar2=0` and requests the busy MCC mode (`+0x95c`); on 1→0 it sets
`bVar2=1` and requests configured `mcc-config-fb-caching` (`+0x131`, J81
value 4). It emits controller event `0x2700c001` for cache ID `0x75`, then
invokes `function-dispidle_ctrl` with that state. If that call succeeds and
the desired MCC mode differs from the last applied mode, the controller
applies it through the cached MCC function; it then updates the cache record
through its `+0x690` method. The completion/error path emits event
`0x2700c002`. This exposes what test4's direct stores omitted: the clock
reference edge, busy counter, and any enabled display coordination. The
current artifacts do not establish live `+0x980`, whether the display
callback resolves, or whether either edge ran; the omission is not evidence
that display-side work caused the RGX hang. Test4's initial `0x300` PMGR word
was overwritten by the generic cycle before selector/GPC stages, so it says
nothing about a later Apple power-history out value.

The evidence is exhausted at the static/runtime boundary: exact software
effects and guards are known, but neither test4 nor available source records
the runtime bitmap value, display mode, or provider callback result. The next
useful work is to make an execution-disabled trace model that reports these
callback effects and explicitly marks those three inputs unknown, then decide
whether reproducing Apple's per-device provider path is feasible in Linux.
There is no supported inference from this analysis that a further RGX read
or another live MMIO sequence is safe.

Evidence: `artifacts/live/private/gpu-offline/gpc-link.c` (`FUN_...32935a0`),
`ident.c` (`FUN_...32933cc`), `ios81-agx-disasm.txt` at
`0xffffff800328de68`, the vtable/provider routing documented in
`2026-11-07-j81-gpc-provider-object-binding.md`, and the test4 capture summary
in `2026-11-07-j81-core-revision-after-clock-test4.md`. Callback evidence is
in `t7000-power-gate.c`, `t7000-manual.c`, `t7000-flags.c`,
`framebuffer-cache-setup.c`, `gfx-clock-special.c`, and
`framebuffer-cache-helper.c`; test4 transaction checkpoints are in
`artifacts/live/gpu/clock-cycle-20261107-test4.log`,
`clock-table-20261107-test4.log`, `gpc-init-20261107-test4.log`,
`postgpc-bridge-20261107-test4.log`, and `core-revision-20261107-test4.log`.

## PMGR startup baseline and DISP0 record distinction

An additional static trace of the original 12B410 `AppleT7000PerformanceController::start`
constrains the startup state before G4G can use the provider. `FUN_...31e7cc8`
scans PMGR power-state indices 32 through 100 (excluding 0x45 and 0x5f),
reads each register at PMGR `+0x20000 + 8*index`, and sets the controller's
`+0x770` active-state bitmap when the actual-state nibble is 15. Startup then
calls `FUN_...31e82f4`: entries marked active are requested at state 15;
unmarked entries are requested at state 0. This is an Apple startup
reconciliation based on the hardware state it observes, before G4G's later
provider clock/power requests.

The framebuffer-cache setup `FUN_...31e8e54` runs after that reconciliation
and initializes the `+0x98c` feature flag. Therefore G4G's later GFX clock
request sees the result of setup, although the flag may remain disabled if
any setup requirement or boot-time override prevents activation.

The matching iOS 8.1 `device-clocks` table resolves a distinction relevant to
the runtime display-mode input: record ID 28, named `DISP0`, uses PMGR state
index 86 and special flags `0x0a`; its bit-3 action controls `+0x980`. The
`disp0` node's direct gate arrays are instead `clock-gates = [112, 118, 116]`
and `power-gates = [112]`. Thus ID 28 is not one of the display node's direct
gate-array entries. Its consumer/callsite is not established by this trace,
so this does not show that the display mode was set before G4G.

The test4 pre-cycle PMGR sample `0x300` shows GFX state index 100 was at 0 in
that Linux boot before its generic off/on cycle. The cycle then changed the
state before selector/GPC work, so it cannot reconstruct Apple's software
bitmap or initial SoC-busy count. No test4 sample covers state index 86 or
the DISP0 mode. In particular, whether the GFX enable creates a busy-count
0-to-1 edge remains unknown. These constraints narrow the missing runtime
inputs but do not establish that the conditional display action caused the
RGX hang.

Evidence: `t7000-flags.c` (`FUN_...31e6fc8`), `t7000-map.c`
(`FUN_...31e82f4`), `framebuffer-cache-setup.c` (`FUN_...31e8e54`), the
original 12B410 `ios81-dt.json` PMGR `device-clocks` bytes, the `disp0`
node's gate arrays in that tree, the pinned
`linux-src/drivers/pmdomain/apple/pmgr-pwrstate.c` definitions and write path,
and test4 captures `clock-cycle-20261107-test4.log` and
`core-revision-20261107-test4.log` summarized in
`2026-11-07-j81-core-revision-after-clock-test4.md`.
