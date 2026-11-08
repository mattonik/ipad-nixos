# J81 iOS 15 AGX user-client and capture-hook evidence

Date: 2026-11-07. Offline artifact/source inspection only; no iPad access and
no Orchard source changes.

## Artifact provenance

The local decoded J81 iOS 15 cache is
`artifacts/live/private/gpu-offline/ios15-kernel`, SHA-256
`832cd980f257e6205b8ec131abea2a8470f3a3455f2c7039c890a091149c7389`. Its
embedded prelink metadata says `DTPlatformVersion=15.8` and
`DTPlatformBuild=19H402`. The exact 19H422 source association for this file is verified by the matching
manifest digest and raw and decoded caches. The prelink value is platform
metadata, not the top-level product build. See [the provenance
check](2026-11-08-j81-ios15-kernelcache-provenance.md). This does not establish
which binary was running on a device. The adjacent
`ios15-kexts.json` is its extracted prelink inventory. Its AGX entry is
`com.apple.AGXG4G`, executable `AGXG4G`, personality `AGXG4G_A0`, class
`AGXAcceleratorG4G_A0`, provider `AppleARMIODevice`, and `IONameMatch` is
`gpu,t7001`. The personality contains no `IOUserClientClass` key.

## What the cache establishes

The decoded kernelcache contains `AGXDeviceUserClient` and
`AGXSharedUserClient` strings. File-offset mapping narrows the provenance:
`AGXSharedUserClient` at file offset `0xc7cfa6` lies inside the AGXG4G
prelinked executable span (`0xc6e640..0xc7ffc3`, from load address
`0xfffffff0057c2640`, size `0x11983`). However, the adjacent string at
`0xc7cfbf` is `site.AGXSharedUserClient`, a shape consistent with an os_log
subsystem/category label. This makes logging metadata the likely explanation;
the occurrence is not evidence that AGXG4G implements a user-client class. The
`AGXDeviceUserClient` occurrences around `0xd1c02b` lie inside the Sandbox
executable span (`0xd00680..0xe2807a`, from load address
`0xfffffff005854680`, size `0x1279fa`), so those occurrences are policy-side
evidence, not proof that AGXG4G implements that class. The kernelcache also
contains generic IOAccelerator-family names `IOAccelSharedUserClient2` and
`IOAccelMemoryInfoUserClient`. The AGX personality does not statically declare
`IOUserClientClass`; no `newUserClient` type-to-class mapping was recovered.
The A10 capture tool's `AGXDeviceUserClient` entitlement aligns with the policy
string, but does not establish iOS entitlement acceptance on J81 or the actual
class opened.

## Dispatch and useful capture points

The A10 reference at
`gpu/tools/a10/ios-capture/iohook.m` in the local Orchard checkout
patches `IOConnectCallMethod` and `IOConnectCallAsyncMethod`, and separately
patches `iokit_user_client_trap`. The latter is the common fast-trap syscall
stub reached by `IOConnectTrap0..6`; its arguments expose the connection,
trap index and six raw words. The method APIs expose the external-method
selector, scalar arguments, structure input/output and return status. These
are the most useful observation points to port first: method-call output
structures can reveal resource creation handles/address pairs, while the trap
hook can correlate submission trap indices and snapshot their pointer-bearing
records before/after the call. The two routes are distinct: a method selector
is not the fast-trap index. The exact J81 AGX external-method table, trap
indices, target function pointers and payload ABI were not recovered here;
do not copy A10 selector/index meanings.

The A10 hook implementation also contains assumptions that need separate
validation on iOS 15/J81: `dlsym` must resolve the trap stub in-process; its
four-instruction trampoline rejects PC-relative prologues; it changes IOKit
code pages to writable/executable and later exits after a trap due to a
completion-thread fault; and its pointer-tree scan accepts only addresses
`0x100000000..0x1000000000`, reads 4 KiB per candidate and has a 96-node
budget. These are not safe portability facts. Prefer first recording bounded
method selector/scalar/structure arguments and return values, then add
trap-record snapshots only after establishing J81 pointer bounds and the
actual submit call.

## Limits and next evidence

This is static string/prelink/source evidence, not an iOS runtime IORegistry
dump, entitlement acceptance result, or call trace. The local prior runtime
inventory does not provide an iOS 15 user-client connection trace. The next
decisive artifact is a read-only J81 iOS 15 observation of the matched
`AGXAcceleratorG4G_A0` service's `newUserClient` result/type (or a controlled
foreground-app trace logging class/type and successful open), followed by
selector/trap call records. Until then, keep both class candidates and all
dispatch meanings provisional.
