# J81 private accelerator mapping wrapper

The helper behind the J81 `0x90007` view path is at
`0xffffff800326e084` in `IOAcceleratorFamily2`.  Its behavior is now clear
from the standalone kext disassembly:

1. accept an accelerator object, a zero/optional selector, and an
   `IOMemoryDescriptor`;
2. query the descriptor's length through its vtable;
3. compare that length with provider limits obtained from accelerator vtable
   slots `+0x608` and `+0x598`;
4. allocate a wrapper object through the provider;
5. retain the descriptor at wrapper offset `0x80`, save the selector and
   length/offset fields at `0x38`/`0x40`, clear its state word, and increment
   the provider's wrapper count.

The J81 caller then invokes wrapper vtable `+0x90` with the kernel task and
private selector `0x90007`.  The allocator itself performs no GPU MMIO,
DART-table write, or firmware operation.  This narrows the unresolved DART
question to the wrapper's `+0x90` implementation and its device-address
policy; replacing it with a generic Linux DMA mapping would still be an
unsupported assumption.
