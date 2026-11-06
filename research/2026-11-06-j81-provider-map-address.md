# J81 provider-map address materialization

The provider-created map object's vtable `+0x80` resolves to
`0xffffff800326d018`.  Its address path is:

```text
if (state & (1 << 6))
    return descriptor->vtable[0xa8](0, &temporary);
return map->field_0x90;
```

The method does not write GPU registers or DART tables.  It either returns a
stored map field or delegates to the retained descriptor's custom `+0xa8`
method.  That custom descriptor target is the remaining static hop needed to
classify the returned value as a CPU virtual address, a physical address, or a
device/DART address.

This narrows the contract's remaining address question to
`descriptor-backed map address materialization and DART ownership`; no Linux
address substitution is enabled.
