# J81 iOS 8.1 MCC configuration stride and startup order

Offline disassembly of the original 12B410 kernelcache. No hardware or live
MMIO was accessed.

## Finding

The earlier 5 x 44-byte grouping of J81 `mcc.config-data` is not the grouping
used by the iOS 8.1 MCC consumer. `AppleS5L8960XMemCacheController::start`
computes the configuration count as `config-data length / 20`; the selector
routine uses a 20-byte stride. The 220-byte property therefore has eleven
20-byte records for this code path. Selector index 4 reads the five words at
byte offsets 80–99:

```
[0x55, 0x11, 0x10, 0x00, 0x95f]
```

This supersedes the prior interpretation that mode 4 selects the final
44-byte tuple. It does not establish names or hardware meanings for these
five fields.

## Instruction evidence

The original 12B410 `AppleS5L8960X` image is embedded in
`artifacts/live/private/gpu-offline/kernelcache`. Prelink metadata gives load
address `0xffffff8002e52000`; with `__PRELINK_TEXT` file offset `0x52a000`
and VM base `0xffffff8002593000`, its carve begins at file offset
14,585,856. `otool -tvV` on that carved arm64 Mach-O shows:

* `start`, `0xffffff8002e53400`, gets `config-data`; a virtual call at
  `0x2e53568` supplies its length, which is multiplied by `0xcccccccd` and
  shifted right 36 (`0x2e53570`–`0x2e53584`), implementing division by 20.
  It stores that count at `self+0xb0` and the data pointer returned by the
  object's `+0xd0` method at `self+0xa8` (`0x2e53588`–`0x2e53598`).
* After PRAM setup, `start` reads `-disable_mcc`. If the flag is clear, it
  calls `FUN_ffffff8002e53924(self, 1)` (`0x2e53744`–`0x2e53754`). Here
  argument 1 is the enable/disable selector: zero takes the disable arm at
  `0x2e53b08`; nonzero takes the enable arm. The enable arm reads the first
  record at `self+0xa8`, uses its fields at offsets 0, 4, 8, 12 and 16, and
  calls `FUN_ffffff8002e54128` (`0x2e53950`–`0x2e53af8`). It then sets
  `self+0xb8` to 1. Timer creation/setup follows this call.
* The separately invoked numeric selector at
  `FUN_ffffff8002e54300` compares the requested index with the count at
  `self+0xb0` and accesses `self+0xa8 + index*0x14` (`0x2e54308`–
  `0x2e54368`). For index 4 this is byte offset 80, confirming the five-word
  record above.
* Startup enable also writes directly from record 0 before calling the helper:
  `+0x850=0x1110`, `+0x838=word[2] | word[3]<<24`, `+0x83c=(old &
  0xfffffc00) | word[4]`, then replaces the low five bits at `+0x830` with
  word[0] and sets/clears bit 8 there from word[1]. It sets bit 0 at `+0x800`.
  For record 0 `[0x10,0,0x95f,1,10]`, those values yield `+0x838=0x0100095f`
  and low ten bits `+0x83c=10`; current upper bits are preserved. The helper
  `FUN_ffffff8002e54128` then does serialized writes through mapped base
  `self+0x98`: `+0x10 |= 0x101`, `+0x800=(old & 0xffffff0f)|0x90`,
  `+0x83c |= 0x8000`, `+0x854=0x020028b1`, `+0x870 |= 0x80000000`,
  `+0x884=0x2030`, `+0x888=+0x88c=0x80c`, zeroes at offsets `0x1000`
  through `0xe000` in 0x1000 steps, then stores `0x66`, `0x61`, and `0x60`
  at `+0xd000`, `+0xe000`, and `+0xf000`. These are instruction-derived
  effects; register meanings are unknown.
  When startup reaches this enable arm, it initializes `+0x830` bits 4:0 to
  `0x10` and clears bit 8 before marking `self+0xb8` initialized. That is
  intended software initialization only; whether this start path ran, and the
  live register's initial value, are not observed for test4.

### Numeric selector 4's exact runtime body

The original 12B410 controller function `FUN_ffffff8002e54300(self, index)`
is the numeric selector. For a valid index it first returns
`0xe00002d8` when startup state `self+0xb8` is zero. Otherwise it loads
word 0 from `self+0xa8 + index*0x14`, reads mapped `+0x830`, and writes
`word[0] | (old & 0xffffffe0)`. It then reads `+0x830` again and writes
`(old & 0xfffffeff) | (word[1] != 0 ? 0x100 : 0)`. This routine does not
call the startup helper and consumes no words 2–4. Thus selector 4's record
`[0x55,0x11,0x10,0,0x95f]` makes these exact writes:

```
+0x830 = 0x55 | (old_830 & 0xffffffe0)
+0x830 = (new_830 & 0xfffffeff) | 0x100
```

