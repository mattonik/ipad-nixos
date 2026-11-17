# J81 Fender bit 29: what the 2026-11-17 capture means and what to test next

Offline synthesis of the [capture result](2026-11-17-j81-fender-page5-capture-result.md)
against existing iOS evidence. No new hardware access.

## Facts

- Linux (this capture): after the known GPC sequence and poll success,
  Fender +0 = 0x40000000, +0x8 = 0, +0x1000 = 1, +0x20000 = 0, PMGR page-5 +0x4 = 0.
- iOS 15.8.5 planned-panic series: page-5 +0x4 is 0 after AGX clock/power
  callbacks and after the stock GPC 0x40000000 store, and 0x40000000 after the
  stock 0x11 request and busy poll
  ([result](2026-11-16-j81-agx-postpower-page5-result.md)).
- Decompiled iOS 8.1 (A8X-native) and 15.8.5 GPC code: the only software stores
  to Fender are +0x10000 = 0xffff0000, +0 = 0x40000000, +0x1000 = 0x11
  (later 0x10) and +0x20000 = 0x20/0. Nothing stores bit 29 to +0. The ready
  guard (iOS 8.1 `FUN_ffffff80032a1e80`, gpc.c) requires `(+0 & 0x60000000) ==
  0x60000000`, then waits for +0x1000 bit 4 to clear, then requires +0x8 == 0
  (source: `artifacts/live/private/gpu-offline/gpc.c`, `ios81-gpc-helpers.c`).
- iOS 8.1 issues provider calls `+0x560(1,0)` and `+0x568(1,&x,0)` immediately
  before the GPC writes (gpc-link.c), i.e. clock and power requests precede them.

## Interpretation

1. Fender +0 bit 30 reading 1 is our own write read back. It carries no
   hardware information. Bit 29 is never written by software in either iOS
   version, so it is hardware-produced.
2. Page-5 bit 30 is likewise hardware-produced and appears in iOS only after
   the 0x11 request completes. Linux and the bare-PongoOS replay perform the
   same writes, reach state 1, and see neither bit. So the GPC/Fender block
   completes its state transition without its ready response; the missing input
   is upstream of these registers, not a value Linux must write.
3. Guard conditions +0x1000 state and +0x8 == 0 are already satisfied in
   Linux; bit 29 (and page-5 bit 30) are the only unmet conditions seen.
4. The +0x20000 handshake runs only after the guard passes, so it cannot be
   the cause.

## Next steps, in order of cost

1. (Offline, cheap) Decompile what iOS 15.8.5 does between its provider
   clock/power calls and the GPC writes, and compare with the Linux PMGR/bridge
   replay for any gate or domain that Linux does not request (the gate index
   passed to the +0x560/+0x568 calls is the lead).
2. (iPad, uses the existing planned-panic transport) Capture Fender +0 and +0x8
   on iOS at the post-poll boundary. Each probe returns one word, so one boot
   per register. This turns "bit 29 is hardware-produced" into a measured fact
   and shows whether iOS has bit 29 at that moment or only later.
3. Do not write bit 29 or page-5 bit 30; no evidence supports it.

Limit: the decompiled files above were read only for the stores and the guard;
the gate indices in step 1 were not decoded in this pass.

## Follow-up (same day): the gate-index lead is already decoded

Existing notes cover the provider clock/power calls end to end, so no new
decoding was needed:
- `clock-gates[0]` and `power-gates[0]` are device ID 124 (0x7c)
  ([clock-enable effects](2026-11-07-j81-g4g-clock-enable-register-effects.md)).
  On an enable edge, ID 124 maps to PMGR state index 100: request state 15 at
  0x20e020320 and poll, apply bridge selectors 9 and 10 (the 66 bridge
  stores at 0x201f00000 / 0x201f80000), then the SoC-busy helper (conditional
  display/MCC callback, see
  [SoC-busy action](2026-11-07-j81-soc-busy-display-action-before-rgx.md)).
- The Linux replay covers the PMGR state request and the 66 bridge stores.
  What it does not show it covers is ApplePMGR's full transition/dependency
  path and the conditional SoC-busy/MCC callback. `gpu-status.md` and
  [PMGR transition gap](2026-11-16-j81-pmgr-transition-gap.md) already name the
  same remaining gap and the next discriminator: a passive ordinary-PMGR
  writer capture during the working iOS GFX window.

Conclusion: the new capture sharpens the symptom (bit 29 and page-5 bit 30 are
hardware responses that never arrive) but does not move the suspect away from
the gap those notes already identify. The useful next work is that PMGR
writer capture, not another Fender or GPC read, and not a bit-29 write.
