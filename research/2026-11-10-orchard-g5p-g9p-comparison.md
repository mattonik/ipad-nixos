# Orchard G5P/G9P comparison for the J81 A8X investigation

## Current public state

Orchard `main` still describes the iPad 6 as experimental and says GPU
acceleration is unavailable. The public A10 demonstration is ahead of that
branch: it reports a G9P Mesa/Vulkan backend rendering Hyprland and WebGL on
iPad 6 hardware, with iPad 7 and related A10 boards as targets.

Sources:

- [Orchard main README](https://github.com/OrchardLinux/orchard)
- [A10/G9P hardware demonstration](https://www.omarchyarchive.com/posts/henrikklee-hyprland-ipad-6-a10-gpu/)

The A9/G5P work is a separate draft Orchard change, not an A10 or A8X
driver. Its source tree is useful because it exposes the minimum integration
surface and its safety boundaries:

- extract the original `com.apple.AGXFirmwareKextG5P` META LDR from the user's
  own kernelcache, rejecting size and digest mismatches;
- add a built-in DRM transport/firmware core and a typed render-job path;
- enable the GPU only on the qualified board through a disabled-by-default DT
  node;
- keep firmware bytes and captured jobs out of the public tree.

See [Orchard PR #74](https://github.com/OrchardLinux/orchard/pull/74),
especially its firmware recipe and `s8003` DT resource patch.

## What is reusable for J81

The G5P DT shape independently matches the addresses already established for
J81: RGX at `0x201000000`, Fender/GPC at `0x201e00000`, and the single
`ps_gfx` power domain. This supports our resource split, but does **not** make
the A9 transport or firmware ABI valid for A8X. J81's interrupt wiring and
firmware protocol still require independent proof.

The reusable design pattern is therefore:

1. identify and extract the A8X META/firmware payload from the local iOS
   kernelcache, with exact size/digest guards;
2. model the existing two hardware windows and `ps_gfx` as separate resources;
3. keep the first driver milestone read-only/bring-up gated until firmware
   loading, IRQ delivery, and one inert render path are separately observed;
4. add Mesa userspace only after the kernel transport has a stable ABI.

The G5P/G9P render job ABI, register programming, and firmware image cannot
be copied to J81: the Air 2 is A8X/T7001 with PowerVR GXA6850, not G5P or G9P.
The interrupt layout is already a concrete warning: the G5P DT patch uses
AIC IRQs 170--174, while J81's recovered `sgx` node uses the distinct
five-interrupt range 134--138. Any future A8X transport must bind the J81
interrupts, not inherit the G5P list.

## Offline next boundary

The highest-value offline task is now a format/sequence comparison: extract
only the generic META firmware-loader and DRM transport concepts from the G5P
patch, then compare them against the J81 iOS `AGXMetaFirmware` constructor and
the already recovered `0x201000000`/`0x201e00000` mappings. No new device read
is justified by the A9/A10 result alone.
