# J81 DART plan model

`tools/gpu_g4g_dart_plan.py` now validates the missing Linux-side contract for
the four registered firmware views. A plan is complete only when all four
mapped bases, backing bases, and DART IOVAs are page-aligned, pairwise distinct,
and each mapped/backing pair is non-identical. The model deliberately does not
assume a GPU DART aperture or stream identity. The recovered J81 ADT gives a
stronger negative result: its `sgx` node has no `iommu-parent`, DART phandle,
VM aperture, or stream property. The remaining question is whether this
pre-M1 GPU bypasses DART or uses an implicit firmware-owned context.

Even a complete synthetic plan returns `execution_allowed=false`. It is a
validation boundary for a future adapter, not a hardware programming tool.
