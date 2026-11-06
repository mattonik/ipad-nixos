# J81 IOMemory flag low-bit resolution

Apple's public XNU `IOMemoryDescriptor.h` defines `kIOMemoryTypePhysical = 0x20`, `kIOMemoryDirectionMask = 0x7`, and direction values `in=1`, `out=2`, `out-in=3`. The J81 initializer's allocator expression ending in `0x22` therefore resolves to physical memory plus outward I/O direction.

Its mapping option `0x80007` resolves only partially: the low `0x7` sets the complete direction-mask field, while the high `0x80000` bit is absent from the current public header. The evidence does **not** identify that high bit as a cache mode. It remains a legacy/private mapping option, so Linux ownership and cache attributes stay unresolved.

Reference: Apple XNU `IOMemoryDescriptor.h`, direction and memory-type definitions: <https://raw.githubusercontent.com/apple-oss-distributions/xnu/main/iokit/IOKit/IOMemoryDescriptor.h>.
