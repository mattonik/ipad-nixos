# J81 read-only control-boot snapshot

The cycle-capable RAM payload booted for a read-only inventory. The snapshot is stored privately at `artifacts/live/j81-readonly-20261107T114456Z/`; its kernel-notes SHA-256 is `82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014`.

`/proc/iomem` reports System RAM beginning at `0x800c00000`, with another small System RAM range at `0x87d0da000`. The runtime FDT `memory@800000000/reg` contains those ranges. The GPU core physical address `0x201000000` lies outside both ranges. For this control boot, the pinned Linux arm64 `phys_mem_access_prot()` non-RAM branch therefore supports `pgprot_noncached` for this address; this is a source-derived conclusion, not a direct PTE measurement. It does not by itself prove the exact memblock state of the earlier test4 boot.

The snapshot also contains display class, controller device-tree and sysfs inventory, memory statistics, and filtered kernel messages. No GPU register mapping or MMIO read, PMGR cycle, module insertion, or firmware execution was performed.
