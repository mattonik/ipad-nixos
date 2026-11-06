# J81 Apple allocation classes

The recovered iOS 8.1 initializer at `0xffffff80032998d8` allocates several
independent aligned objects. The primary pair is created separately for two
address views; later allocations create additional GPU-side structures and
map each through their own `+0x90`/`+0x140` calls. The firmware descriptor is
filled from one of these driver-owned structures, not from the single packed
`FW_DATA` object used by Orchard.

This is direct evidence against collapsing every Apple low/global region into
one Linux allocation. The safe adapter must preserve allocation-class identity
until each descriptor field's consumer is identified. The current model's
packed extents remain useful for address arithmetic only.

No allocation was performed by the Linux test image; this is static evidence
from the private iOS decompilation.
