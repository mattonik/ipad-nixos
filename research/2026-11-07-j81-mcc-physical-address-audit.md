# J81 MCC physical-address audit (2026-11-07)

Offline audit only; no device access or MMIO was performed.

## Address path in the original iOS 8.1 tree

The saved 12B410 J81 tree is `artifacts/live/private/gpu-offline/ios81-dt.json` (decoded from `ios81-dt.bin`). The MCC node is a child of `arm-io`, with `reg = { addr: 0, size: 0x200000 }`. `arm-io` declares two address and two size cells. The critical detail is that this is Apple's ADT, not a flattened DT blob whose `ranges` should be decoded with generic FDT big-endian cell rules. The original iOS kernel's own `IODTResolveAddressCell` routine combines two raw 32-bit cells as low-word first (`first | second << 32`). Applying that exact convention to `arm-io.ranges` gives:

```
child 0x0000000000000000 -> parent 0x0000000200000000, length 0x0000000100000000
child 0x0000000600000000 -> parent 0x0000000600000000, length 0x0000000200000000
```

Thus MCC child address zero falls wholly in the first window and Apple's own range-resolution code translates it to physical `0x200000000..0x2001fffff` (2 MiB). The old `0x02000000` result came from incorrectly grouping the raw cell bytes as a big-endian 64-bit integer. The corrected address is in the same high physical-address domain as GPU (`0x201...`), PMGR (`0x20e...`) and Linux-published peripheral ranges.

The original 12B410 kernelcache analysis identifies `AppleS5L8960XMemCacheController` as the `mcc,s5l8960x` provider. Its `start` at `0xffffff8002e53400` calls `IOService::mapDeviceMemoryWithIndex(0, 0)`, stores the returned `IOMemoryMap` at `self+0x88`, then calls `IOMemoryMap::getVirtualAddress` and stores the mapped VA at `self+0x98`. The original `IODTPlatformExpert::getNubResources` calls `IODTResolveAddressing(entry, "reg", ...)`; that resolver reads the parent bus `ranges` property and `IODTResolveAddressCell` combines address cells low-word-first while walking the parent hierarchy. This directly ties the MCC `reg` resource to the Apple ranges translation above. The provider's register accesses at offsets `+0x10`, `+0x800`, `+0x83c`, and `+0x1000..+0xf000` are relative to this map, not PMGR offsets. Detailed register effects/startup ordering are in `2026-11-07-j81-mcc-ios81-record-stride.md`.

**Limit:** this is static source-derived resource translation, not a measured physical bus decode or runtime mapping address. It resolves the probable physical address much more strongly than the prior generic-DT calculation, but does not prove the MCC peripheral responds there under Linux or establish register semantics/access safety. No Linux MMIO access follows from it.

## Comparison with the available Linux snapshot

The read-only control snapshot at `artifacts/live/j81-readonly-20261107T114456Z/` reports `/proc/iomem` MMIO windows beginning around `0x20a...`, `0x20c...`, `0x20e...`, PCIe at `0x600000000+`, and System RAM at `0x800c00000+`. It does not enumerate the MCC range `0x200000000..0x2001fffff`. The captured runtime FDT identifies `apple,j81` / `apple,t7001`; the selected inventory covers display and PMGR nodes, not an MCC node. This Linux snapshot therefore neither contradicts the corrected static address nor demonstrates Linux MCC ownership/mapping.

The Linux snapshot's `/proc/iomem` and memory ranges do not classify the translated MCC range as RAM or publish it as a device resource. The safe conclusion is address resolution only; Linux ownership, decode, access width, side effects, and power prerequisites remain unverified. Do not add a Linux MMIO read or mapping based only on this static evidence.
