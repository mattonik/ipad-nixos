# J81 boot-descriptor boundary

The iOS 8.1 thread setup builds a second host-side descriptor after the GPC
control list. It records six fixed address-class values:

`0x400000000`, `0x500000000`, `0x100000000`, `0x100000000`,
`0x600000000`, and `0x700000000`, followed by the optional controller value
and the bootloader address `0xe1c0000000`.

It then calls the accelerator address-view hook (`+0x140`) repeatedly and
stores the translated 32-bit values in the descriptor's view table. This is
still boot metadata construction: there is no render submission, GPU fence,
doorbell, or DART programming in this routine. The exact meaning of the six
classes and their Linux equivalents remains unresolved, so the simulator only
reviews their ordering and keeps execution disabled.
