# J81 boot marker: archive format experiment and host-only argument prototype

2026-11-09. No instrumented iPad boot or GPU register access. This follows the
[format-string substitution experiment](2026-11-09-j81-host-marker-substitution.md).

## Archive rendering uses the archive's format data

A private copy of the existing iPad `.logarchive` was made. The startup
message's original format string appeared once in its `dsc` decoded-string
file. Replacing that string, byte-for-byte and length-for-length, **in the
copied archive only** changed the same pre-existing startup event rendered by
`log show`: the original archive rendered `Starting GPU driver`, while the
copy rendered `J81MARK1 GPU driver`. The log event's argument remained
`release`. The original archive was not modified.

Thus this event's displayed format can be supplied by archive metadata, even
though the event was recorded earlier. This does not establish whether a
future patched boot's captured `dsc` metadata would reflect memory or the
on-disk image. It makes the original proposed format-string-only marker
ambiguous and a poor first choice.

## Candidate marker in the existing string argument

The AGXG4G code at `0xfffffff0066833b8` loads the eight bytes `release\0`
from a constant into `d0` and stores them at `sp+0x30`, then passes the stack
string to its existing startup log. A host-only alternative replaces the two
instructions that load that constant with:

```
mov  x8, #0x314a   // little-endian bytes 'J', '1', then zeroes
fmov d0, x8
```

The existing store and logging call remain unchanged. The expected message
is `AGXk: Starting GPU driver. Available features: J1`. This does not add a
logging call, trampoline, new MMIO access or new format string. At the
inspected site, the next use of `x8` overwrites it with `sp+0x30` before the
logging call; the replacement instructions do not set condition flags.
The actual execution context, all architectural state and device-specific
patching effects still need independent review. This is a synthetic marker,
not a GPU observation.

In a related public [XNU 8020.140.41 log encoder](https://github.com/apple-oss-distributions/xnu/blob/xnu-8020.140.41/libkern/os/log_encode.c),
`%s` argument bytes are copied into log public-data storage. That is a
reason to expect an argument marker to survive format lookup, **not proof**
of the behavior of the installed 19H394 kernel or its archive. A real test
must verify this on the device. The static format stays the same.

## Host tests and boundaries

A temporary reference-checkout KPF component searches the four original
instructions in AGXG4G `__TEXT_EXEC,__text`. On the original archive
kernelcache, it found one and replaced the first two instructions in the
host harness's private mapping. Missing and duplicate signatures in
disposable image copies resulted in no replacement. All three runs exited 0;
a declined marker is not a stock KPF failure. The original file hash remained
unchanged. A separate native arm64 self-check executed the proposed marker
instructions and confirmed that storing `d0` yields `J1` plus six zero bytes.

The patch is compiled **only for `KPF_TEST`**; the non-test path contains no
mutation. This is not a device module, does not prove KPF loading or code
signing behavior, and does not prove the iPad can boot or retrieve the
marker. The exact four-instruction match needs build and section checks,
independent liveness/ABI review, cache-coherency validation and explicit
failure and recovery behavior before any device experiment.

Private prototype and self-check:
`artifacts/live/private/j81-boot-marker/j81_argument_probe.c` SHA-256
`a629b294718f71231f0e0ccd4f8df39a459be82c3f5ab617c827f9e19bea46f9`,
`j81-argument-selfcheck.c` SHA-256
`c73de80f1580239de65e52e45a8cef99ebc3ab6c66fe8d28026f58fe355474dd`.
The modified archive copy and rendered event are private under
`artifacts/live/private/ios-logarchive-19h394/`.
