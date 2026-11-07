# J81 event-ring backing-object runtime class (offline, 2026-11-07)

This follow-up traces the provider and backing-object virtual calls used by the
J81 event-ring allocation. It uses the preserved iOS 8.1 kernelcache and its
prelinked kexts only; no firmware was run and no device was accessed.

## Recovered receiver chain

The `AGX` personality in `artifacts/live/private/gpu-offline/kexts.json`
registers `AGXAcceleratorG4G_A0` for `gpu,t7001` and declares
`IOProviderClass = AppleARMIODevice`. In `ios81-init-allocation.c`, AGX's
`start`-side object field at `this+0x58` is carried as `lVar9` into the
IOAcceleratorFamily2 allocator at `0xffffff800326dfa4`. That helper:

1. invokes `provider->vtable[0x608]` for a size limit;
2. invokes `provider->vtable[0x5e8](provider, kernel_task, selector, size,
   flags, providerData)` to create the retained backing object;
3. places the returned object at wrapper `+0x80`.

`kernel_task` is not a guessed class argument: the AGX import cell at
`0xffffff80032ac558` resolves to the kernelcache export
`_kernel_task` (`0xffffff8002536010`). The ring setup then invokes wrapper
slot `+0x90` for the task mapping and invokes the backing object's slot
`+0x140`; the latter return is saved as the CPU base used to form the ring
state and event-record pointers. These call sites are at
`0xffffff800329a660`–`0xffffff800329a6b8` and are preserved in
`ios81-agx-disasm.txt`, `ios81-init-allocation.c`, and
`ios81-ring-allocator.c`.

This establishes the provider **class contract** (`AppleARMIODevice`) and the
two virtual slot offsets, but does not establish either slot's concrete
runtime target. The `AppleARMIODevice` initializer found in `ARMPlatform.raw`
constructs/registers its `OSMetaClass`; its vptr is the metaclass vtable, not
the runtime service object's vtable. Treating that metaclass table as the
provider table would be an invalid resolution. The prelinked raw kext has no
usable `LC_SYMTAB`, and the available external kernelcache symbols do not
export an `AppleARMIODevice` vtable or implementation symbol.

## Backing class cross-checks

The kernelcache's exported public vtables were read from the matching
`__DATA,__const` contents at their symbol addresses:

| Class | vtable slot | Resolved target |
|---|---:|---|
| `IOMemoryDescriptor` | `+0x140` | null |
| `IOBufferMemoryDescriptor` | `+0x140` | `IOBufferMemoryDescriptor::setDirection` (`0xffffff80023d6f70`) |
| `IOMemoryMap` | `+0x80` | `IOMemoryMap::getVirtualAddress` (`0xffffff80023e4640`) |
| `IOMemoryMap` | `+0x140` | `IOMemoryMap::MetaClass::alloc` (`0xffffff80023e3d3c`) |

The slot-`+0x140` result in AGX is used as a mapped CPU base, so these public
base classes do not identify the dynamic backing object. In particular, the
known public `IOMemoryMap::getVirtualAddress` is at `+0x80`, and the AGX call
receiver is the wrapper's backing field, not the map handle returned by
wrapper `+0x90`. The matching kernelcache also contains class-name strings
`IOAccelMemory`, `IOAccelMemoryAllocator`, and `IOAccelMemoryMap`; these are
plausible search leads only, not proof that any one is the ring object or
implements either slot.

## Result and next evidence

The concrete provider class name is now pinned to `AppleARMIODevice` by the
AGX personality, and the called provider arguments are pinned, including the
`kernel_task` argument. However, static evidence currently available does not
recover the AppleARMIODevice instance vtable's `+0x5e8` target, the class
returned from that factory, or its `+0x140` target. The public vtable checks
exclude a naive assignment of the result to the public IOMemoryMap or
IOBufferMemoryDescriptor virtual at that offset; they do not exclude a private
subclass or an adapter.

To close the chain, recover the runtime AppleARMIODevice vtable from the
prelinked class construction/relocations (or its exact slot's pointer in the
full kernelcache), then follow the `+0x5e8` return class construction to its
vtable. Only after that should the backing `+0x140` result be assigned an
address domain or equated with a GPU-visible address.

Evidence inputs: `artifacts/live/private/gpu-offline/kexts.json`,
`ios81-init-allocation.c`, `ios81-ring-allocator.c`, `ios81-agx-disasm.txt`,
the kernelcache `nm -m` exports and vtable bytes, and the Ghidra 12.1.4
headless project `armplatform` run with OpenJDK 21 per
`tools/ghidra/README.md`.
