# Apple map-selector consumers

The call-site behavior distinguishes the selector roles even though their private names are unavailable:

- The firmware-prepare path maps with `0x70007`, then calls the returned map's `+0x80` to obtain an offset and adds four firmware-relative offsets before invoking the accelerator's `+0x210` registration hook.
- The initializer's four physical SGX resource records are visible in the
  iOS 8.1 constant table: `0x201e00000/0x2000`, `0x201e10000/0x1000`,
  `0x20e100000/0x2000`, and `0x20e104000/0x1000` (the last two are the
  interrupt-controller-side windows). These are host MMIO/resource views, not
  evidence of a GPU DART aperture.
- The GPC timestamp path first maps a buffer with `0x80007` and calls its `+0x90` prepare method, then maps a second buffer with `0x60005` and prepares that map as well.

Thus the selector changes which address/prepare contract the caller receives. `0x80000` cannot be modeled as a cache-only property; it participates in the Apple address-space contract. J81's four-view Linux plan must keep this selector unresolved until an equivalent mapper contract exists.
