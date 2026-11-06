# J81 GPC control-list boundary

The first post-handshake writes are made by small host helpers, not by a GPU
render command path:

- `0xffffff80032a1cc8` stores one 32-bit value into the mapped GPC object;
- `0xffffff80032a1f4c` writes the GPC control word at offset `0x20000`;
- `0xffffff80032a1f84` writes `0x40000000` at the GPC base;
- `0xffffff80032a2008` appends a four-word control record containing a target
  offset, high address word, flags, and low address word;
- `0xffffff80032a2160` appends the `0xffff0000` end marker.

The post-LDR routines use these helpers for META/GPC startup and teardown. They
are useful for an execution-free ordering model, but they do not identify a
GPU render ring, DART IOVA, or command-buffer ABI. The real render boundary is
still later and remains unresolved.
