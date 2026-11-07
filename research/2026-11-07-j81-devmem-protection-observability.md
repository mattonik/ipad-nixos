# J81 `/dev/mem` GPU mapping observability

Offline feasibility check; no device access.

The test kernel is the pinned Hoolock Linux revision
`6831bc701a6ce059e71e5aaa9488c9195bea6927` (7.3.0-rc1), from
`flake.lock` and `kernel/hoolock.nix`. At that exact source revision,
`arch/arm64/mm/mmu.c:phys_mem_access_prot()` selects
`pgprot_noncached(vma_prot)` when `pfn_is_map_memory(pfn)` is false; for a
RAM PFN, `O_SYNC` instead selects `pgprot_writecombine(vma_prot)`. The
predicate delegates to `memblock_is_map_memory()` in `arch/arm64/mm/init.c`.
Thus the Linux-selected protection can be inferred from the live RAM map,
but that is source-derived, not a measurement of the installed PTE.

The pinned kernel configuration starts from Hoolock Docs `config_16k` at
`23ebe1fbc375599221553a7e1815e5de182a6b42`, then changes 4K pages and a few
named options. That base enables `PROC_PAGE_MONITOR` and `DEBUG_FS`, but has
`PTDUMP_DEBUGFS` disabled. `/proc/<pid>/pagemap` reports presence, PFN and
software PTE flags, not ARM64 memory attributes; `/proc/kpageflags` reports
page metadata, not a mapping's protection. `smaps` can describe a PFN/IO VMA
but not its AttrIndx. The optional kernel page-table dump is unavailable in
this config and, in any case, is for kernel mappings rather than an arbitrary
userspace VMA.

For a future control boot, the minimal no-GPU-access check is to save the
live `/proc/iomem` System RAM ranges (and, if useful, the runtime FDT memory
`reg` properties) alongside the kernel-notes identity. If those ranges
exclude the GPU core PFN at `0x201000000`, the pinned arm64 source implies
the `pgprot_noncached` branch. Do not mmap/dereference the GPU merely to
collect pagemap: it cannot reveal the attribute. Direct runtime PTE
inspection would require a purpose-built kernel hook/module that walks the
diagnostic process's page tables; its build/config and ABI costs are not
justified for this check.

The loader populates the DT memory range, so repository DTS showing
`memory@800000000` does not by itself prove which ranges entered memblock in
the failed test4 boot. The test4 capture has no matching live `/proc/iomem`
snapshot; the GPU PFN's classification on that boot remains unconfirmed.

Evidence: Hoolock Linux pinned `arch/arm64/mm/mmu.c` and `arch/arm64/mm/init.c`;
Hoolock Docs pinned `config_16k`; `kernel/hoolock.nix`, `flake.nix`, and
`flake.lock`; Linux `Documentation/admin-guide/mm/pagemap.rst`.
