# J81 19H394 marker: host review and temporary KPF build

2026-11-09. This records host work only; no device boot was performed.

The candidate replaces the two instructions at unslid
`0xfffffff0066833b8` with `mov x8,#0x314a; fmov d0,x8`. The following
original `str d0,[sp,#0x30]` supplies `J1\0` to an existing GPU startup
logging call. In the disassembly, the next instruction overwrites `x8` with
`sp+0x30`; the replacement does not set flags, alter the stack, branch or
introduce a new call. The surrounding original code already uses `v0`.
A native ARM64 self-check initialized all of `v0` to ones and verified the
replacement leaves `J1` followed by fourteen zero bytes after a `q0` store.
This is a targeted check, not a full kernel execution or independent audit.

The device's ordinary archive reports kernel process image UUID
`CC26BE6A-292B-3759-9ED0-290BCF18B090`, matching the downloaded 19H394
kernel's Mach-O UUID. This is an additional consistency check, not a hash of
the device's running memory.

The reviewed temporary KPF component requires that UUID, Darwin 21.6,
XNU `8020.241.42~8`, one exact 16-byte match in AGXG4G `__TEXT_EXEC,__text`,
and unchanged four matched instructions immediately before applying the two
replacement words. A mismatch prints `applied=0` and leaves the custom site
unchanged. The component does not suppress ordinary stock KPF patches.
The host harness succeeded with the correct image and declined altered,
duplicate and wrong-UUID inputs; it also declined the 19H422 image. The
source image was unchanged. Device code is enabled only by the explicit
`J81_MARKER_DEVICE_BUILD` compile flag.

PongoOS reference checkout `e98323f8a09abd80fc4cbcd74dee023b91a1ec22`, with
newlib submodule `f9ea5054de8fb51dff6f6d3c2e7cdd4aa89744b8`, built the
ARM64 Mach-O KPF module with that flag. Private module:
`artifacts/live/private/j81-boot-marker/checkra1n-kpf-pongo-j81-marker`,
SHA-256 `7fb1662f2552749707e0c37c3efdbaad40b1b15f91c326e525ae7ed7abeff870`.
Private guarded source SHA-256
`dd39e21a77a7f20dbcb2779e5f56e570aaed463b6e186aefb89375bdc809072e`.
The module has not been loaded, and the binary is not proven compatible with
the palera1n binary's embedded PongoOS. The reference checkout's `entry.c`
invokes the preboot hook before `lowlevel_cleanup`, which cleans/invalidate
caches before the jump; the actual embedded PongoOS build has not been
identified, so its coherence path remains unverified.

The reference source tears down USB before calling the preboot hook. A
`printf` receipt therefore cannot be assumed to arrive at the Mac. A `J1`
message recovered from the boot archive would positively show the marker ran;
an absent message is inconclusive without an independent patch receipt and
verified logging/boot conditions.

Palera1n's [documentation](https://github.com/palera1n/palera1n/blob/main/docs/palera1n.1)
describes its normal rootless mode as a temporary jailbreak boot and says its
jailbreak files are stored on a temporary filesystem unless the loader or SSH
is used to write files. It is still more than merely loading this one marker:
stock KPF and boot environment changes also occur. Exact v2.4 behavior and
compatibility of our module are not established here. Before running a boot,
make the receipt and the actual selected PongoOS/boot path concrete, and
preserve the normal boot/DFU recovery path. A successful ordinary iOS boot
was observed before this work; no attempt has yet been made to return from a
custom iOS boot to Linux.

The reference PongoOS `_write_r` implementation also calls `screen_putc`
when printing; this suggests the receipt may appear on the iPad display,
but visibility and the embedded build are unverified.
