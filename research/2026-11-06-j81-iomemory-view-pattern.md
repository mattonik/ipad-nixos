# J81 IOMemory view pattern

The recovered iOS 8.1 `ios81-init-allocation.c` shows a repeated allocation/mapping pattern behind the four-view layout. Each backing allocation is created with an allocator flag expression ending in `0x22`, then the resulting object is mapped through its `+0x90` method with `0x80007`. The first four repetitions use independent size sources (`param_1[3]`, `[4]`, `[5]`, and `[6]`) and independent object/view slots.

This strengthens the existing classification: the views are separate physical-I/O-backed objects with a common mapping policy, not four offsets into one ordinary Linux firmware buffer. It does not resolve the legacy high mapping bit in `0x80007`, nor the Linux lifetime/ownership equivalent, so the execution gate remains closed.
