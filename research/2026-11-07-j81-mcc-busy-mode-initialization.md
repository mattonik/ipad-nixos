# J81 iOS 8.1 MCC busy-mode initialization

Offline static trace of the iPad5,3 iOS 8.1 (12B410) T7000 controller. No
device, firmware execution, or MMIO was used.

## Finding

The busy MCC mode field at `AppleT7000PerformanceController this+0x95c` is
assigned by the controller's `start` path, not by the recovered C++
constructor. The assignment is guarded. On the normal J81 path, the PMGR
device tree supplies `mcc-config-disp-on = 3`, and startup writes that value
to `+0x95c` if the MCC function object resolves. This establishes the
configured busy-mode value as 3 under those conditions. It does not prove the
value in any particular runtime boot.

## Instruction/decompiler evidence

The `T7000.raw` slice at base `0xffffff80031e3000` is the 12B410 AArch64
T7000 controller image, analyzed in Ghidra project
`artifacts/live/private/gpu-offline/t7000`. A whole-slice immediate search
for `0x95c` found the field store at `0xffffff80031e8924` in
`FUN_ffffff80031e87c8`, the read/use in the busy-edge routine
`FUN_ffffff80031eb7c0`, and an address calculation in the DISP0 handler
`FUN_ffffff80031ea58c`. The search was:

```sh
JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
/opt/homebrew/opt/ghidra/libexec/support/analyzeHeadless \
  ipad-nixos/artifacts/live/private/gpu-offline t7000 \
  -process T7000.raw -noanalysis \
  -scriptPath "$PWD/ipad-nixos/tools/ghidra" \
  -postScript FindImm.java ffffff80031e3000 ffffff80031f1000 95c 95c
```

The exact assignment in `FUN_ffffff80031e87c8` is:

```c
// if soc-tuning != 0 and function-mcc_ctrl resolves:
... lookup("mcc-config-disp-on") ...
local_24 = *piVar3;
*(int *)((long)param_1 + 0x95c) = local_24;
```

The routine is called from `AppleT7000PerformanceController::start`,
`FUN_ffffff80031e6fc8`, after startup sets up its other controller state.
The routine first reads `soc-tuning`; if zero or absent, it returns without
assigning `+0x95c`. If `function-mcc_ctrl` is missing, it also returns before
the assignment. The assignment itself is inside successful lookup of
`mcc-config-disp-on`; if that property is absent, the field is not written by
this routine. Therefore this is a guarded start-time initialization, not an
unconditional constructor default.

The decoded J81 tree `artifacts/live/private/gpu-offline/ios81-dt.json`
contains the PMGR properties `soc-tuning = 1`,
`mcc-config-disp-on = 3`, `mcc-config-disp-off-audio-off = 1`,
`mcc-config-disp-off-audio-on = 2`, and `mcc-config-fb-caching = 4`.
`function-mcc_ctrl` points to function `Mem$`. Thus, provided the matching
function object resolves during start, the code writes 3 to `+0x95c`. The
busy-edge handler selects this field on the 0-to-1 SoC-busy edge; the
configured framebuffer mode 4 is a separate field at `+0x988` used on the
1-to-0 edge.

## Constructor/allocation boundary and limits

The recovered `AppleT7000PerformanceController::start` and its directly
relevant helper contain no unconditional zero-store to `+0x95c`; the one
instruction-level store found in the T7000 slice is the guarded property
assignment above. The class instance's allocation and base-class construction
are dispatched through the IOKit metaclass/framework path outside this
T7000-only slice. The preserved disassembly/decompilation does not establish
whether that allocator zeroes the complete instance, nor does it recover a
class-specific constructor that initializes `+0x95c`. Consequently, if the
guarded start assignment is skipped, static evidence here cannot say whether
the field is zero, stale, or otherwise initialized before first use.

The J81 device tree and static code show what a successful configured startup
should store. They do not prove that the MCC function resolved or that this
startup branch ran in the captured boot. No runtime object-memory capture
contains `+0x95c`.
