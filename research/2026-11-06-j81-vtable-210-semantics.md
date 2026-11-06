# J81 accelerator vtable `+0x210`

The ARM64 call site in `0xffffff800329e63c` resolves the unknown slot exactly:

```text
x0 = AGX accelerator object
x1 = mapped preparation-object base + four indexed offsets
x2 = index 0..3
```

The slot is invoked four times before the Apple LDR copy/verify routine. It is
therefore a setter/registration method for four address views, not a generic
GPU-address translation function and not an MMIO operation. The four offsets
come from the initializer's host layout calculator (`param + 0x524`).

This explains the remaining mismatch with Orchard: Apple registers four
per-view addresses in an accelerator object before loading the LDR, whereas
Orchard derives its FW-object addresses directly from layout entries and a
single FW-data allocation. A safe adapter must model these registrations
explicitly or reject the image.

No firmware was executed and no device state changed.
