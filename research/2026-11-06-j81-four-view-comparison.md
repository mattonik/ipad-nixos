# J81 Apple versus synthetic four-view comparison

The real `g4g81-image.bin` model and the complete synthetic four-view plan agree on all four recovered packed offsets:

`0x00000`, `0x0f000`, `0x13000`, and `0x14000`.

The comparison remains incompatible because the real Apple model has no proven Linux base address, ownership class, or cache mode for any view. Those are the only per-view differences in the metadata comparison; execution remains disabled. The model also retains the three global blockers:

- physical allocation backing each META bucket;
- Apple shared-memory address translation;
- firmware-alive and thread-start ownership.

This narrows the next offline task to recovering view attributes and lifetime, rather than revisiting the packed layout.
