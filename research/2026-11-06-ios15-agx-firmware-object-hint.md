# iPadOS 15 AGX firmware-object hint

The local iPadOS 15 AGX decompilation provides one useful host-side constraint for future J81 work. In `artifacts/live/private/gpu-offline/ios15-fw-objects.c`, the AGX setup path copies eight independent descriptor triples from the AGX state object into a host object. The source entries are at state offsets:

`0xed0`, `0xee8`, `0xf00`, `0xf18`, `0xf30`, `0xf48`, `0xf60`, and `0xf78`.

Each entry contributes an address-like 64-bit value and a 32-bit size; the destination records are spaced 0x10 bytes apart, with a zeroed status word between entries. The same path also copies a separate `0x1ba8`-relative value and a mask into the tail of the host object.

This is evidence that newer AGX hosts model more than the four physical views recovered from the J81 iOS 8.1 initializer. It is not evidence that J81 requires eight views, nor that the iPadOS 15 object layout can be reused on G4G. The actionable constraint is to keep any future J81 host model explicit about descriptor count and ownership rather than silently assuming that four view registrations are the complete firmware ABI.

No firmware bytes were imported into this note and no execution path is enabled.
