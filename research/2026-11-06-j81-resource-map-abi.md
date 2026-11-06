# J81 resource-map ABI boundary

The firmware-object resource path now has concrete kernel symbol identities:

```text
0xffffff80023de5a4  IOMemoryDescriptor::withPhysicalAddress
0xffffff80023e4840  IOMemoryDescriptor::createMappingInTask
```

For each of the four active resource records, `0xffffff800329d558`:

1. creates a physical descriptor with `withPhysicalAddress(physical, size,
   alignment, 3)`;
2. calls the firmware helper at `0xffffff800329d6a4`, whose descriptor view
   uses the private selector `0x90007`;
3. creates and retains an `IOMemoryMap` with
   `createMappingInTask(kernel_task, 0, 0x101, 0, 0)`;
4. stores the map object at `0x5a0 + index * 8` and the descriptor at
   `0x578 + index * 8`.

The `0x101` argument is the map object's address/option field as consumed by
the implementation: the mapping routine stores it and passes it onward with
the internal `0x08000000` map bit.  It is not a GPU register value.  The
separate `0x90007` selector remains an Apple accelerator/DART policy field.

This resolves the object lifetime and mapping-call ABI, but not the final GPU
IOVA or DART ownership.  Linux must still provide equivalent backing and
device-visible addresses before execution can be enabled; the host model
remains fail-closed.
