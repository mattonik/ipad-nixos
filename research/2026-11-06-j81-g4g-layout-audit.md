# J81 G4G host-layout audit

The current metadata-only model was run against the private J81 G4G image
(`artifacts/live/private/gpu-offline/g4g81-image.bin`). It maps all 72 load/zero
records into candidate Linux allocations (`all_fit=true`):

| candidate | base | aligned size |
|---|---:|---:|
| `FW_DATA` (segment 0) | `0x10000000` | `0xf000` |
| `FW_DATA` (segment 1 candidate) | `0x20000000` | `0x4000` |
| `META_BOOTLOADER` (segment 2) | `0x40000000` | `0x1000` |
| `FW_DATA` alias (segment 3) | `0x60001000` | `0x1000` |
| `FW_COREMEM_CODE` | `0x80000000` | `0xd000` |

The arithmetic fit result is useful but not sufficient for a firmware boot.
Orchard's `pvr_fw.c` accepts only `FW_CODE`, `FW_DATA`, `FW_COREMEM_CODE`, and
`FW_COREMEM_DATA` layout types; Apple's slot 2 is a separate
`META_BOOTLOADER` region with no matching Linux layout type. Therefore the
candidate is **not Linux-compatible yet**, despite all 72 records fitting its
packed extents. The physical
allocation behind each META bucket, Apple shared-memory address translation,
and ownership of the thread-start/alive handshake remain unresolved. The
model therefore remains execution-disabled; no firmware or device action is
authorized by this audit.

Offline command:

```text
python3 tools/gpu_g4g_apple_model.py artifacts/live/private/gpu-offline/g4g81-image.bin
```

Result: 72/72 records fit; `python3 tools/check_offline.py` remains clean.
