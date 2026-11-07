# J81 MCC one-shot read preparation

Offline probe design; no device access or MMIO was performed.

`kernel/mcc-read-once/` builds a tiny out-of-tree module against the exact
PMGR-cycle test kernel: Hoolock 7.3.0-rc1 with patch 0123, via its own
`build.nix`. Module initialization checks
`apple,j81` and creates a read-only sysfs endpoint, without mapping or reading
hardware. The host-side acknowledged runner is implemented by
`boot/j81_mcc_capture.py`; the target-side preflight and read flow is
implemented by `boot/j81-mcc-read-once-run.sh`. Preflight checks the target
model and compatible string, boot ID, kernel release and notes hash, module
hash, and RAM-only root before opening the watchdog or loading the module.
The existing supervisor requires the
20-second watchdog and an operator `READ` acknowledgement immediately before
the sysfs read; it feeds only after the host persists and acknowledges the
returned value. The wrapper pins
kernel-notes SHA-256 to the cycle payload's saved value
`82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014`. The module
reserves only the containing 4 KiB page `0x200000000..0x200000fff`, maps that
same page, performs one
32-bit `readl` at `0x200000830`, and releases the mapping and reservation. A
failed reservation or mapping is a hard stop; no retry in that boot. The
module takes a permanent self-reference after sysfs setup, so normal module
unload cannot remove the endpoint or reset its one-shot guard before reboot.

Address basis: the iOS 8.1 ADT MCC resource is child offset 0, size 2 MiB.
Apple's `IODTResolveAddressCell` combines cells low-word-first and resolves
the first `arm-io.ranges` window to physical `0x200000000`. The original
12B410 MCC numeric selector reads `+0x830` as a 32-bit word before its
read-modify-write, and selector 4's record is `[0x55, 0x11, 0x10, 0, 0x95f]`.
If Apple's startup enable ran, it initially sets bits 4:0 to `0x10` and
clears bit 8. If the selector-4 callback later ran, its code writes bits
4:0 from `0x55` (resulting low five bits `0x15`), sets bit 8, sets bit 6,
and preserves bit 5 and the other prior bits. Those are conditional iOS
expectations, not Linux expectations: a Linux capture has no established
MCC initialization or ownership state, so any returned word is observational
and should not be judged against either value.

Offline checks pass for the mocked module, host capture protocol, shell syntax,
and the composed watchdog supervisor transcript. The actual module build
succeeded against the patched Hoolock 7.3.0-rc1 cycle kernel. The built module
is `artifacts/live/gcroot-j81-mcc-read-once-module/mcc-read-once.ko` with
SHA-256 `7f7a73305c843f11a5b4311eb3890cbf3e52a23d83992511df3231ae09fe8492`.
Its embedded vermagic is `7.3.0-rc1 SMP preempt mod_unload aarch64`. This is a
build artifact only; it has not been loaded or tested on hardware.

### Staging bundle

The updated watchdog supervisor was cross-built with the existing Linux
builder as a static AArch64 binary. SHA-256:
`81ade85aff5811689abaec0c5318d7ba6997bc3ecc9681c95df8088e7271d826`.
The RAM-staging bundle is
`artifacts/live/gpu-test-bundle-20261107-mcc`; its manifest includes that
supervisor, the module above, and `j81-mcc-read-once-run.sh`. The module hash
in the bundle is
`7f7a73305c843f11a5b4311eb3890cbf3e52a23d83992511df3231ae09fe8492`.

Host-only checks passed for the supervisor's acknowledged-read path, the
module's bounded single-read and cleanup behavior, the MCC capture protocol,
bundle manifest contracts, shell syntax, and every staged file's manifest
hash. The cross-build needed 64.6 MB of Nix cache dependencies; the builder
completed despite unavailable cache DNS after those dependencies were fetched.
Host free space then fell below the builder's 15 GB build floor, so no more
Nix builds should run until space is available. No iPad access or hardware
capture was performed.

Limit: the corrected physical address is static Apple source-derived evidence,
not a live decode. Linux's current `/proc/iomem` does not list the range. A
successful reservation only excludes Linux resource-tree conflicts; it does
not prove that the peripheral is powered, responds safely, or that the access
will not hang. The one 32-bit access width is grounded in Apple's exact
selector path. The module must be rebuilt against the exact running kernel;
Linux vermagic plus the runner's kernel-notes hash gate this. No unrestricted
address, write, address scan, PMGR gate, or bypass is included.
