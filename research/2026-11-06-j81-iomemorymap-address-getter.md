# J81 `IOMemoryMap` address-getter resolution

The retained map objects used by the firmware preparation path can be typed
from the kernel's `IOMemoryMap` vtable:

```text
IOMemoryMap vtable:                 0xffffff8002494a80
vtable[0x80]:                       0xffffff80023e4640
0xffffff80023e4640:                IOMemoryMap::getVirtualAddress()
```

The J81 preparation routine calls the map object's `+0x80` before adding the
packed LDR offsets and passing the result to accelerator `+0x210`.  Thus the
static evidence says the value is obtained from an `IOMemoryMap` virtual
address getter; it is not a hard-coded GPU register address or a firmware
image field.

This resolves the object method, but not the address-space ownership: Apple
may use the returned CPU mapping as a shared META view, while the accelerator
or its private `0x90007` selector may establish device visibility elsewhere.
The Linux port still needs an explicit equivalent for that policy before any
GPU-visible address can be substituted.
