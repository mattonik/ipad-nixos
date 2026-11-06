# J81 private map-wrapper dispatch

The selector path is now resolved through both virtual dispatch layers:

```text
wrapper vtable +0x90  -> 0xffffff800324a0bc
provider vtable +0x5a0 -> 0xffffff80032677e4
provider vtable +0x6c0 -> provider-created map object
```

`0xffffff800324a0bc` first searches the wrapper's existing map list for the
same task.  With selector bit `0x8` set, it asks an existing map object to
validate/reuse the mapping.  Otherwise it calls provider `+0x5a0` with the
task, wrapper, and selector.  J81's provider target `0xffffff80032677e4`
allocates a map object via provider `+0x6c0`, then invokes that object's
`+0x70` initializer with `(provider, task, wrapper, selector)`.

This proves that `0x90007` selects a private accelerator map policy and is not
just an IOMemoryMap cache flag.  The wrapper and dispatch layers themselves
perform no GPU MMIO or direct DART-table programming.  The remaining address
question is now limited to the provider-created map object's `+0x70` method
and whether that method returns a device-visible address, a shared CPU view,
or both.
