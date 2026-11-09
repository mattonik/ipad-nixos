# J81 pre-ID readiness sequence audit

Date: 2026-11-09. Offline comparison of the original iOS 8.1 AArch64
disassembly, current GPU notes, and Linux test4 captures. No device access.

## Result

The source-supported Apple sequence after the GFX PMGR state request has no
additional pre-ID GPC hold/reset routine. G4G requests provider clock-on and
power-on for gate ID `0x7c`, performs Fender/GPC setup, optionally polls state
bit 4 clear, delays 10 microseconds, and then dispatches the identity read.
The first read is RGX `+0x20` (`0x201000020`); `+0x18` follows only if that
read returns. Apple requests GPC state zero only after the matcher returns.

For the confirmed J81 GFX clock-change path, the lower PMGR sequence is PS
index 100 to state 15 with an actual-state wait, selector 9's 33 bridge pairs,
selector 10's 33 pairs, then the conditional SoC-busy bookkeeping/callback.
Linux test4 reached PMGR `0x3ff`, issued those 66 bridge stores, brought GPC
to state 1/control `0x40000000`, and then stalled at the first RGX read. The
only source-backed sequence difference before that read is Apple's provider
clock/power callbacks and their software-side state; test4 used generic genpd
and manual bridge/GPC helpers. This does not establish that any callback was
missing at runtime or that reproducing one would make RGX readable.

## Disassembly checks

In `ios81-agx-disasm.txt` at `0xffffff80032935a0`:

- Provider `+0x560(1, 0)` and `+0x568(1, &local, 0)` run before GPC mapping.
  Their return codes are not tested before the identity call. The output word
  is initialized to zero and only consulted after identity and GPC state-zero
  cleanup to select optional power-off then clock-off.
- The GPC writes are, in order, `+0x10000 = 0xffff0000`, `+0 = 0x40000000`,
  and `+0x1000 = 0x11`. If the poll flag is set, Apple repeatedly reads
  `+0x1000` until bit 4 clears. It then calls `IODelay(10)` before the
  accelerator `+0x800` identity method.
- The proven accelerator vtable sends `+0x800` to `0xffffff80032933cc`,
  which dispatches `+0x810` to `0xffffff800328de68`. That method loads
  mapped RGX `+0x20`, then `+0x18`. There is no intervening hold/reset method.
- `0xffffff800329eb28` does assert GPC hold and transition to state zero, but
  it belongs to a separate firmware-object vtable. The recovered early
  accelerator `+0x800` entry is not this function, and no call edge places
  `329eb28` before the first ID read.

The 10-microsecond delay is a concrete sequence difference from test4's
host-mediated phases, but the captures do not provide a timestamp for the
core-read attempt sufficient to prove that test4 violated this delay. It is
not a supported explanation for the hang. Likewise, the early G4G `+0x790`
property hook is not a clock selector: its resolved target reads `no-gpc` and
`model-slow` properties and sets flags.

## Clock-selection boundary

Static 12B410 dispatch resolves G4G's provider calls through
`AppleARMIODevice`/`AppleT7001IO` to the T7000 performance controller. The
clock callback maintains per-device reference state; on an enable edge it
requests PMGR state index 100 at 15 and applies selectors 9/10. The power
callback consumes a saved `WAS_PWRGATED` indication; it is not a raw power
toggle. Those callback side effects and the conditional display/MCC busy edge
are not represented by Linux test4. The available source does not reveal a
separate pre-ID numeric GPU clock-frequency choice, nor a GPC readiness test
beyond the optional state-bit poll and delay.

## Decision and limits

No new concrete safe hardware sequence follows. The candidate firmware hold
sequence is not on the proven pre-ID call path; the complete Apple provider
callback path remains the material source-level difference, but its hardware
effects are not a justified replay until separately bounded. No clock rate,
RGX-ready predicate, or reason for the stalled transaction is established.

Evidence: ignored local `artifacts/live/private/gpu-offline/ios81-agx-disasm.txt`
at `32935a0`, `32933cc`, `328de68`, and `329eb28`; notes
`2026-11-07-j81-gpc-provider-object-binding.md`,
`2026-11-07-j81-pre-id-provider-return-gate.md`,
`2026-11-07-j81-gpc-hold-before-id-boundary.md`, and
`2026-11-07-j81-test4-raw-readback-boundary.md`; saved test4 transcript
`artifacts/live/gpu/clock-table-20261107-test4.log` and
`core-revision-20261107-test4.log`.
