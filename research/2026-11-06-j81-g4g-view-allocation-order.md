# J81 G4G view allocation order (offline)

The iOS 8.1 `FUN_ffffff80032998d8` trace resolves the first four provider
views used by the G4G setup. Each allocation uses the same provider map
selector `0x80007`, allocator flags `0x22`, page-aligned size, and then calls
the map object's address method. The allocation order is:

| view | source size | mapping metadata | packed image offset |
|---:|---:|---|---:|
| 0 | `param_1[3] * 0x6c`, minimum `0x2000` | selector `0x80007`, flags `0x22` | `0x00000` |
| 1 | `param_1[4] * 0x6c`, minimum `0x2000` | selector `0x80007`, flags `0x22` | `0x0f000` |
| 2 | `param_1[5] * 0x6c`, minimum `0x2000` | selector `0x80007`, flags `0x22` | `0x13000` |
| 3 | `param_1[6] * 0x3594`, minimum `0x2000` | selector `0x80007`, flags `0x22` | `0x14000` |

The first three views allocate a 64-byte-per-entry host table after mapping;
the fourth allocates the larger `0x3594`-byte-per-entry firmware structure.
The trace repeats the same pattern for later auxiliary allocations, but those
are not part of the four packed J81 image views.

This closes the static view count, order, size formulas, selector, and cache
flags. It does **not** recover runtime CPU/device base addresses or DART
ownership: those still depend on the provider map object's `+0x80` address
method and the descriptor-backed `+0xa8` path. No firmware bytes were copied
and no hardware access was performed.