No other mapped MCC register is written by selector 4 itself. In particular,
the record's `0x10`, `0`, and `0x95f` tail fields do not cause the startup
`+0x838`, `+0x83c`, or helper sequence on this numeric path. The routine's
count check emits an error if index is out of range but does not branch away;
J81 index 4 is in range because the startup count is 11.

The PMGR caller reaches the MCC function object on the GFX busy-count 1-to-0
edge only when the display-idle callback succeeds, mode 4 differs from its
cached mode, and the MCC function-object guard and pointer are present. That
indirect function-object dispatch supplies `(enable=1, mode=4)` and records
the successful returned mode in provider software. The controller's separate
`callPlatformFunction` active-action path checks `-disable_mcc` before it
applies its startup/disable routine. The function-object forwarding body is
now recovered below: it does not check `-disable_mcc` itself, but the boot
argument can prevent its selector from writing by leaving the controller's
initialized marker clear. These are static call conditions, not proof they
held in test4.

An instruction-level check of the PMGR caller confirms the mode argument and
success update: in `FUN_ffffff80031eb7c0`, the selected mode is loaded from
provider `+0x988` when the edge boolean is 1 (J81's configured value is 4), or
from `+0x95c` otherwise. If it differs from cached `+0x968`, the caller puts
that selected mode in `w1` before calling `FUN_ffffff80031eb6a0` at
`0x31eb940`. The helper requires guard `+0x958` and object pointer `+0x978`,
then invokes the object's vtable method at `+0x78` with `enable=1` and the
selected mode. The original 12B410 `AppleS5L8960X` image resolves that slot
directly. The `AppleS5L8960XMemCacheModeFunction` instance constructor at
`0xffffff8002e5475c` stores vptr `0xffffff8002e5d8b0`; its vtable slot
`+0x78`, at `0xffffff8002e5d928`, contains `0xffffff8002e548a0`. That method
loads the selector from `[x1]`, loads the MCC controller pointer from
`[this+0x28]`, and calls `0xffffff8002e542f0` (the numeric selector body,
whose first substantive instruction is at `0xffffff8002e54300`). Crucially,
it then overwrites the selector's return value with zero and returns success.
Thus PMGR can update cached mode `+0x968` after this wrapper returns even if
the controller selector itself returned an error without writing registers.

The wrapper and selector contain no `-disable_mcc` check. There is an
indirect startup-state gate: controller `start` initializes `+0xb8` to zero
at `0xffffff8002e53708`, reads `-disable_mcc` into `+0xb4`, and calls the
startup enable routine only when the flag is clear (`0x2e53744`–`0x2e53754`).
When `-disable_mcc` is set, startup skips that routine, which is the code path
that marks `+0xb8` initialized. The numeric selector checks `+0xb8` at
`0x2e54324`–`0x2e54328`; if clear, it returns `0xe00002d8` at `0x2e543d4`
before the MCC register writes. Since the function-object wrapper discards
that error and returns zero, PMGR may record mode 4 as applied even though
no selector register write occurred. This is a static control-flow
conclusion, not evidence that `-disable_mcc` was set or that this path ran on
test4.

The first selector write is exactly `0x55 | (old & 0xffffffe0)`: the source
does not mask word 0 back to five bits. So besides replacing bits 4:0, record
word 0 sets bit 6 and leaves bit 5 from the prior value. The following write
sets bit 8 because word 1 is nonzero. Treating word 0 as a plain 5-bit mode
would miss that direct instruction effect; meanings of these bits are not
established here.

The J81 PMGR tree separately sets `mcc-config-fb-caching=4` and binds
`function-mcc_ctrl` to `mcc`/`Mem$`. The startup call above applies the first
record through the enable path; the busy-edge release requests numeric
selector 4 through the PMGR callback path. Those are distinct operations.
This establishes their order within MCC service startup versus its later
runtime selector calls, but not whether MCC's service start completed before
G4G or AppleMobileADBE0 started. The available IOKit matches and saved logs
still provide no cross-service boot timeline or runtime callback evidence.

## Evidence limits

The parsed property is static DT data, and the disassembly establishes how
the original consumer strides it. Keep row field meanings and the runtime
state of `-disable_mcc` unknown. Do not use these offline register writes as
a Linux programming recipe.

Evidence: `artifacts/live/private/gpu-offline/kernelcache`,
`artifacts/live/private/gpu-offline/ios81-dt.json`, and the AppleS5L8960X
prelink load address in `artifacts/live/private/gpu-offline/kexts.json`.
The 220-byte values were decoded as little-endian u32s. Function bodies were
rechecked with Ghidra 12.1.4 against the original 12B410 kernelcache's carved
`AppleS5L8960X` Mach-O, using `MakeFuncDecomp.java` at
`0xffffff8002e53924`, `0xffffff8002e54128`, and `0xffffff8002e54300`.
Instruction addresses and startup data-flow are from that image; no hardware
or live MMIO was accessed.
