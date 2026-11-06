# J81 provider-map lifecycle around address materialization

The provider map object's adjacent methods show that its retained descriptor
is used for lifecycle state, not direct GPU programming:

- `+0x80` (`0xffffff800326d018`) returns `map+0x90` unless state bit 6 is
  set, in which case it delegates to the retained descriptor's `+0xa8`.
- `+0x88` (`0xffffff800326d094`) increments the map reference/preparation
  count and uses the retained descriptor/provider callback when needed.
- `+0x98` (`0xffffff800326d1d0`) releases the preparation state through the
  same descriptor/provider path.
- `+0xa0` (`0xffffff800326d220`) decrements the map reference count.

These paths update object state and call descriptor/provider virtual methods;
they contain no GPU MMIO or DART-table writes.  The only unclassified value
producer is the descriptor-specific `+0xa8` method used by the state-bit-6
branch of the address getter.
