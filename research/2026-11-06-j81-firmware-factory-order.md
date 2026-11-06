# J81 firmware factory ordering

The J81 preparation routine at `0xffffff800329e63c` is the concrete factory
chain preceding the unresolved start handoff:

1. allocate an aligned preparation object;
2. obtain its mapped view and register four translated firmware views through
   accelerator vtable `+0x210`;
3. copy and verify the LDR records with `0xffffff800329fbe8` on the CPU;
4. append boot/config words and translated object addresses.

The routine performs no GPU register writes, DART programming, or firmware
execution. Therefore the remaining `0xc0` virtual call in the descriptor
builder is a later controller/start boundary, not an omitted loader step. The
next static target is the concrete object/vtable used for that call; the safe
simulator must continue to stop before it.
