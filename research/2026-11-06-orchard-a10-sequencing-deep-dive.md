# Orchard A10 sequencing versus J81

I reviewed Orchard commit `b5e37693bb1246ce566406a205ae0ca834cdc18e9`
(`kernel: the A10 GPU in drm/imagination`) and compared its power-on path with
the J81 captures.

## What the A10 driver actually requires

The A10 implementation is not just a register shim. Before any RGX access it:

1. maps a 1 MiB firmware window and a coherent heap;
2. programs the window into both Fender (`+0x200c`, 4-byte stride) and the A7-IOP
   (`+0x8`, 8-byte stride), then enables the IOP window at `+0x38`;
3. enables Fender run at `+0x2048`;
4. boots Apple RTKit and starts endpoints `0x20` and `0x21`;
5. forces Fender state 0 when a previous state is nonzero;
6. requests a nonzero performance state and waits for the acknowledged state;
7. only then builds the Apple firmware layout and waits for the firmware's
   shared-memory ready flag.

The A10 driver therefore has two separate prerequisites that our J81 probes do
not have: a live coprocessor transport and a firmware-owned shared-memory
contract. Its `gfx-kf`/A7-IOP node is not optional plumbing.

## What the J81 result proves

The J81 PMGR cycle, GPC init, and post-GPC bridge read demonstrate that the
application processor can acquire the GFX domain and access the Fender/GPC
window. They do **not** demonstrate that the RGX slave port is released. The
first direct read at `0x201000020` still hangs, exactly where an Apple firmware
or an additional A8X-specific wrapper would be expected to own the transition.

This explains why copying Orchard's three GPC writes was insufficient: those
writes are downstream of A10's RTKit/window setup. On J81, the missing piece is
not another generic Linux power-domain call; it is the undocumented A8X host
initialization and firmware/alive contract.

## Consequence for implementation

Do not port `pvr_apple.c` or its A10 firmware filename to J81. The useful parts
to retain are the ordering and fail-closed state machine. The next offline
milestone is to identify the J81 G4G firmware's host-visible window, boot
descriptor, and alive notification from the iOS 8.1 AGX kext. Until those are
known, another RGX read or a render attempt would only repeat the established
hang boundary.

Source checked locally; no firmware bytes or hardware access were added.
