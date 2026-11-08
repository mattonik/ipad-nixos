# J81 iOS 15: `bd6328` is a PMGR counter read; GFX is in the SoC-tuner device set 0

Date: 2026-11-08. Offline disassembly of the iPadOS 15.8.8 (19H422) J81
kernelcache (`ios15-ApplePMGR.raw` and the `AppleT7000SOCTuner` kext cut
from `ios15-kernel`), plus the private Pongo ADT capture
(`gpu-observations/20261106T060741Z-pongo-adt.adt`, kept out of Git). No
device access. Follows `2026-11-08-j81-ios15-bcc56c-timing-accounting.md`.

## 1. `bd6328` only reads PMGR registers

`bcc56c`'s optional branch runs `0x...bd6328(pmgr, selector, args)` under
the PMGR command gate with selector 1. `bd6328` uses `args[0]` to index
`pmgr+0x34080`, which gives an entry in a 32-byte table at `pmgr+0x34038`,
then dispatches on selectors 1–5 through a jump table.

Selector 1 bounds-checks `args[2]` against the entry, then calls
`0x...be4488`. That helper makes two 64-bit loads through `0x...bcf7f0`
(bounds check, then `ldr x0, [map+off]`) from PMGR register block 7, at
offsets `n*16` and `n*16 + 8`. It packs them into a value plus two flag bits,
stores the result to the caller's block, and returns.

Selector 1 has no register store. The other selectors use `be4354`/`be43e8`,
`be4438` and `be4544` (`be4544` is a multi-word bit-field read through vtable
`+0x980`). `bcc56c` does not use them. The `bcc56c` path therefore reads a
PMGR counter and changes no hardware state.

The ADT's PMGR `energy-counters` list has these entries: Rest of SoC, VENC,
VDEC, ISP, CPU0–2, SoC Base, SoC and CPU. None is GFX. No property named
`state-config` appears in the capture. Together, these suggest that GFX has
no counter record on this path, but the capture does not prove it.

**Conclusion:** the GFX power-up path in `bd81a8` contains no unclassified
hardware write.

## 2. The iOS 15 form of the display/MCC busy callback

iOS 8.1 runs a display-idle/MCC callback on a GFX busy edge when framebuffer
caching is enabled (`2026-11-07-j81-soc-busy-display-action-before-rgx.md`).
In iOS 15 the same pieces form a separate driver:

- `com.apple.driver.AppleT7000SOCTuner` (class `AppleSOCTuner`, about
  4.5 KB of code at `0xfffffff006cd8000`) matches `soc-tuner,t7000` on
  `ApplePMGRNub`, so it binds on J81.
- J81's `soc-tuner` node has `soc-tuning = 1`, `fb-caching = 1`,
  `mcc-configs = 1,2,3,4`, `function-mcc_ctrl` and `function-dispidle_ctrl`.
  It also has four device sets (decoded through the PMGR `devices` table):

| Set | Devices |
|---|---|
| 0 | MEDIA (`0x12`), ISP (`0x18`), DISP1 (`0x1d`), DISP-FB-ACTIVE (`0x74`), **GFX (`0x7c`)** |
| 1 | CPU-BUSY (`0x6d`) |
| 2 | DISP0 (`0x1c`) |
| 3 | MCA0–MCA4 (`0x40`–`0x44`) |

- `AppleSOCTuner::start` reads `soc-tuning`, `fb-caching`,
  `mcc-power-gating`, `dcs-power-gating`, `soc-tuner-debug`, `devices`,
  `#device-sets`, `mcc-configs` and the two `function-*` properties. It
  requires `_mccCtrlFunction` and `_dispIdleCtrlFunction`.
- The tuner only carries out requests. Its methods call
  `_mccCtrlFunction->callFunction` with command 1 plus `mcc-configs[i]`
  (`0x...cd8bfc`, which also updates an IOReport state), command 2 plus a
  value (`cd8c70`) and command 3 (`cd8cbc`). They also call
  `_dispIdleCtrlFunction` (`cd8d08`). Its `callPlatformFunction` dispatcher
  (`cd8adc`) sends four platform-function symbols to vtable slots
  `+0x550`–`+0x568`.
- `ApplePMGRNub` reads `#device-sets` and each `device-set-%d` at
  `0x...be245c`–`be24f8`, and is the source of the busy states. The policy
  itself is in the tuner (section 3).

So on iOS 15, GFX busy is one of five inputs to device set 0. When that set's
busy state changes, PMGR can tell the SoC tuner to switch the MCC config and
display idle. Linux test4 did none of this. This is the one Apple mechanism
left that both ties GFX to the MCC and is missing from test4. Section 3
shows what it does.

## 3. The tuner's policy (`0x...cd827c`)

A follow-up trace corrects one claim in section 2: the policy lives in the
tuner itself, not on the PMGR side. Its tuner-specific methods
(`cd8bfc`/`cd8c70`/`cd8cbc`/`cd8d08`) are called directly from one update
routine, `cd827c(this, sets)`. That routine prints "New display state",
"New MCC config" and "MCC config: %u -> %u". `sets` is a four-word array.
Taking word *n* to be the busy state of device set *n* (an inference from
the layout):

| Display (set 2, DISP0) | Set 0 or set 1 busy | Set 3 (MCA audio) busy | MCC config index | `mcc-configs` value | Display idle |
|---|---|---|---|---|---|
| on | yes | — | 2 | 3 | off |
| on | no | — | 3 | 4 (fb-caching) | on |
| off | — | yes | 1 | 2 | — |
| off | — | no | 0 | 1 | — |

The values match the iOS 8.1 names `mcc-config-disp-off-audio-on = 2` and
`mcc-config-fb-caching = 4`. When the display-on state changes, the routine
also calls a per-set method for every device set (`cd8b94`).

**What this means for GFX:** with the display on, GFX (in set 0) becoming
busy moves the MCC *out of* framebuffer-caching mode (4) into config 3, and
turns display idle off. This is a memory-controller performance policy. The
GPU does not need it to be reachable. A Linux boot that never put the MCC
into fb-caching mode has nothing to undo. The earlier single read
`0x200000830 = 0` does not tell us which config the MCC is in. This makes it
unlikely, though not ruled out, that the tuner explains why the RGX
register read hangs.

## Not established

- The PMGR code that turns a device-set busy change into a tuner call, and
  whether it runs before G4G's first ID read on iOS 15. G4G's clock enable
  goes through the generic state path (`bd7a1c` → `bd7ad0` → `bd81a8`), and
  nothing on that path calls the tuner. The busy accounting may come from a
  separate busy/idle report.
- What each `mcc-configs` value means in MCC registers. The `mcc_ctrl`
  target is the PMGR function `Mem$` (the ADT's `function-mcc_ctrl`
  selector), which is not decoded here.

## Next offline step

Lower priority now. Section 3 shows the tuner only changes MCC performance
mode. A stronger lead is state that iBoot leaves behind for GFX or RGX.
Another is what G4G does between its power enable and the ID read: the GPC
`0x40000000`/`0x11` writes, the bit-4 poll and the 10 µs delay, which test4's
GPC state 1 only partly covers. Only
an MCC register sequence that this produces, and that test4 lacked, would
justify a new hardware test. The stop rules in
`2026-11-08-j81-next-mcc-experiment-decision.md` still apply.
