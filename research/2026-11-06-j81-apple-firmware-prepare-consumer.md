# J81 Apple firmware-prepare consumer

The recovered `0xffffff800329e63c` preparation routine consumes the parsed
layout rather than passing the six-word descriptor directly to META. It:

1. allocates a separate aligned firmware-preparation object;
2. obtains its mapped view;
3. writes four indexed address values through the accelerator vtable at
   `+0x210`;
4. invokes the LDR copy/verify routine `0xffffff800329fbe8`;
5. appends boot/config words and translated object addresses.

This identifies the next Apple-specific boundary: vtable `+0x210` is the
address-view/descriptor consumer that must be resolved before an Orchard
adapter can be designed. The LDR parser and packed extents alone are not
enough.

No firmware was executed and no hardware state was changed.
