# J81 iOS 8.1 display/MCC effects before the first GPU ID read

Offline source trace of the original 12B410 kernelcache, matched J81 ADT, and
saved Linux test4 transcript. No device, MMIO, or build was used.

## Code order

In G4G's `FUN_ffffff80032935a0`, the iOS provider clock request for ID `0x7c`
(124) precedes GPC setup and the identity matcher. For an actual PMGR clock
transition edge, the ID-124 record has flags `0x06`: Apple requests PMGR state
15 for state index 100, applies selector 9's 33 stores then selector 10's 33
stores, and calls the SoC-busy helper. The helper increments its in-memory
count. It calls the display/MCC path only when feature `+0x980` and byte
`+0x98c` are enabled, the count crosses 0↔1, and callback object `+0x990`
exists. It passes code `0x2700c001` to PMGR vtable `+0x740`, calls display
callback vtable `+0x78`, and only on callback success may apply an MCC mode.
The iOS 8.1 slot is unresolved; that code is likely a trace marker, a strong
inference from the iOS 15 helper, call shape, and constants, not proof. The helper completes and
G4G continues into GPC setup; the first GPU ID access is the 32-bit read at
`0x201000020`.

J81 configures `fb-caching=1`, `mcc-config-fb-caching=4`, display cache ID
`0x75`, and `function-dispidle_ctrl` to `disp0`. On a last-busy release
(count 1→0), the helper passes boolean `true`; after successful callback
return, it requests mode 4 if that differs from cached mode. The MCC function
object dispatches numeric selector 4. In the 12B410 MCC controller, selector
4 reads mapped `+0x830` and writes:

```
+0x830 = 0x55 | (old & 0xffffffe0)
+0x830 = (new & 0xfffffeff) | 0x100
```

These are the exact instruction-derived stores. Their semantic bit meanings
are unknown. The function-object wrapper discards the selector's return code
and returns success, so PMGR's cached mode can advance even if the MCC
controller's startup-state guard prevented those stores. The boot argument
`-disable_mcc` can leave that initialization marker clear; its test4 value is
unknown.

The display-idle callback is not a synchronous hardware completion. Its 8.1
`AppleDisplayPipeSetSystemIdleStateFunction::callFunction` checks its object
and readiness, then calls `thread_call_enter1` with the boolean. Zero means
the work was queued successfully. The queued worker later checks readiness
and state-change conditions, may publish `MemCacheState` (true→1, false→2),
and dispatches into `IOMobileGraphicsFamily`. The traced functions show no
direct MMIO there, and the worker's eventual controller effects are
unresolved. Therefore the MCC selector stores occur synchronously after
callback queue acceptance when its gates pass, but queued display work may
finish either before or after `0x201000020` is attempted.

## DISP0 setup stores and ordering uncertainty

AppleMobileADBE0 startup requests display clock gate ID 112. In the J81 PMGR
table, ID 112 depends on record ID 28 (DISP0), whose separate bit-3 action
sets provider field `+0x980` and updates mapped PMGR offsets `+0x20290` and
`+0x20298`. On enable, each is a read-modify-write equivalent to
`(old & 0xfff0ffff) | 0x00040000`; on disable, each is `old & 0xfff0ffff`.
The handler then calls the MCC helper. These offsets are PMGR-relative, not
MCC-relative. ID 124's `0x06` record does not itself select this bit-3 action.

The source establishes that display startup requests ID 112 and that a
completed ID-112 edge dispatches ID 28. It does not establish that edge ran
before G4G's ID-124 busy edge: the two services' start order and live
reference-count transitions are absent from the saved artifacts. The
`+0x980`, `+0x98c`, callback outcome, MCC initialization marker, and MCC
register values were not captured in test4.

## Relationship to the planned/saved single read

The one-shot GPU-ID probe reads GPC state and control first, then waits for a
host `READ` token before reading `0x201000020`; it has no display/MCC callback
or MCC register read. The saved test4 run stopped after emitting the
before-read marker for that address, without an after-read checkpoint. Its
Linux bridge-table checkpoints show the selector stores were replayed, but
do not show Apple's busy bookkeeping, display callback, MCC selector, or
ID-112 dependency edge. Thus the callback chain is statically ordered before
the GPU read in Apple's G4G path when its gates are taken, but its runtime
execution and hardware effects cannot be attributed to test4. A single MCC
read would only provide a raw value and cannot prove that selector 4 ran.

The exact selector-4 signature, limitations of a lone read, and hardware
read-safety boundary are documented in
`2026-11-07-j81-mcc-mode4-read-interpretation.md`; the provider/dependency and
callback disassembly evidence is in
`2026-11-07-j81-soc-busy-display-action-before-rgx.md` and
`2026-11-07-j81-disp0-record-consumer-trace.md`. No additional hardware
sequence or register read is justified by this static trace.
