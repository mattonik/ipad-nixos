# iPadOS 15 cross-check of J81 mapping selectors

The local 19H422 G4G decompilation uses the same selector families as the
8.1 J81 path, but the view-object ABI has moved:

- `0x80007` is used for the main firmware/GPU allocation;
- `0x70007` is used for the alternate firmware-preparation allocation;
- the returned view is checked through its `+0x98` method in iPadOS 15 (the
  8.1 equivalent is `+0x80`/`+0x90` depending on the object).

The selectors are therefore stable role identifiers across releases, while
the vtable offsets are not. The high selector field is still coupled to the
allocation/view class; it cannot be reduced to a Linux cache flag. This
cross-version match supports keeping J81's four view bases and selector role
explicit in any future adapter, but does not reveal the A8X physical address
or cache implementation.

Evidence is from `artifacts/live/private/gpu-offline/ios15-g4g-preprobe.c` and
the corresponding 8.1 `ios81-init-allocation.c`; no firmware or device access
was involved.
