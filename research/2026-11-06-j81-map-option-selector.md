# J81 map-option selector evidence

The private descriptor method at vtable offset `+0x90` is called with multiple high-bit selectors in the recovered code:

- `0x80007` for the repeated G4G allocation views;
- `0x70007` in the firmware-prepare path;
- `0x60005` for a GPC timestamp buffer.

All retain low direction bits, while the high fields vary by buffer role. This is direct evidence that the high field selects a mapping class or address-space policy rather than a simple cache mode or direction. It also means Linux cannot safely replace J81's `0x80007` with a generic DMA mapping flag: the selector is part of the Apple descriptor ABI.

The exact semantics of selectors `0x60000`, `0x70000`, and `0x80000` remain unresolved; no execution path is enabled.
