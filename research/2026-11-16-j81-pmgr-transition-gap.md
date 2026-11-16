# J81 remaining gap: ApplePMGR transition versus raw replay

## Result of the post-PongoOS review

The new bare-PongoOS result changes the priority of the remaining hypotheses.
After the recovered PMGR power state, 66 bridge stores, and GPC request, a
PongoOS read of RGX `+0x20` stalled just as Linux does. This makes a
Linux-only mapping or userspace error insufficient, but it does not make the
66 stores a complete representation of Apple's clock action.

The matching 19H394 G4G probe has this exact order:

1. provider `+0x568(1, 0)` (clock action);
2. provider `+0x570(1, &out, 0)` (power action);
3. GPC `+0x10000 <- 0xffff0000`, `+0 <- 0x40000000`, and
   `+0x1000 <- 0x11`, with the stock busy poll;
4. delay and RGX identity load at `+0x20`.

The previous iOS boundary capture proves page-5 `+0x4` remains zero after
steps 1 and 2, and changes during step 3. Thus the provider actions are not
established as the writer of bit 30. They remain relevant because they are
the last unreplicated *transition owner* before the GPC request.

## What the 66-store result actually covers

The iOS writer capture proves that a GFX transition requests 33 selector-9
and 33 selector-10 bridge stores, in the same order and with the same values
as the Linux replay. Those are virtual PMGR `+0x998` bridge-writer requests.
It does not cover all work performed by the ApplePMGR transition engine.

Static 19H394 PMGR code shows the transition path also:

- derives dependent device-state changes before applying the aggregate;
- enters the PMGR device transition/settle path; and
- may issue ordinary-region writes through virtual `+0x988`, a different
  mapping family from the bridge writer.

More specifically, the inspected generic state-transition helper
`0xfffffff006bc6ed8` reads the target device word through `+0x980`, writes a
revised word through `+0x988`, updates the actual-state field through `+0x990`,
and can make further `+0x988` writes while changing control bits for a target
state of `0xf`. This is static reachability, not proof that a particular GFX
transition takes every branch, but it is enough to show why replaying only the
selector-bridge stores is incomplete.

The existing page-5 writer capture only looked for a `+0x988` request whose
effective target was ordinary region 0, offset `0x5004`, instance 0. Its
negative result does **not** say that no other ordinary PMGR write occurred
during the GFX transition. Conversely, static reachability does not prove a
particular dependency or ordinary write runs for J81 GFX.

An unmerged, locally retained follow-up also compared completed ordinary and
bridge-store effective addresses against the page-5 reader's effective
address. That was a stronger test of a CPU writer *to page 5*, but it retained
the same target restriction. It cannot identify an ordinary write to another
PMGR register made by the GFX clock action, so it is not a substitute for the
windowed all-ordinary-write capture below.

## Best next discriminator

Use a passive iPadOS capture of **all completed-entry candidates to PMGR
`+0x988` during the already-proven GFX provider window**. Record only the
method arguments needed to reconstruct the effective ordinary PMGR target:
region, offset, value, and instance. Do not add MMIO reads or writes, do not
trace the bridge `+0x998` path again, and do not make another RGX read.

The probe needs these guards:

1. exact 19H394 UUID and a unique code signature for `bd04f0` (`+0x988`);
2. a provider-window marker tied to the previously working G4G clock action;
3. bounded per-CPU-safe reservation, overflow reporting, and no device
   pointers in logs;
4. a host simulation covering outside-window calls, overflow, and duplicate
   records; and
5. a baseline boot control with the hooks installed but no captured GFX
   records required for success.

A nonempty, GFX-window ordinary write absent from the Pongo/Linux plan would
be a concrete next replay candidate. An empty capture would only rule out
this method/window; it would not exclude direct stores, another PMGR object,
firmware/autonomous activity, or a boot-stage difference.

## Minimal implementation boundary

This does not require a new interception family. The existing private
page-5-writer experiment already proves both required safe points: a
trampoline at the completed `+0x988` store instruction and a wrapper around
the G4G clock callback. Its current full binary is **not** an acceptable
baseline because it also injects five PMGR/GPC/page-5 reads and substantial
logger code. The new variant should be a reduced two-hook implementation. It
should set an atomic `in_gfx_clock` flag
immediately before that callback and clear it immediately after it returns.
The existing store trampoline should reserve at most 16 records only while
that flag is set, execute the displaced store unchanged, then publish
`region`, `offset`, `value`, and `instance`. It must not publish the PMGR
object pointer, add an MMIO operation, or retain the five earlier page-5
diagnostic reads.

The first device image should install those two hooks but leave recording
disabled, proving the reduced transport boots. Only after that baseline should
the recording flag be enabled. That separates a hook/resume failure from a
meaningful empty capture and avoids repeating the earlier entry-hook failure
mode.

## Explicitly deferred

Do not directly write page-5 bit 30, guess reset/PLL/voltage values, repeat
the RGX read, or restore broad power-domain sets. Each varies state without
separating the known missing Apple transition from unrelated boot state.

Evidence: [G4G pre-ID order](2026-11-08-j81-ios15-g4g-pre-id-clock-power.md),
[66 bridge-store comparison](2026-11-10-j81-ios-corrected-bridge-result.md),
[ordinary-writer result](2026-11-11-j81-ios-page5writer-result.md),
[entry review](2026-11-15-j81-entry-gpc-offline-review.md), and the
[bare-PongoOS stall](2026-11-16-j81-pongo-core-read-result.md).
