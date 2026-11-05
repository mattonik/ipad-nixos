# J81 G4G host-plan result (2026-11-05)

The private 8.1 kernelcache contains the G4G firmware image as the
`AGXFirmwareKextG4G` `__TEXT.__const` span described in the offline trace:

* virtual address: `0xffffff8002e39327`;
* length: `0x16cd8` (93,400 bytes);
* extracted artifact: ignored
  `artifacts/live/private/gpu-offline/g4g81-image.bin`;
* SHA-256: `314454e8d3179c255d704b6e481f971502bf7ec32f2a21b1345c6c8ba63534b8`.

The new offline tools processed that real image without executing or exposing
its payload bytes:

```
python3 tools/gpu_ldr_inspect.py artifacts/live/private/gpu-offline/g4g81-image.bin --report
python3 tools/gpu_g4g_host_plan.py artifacts/live/private/gpu-offline/g4g81-image.bin
```

The resulting metadata is kept ignored under
`artifacts/live/private/gpu-observations/`.

## Observed host contract

| Item | Result |
|---|---:|
| Load records / copied bytes | 58 / 85,980 |
| Zero records / zero bytes | 14 / 14,028 |
| META config writes | 27 |
| Start-thread entries | 2 |
| Apple 8.1 core-guard zero starts | 3 |
| Apple 15.8.8 core-guard zero starts | 3 |

The two thread records use fields beginning at `0x8000b288` and `0x8000a288`,
which lie in the guarded core-memory region. The three guarded zero ranges
therefore are not incidental metadata; they intersect the thread setup that
Apple preserves/handles specially. Linux's generic META loader cannot be
treated as equivalent until this behavior is reproduced or deliberately
replaced with a proven host layout.

The 27 config targets are all META-space addresses, including segment/cache
and thread-control registers such as `0x048000e8` and the `0x04830200` range.
The report confirms the inner stream is structurally usable, but every plan
operation remains marked `review-only` and `execution_allowed=false`.

## Region buckets

The host-plan generator now classifies each region without interpreting its
payload. The real image contains:

| META address class | Load | Zero |
|---|---:|---:|
| low/local-global | 50 | 7 |
| global alias | 5 | 4 |
| core code (`0x80000000`–`0x81ffffff`) | 3 | 3 |
| core data (`0x82000000`–`0x83ffffff`) | 0 | 0 |

No region crosses the core-code boundary. This sharply narrows the offline
adapter: it needs separate handling for three core-code loads and three
Apple-skipped core-code zero ranges, while the remaining low/global records
can be compared against Linux's ordinary firmware segments. It still does
not establish which physical allocation backs any bucket.

The Apple four-slot selector is now modeled exactly: for addresses at least
`0x08000000`, except the `0x80000000`–`0x87ffffff` core window,
`apple_segment_index = (address >> 29) & 3`. The real image uses all four
slots:

| Apple slot | Regions | Bytes |
|---:|---:|---:|
| 0 | 44 | 60,452 |
| 1 | 13 | 14,484 |
| 2 | 1 | 56 |
| 3 | 8 | 4,096 |

This narrows the Linux mapping work to four concrete segments plus the
core-code bucket; it does not yet prove the ownership of slot 1.

Slot 0 starts at `0x10000000`, Linux's META data base, so it maps strongly to
`FW_DATA`. The thread-0 record's third word is also `0x10000000`. Slot 2 starts at `0xc0000000`, Linux's
`ROGUE_FW_BOOTLDR_DEVV_ADDR_0`, so it maps strongly to the META bootloader.
Slot 3's `0xe0000000` alias masks to `0x60000000`, Linux's uncached META data
alias, and also maps strongly to `FW_DATA`. Slot 1 starts at `0x20000000`, and
the thread-1 record's third word points at that exact base. That is evidence
for a private-data/stack allocation, not proof of code; its Linux owner remains
unresolved because the generic driver exposes only one ordinary `FW_DATA`
allocation. The iOS 8.1 initializer separately allocates several buffers and
obtains paired views for each, so a future adapter must model allocation
classes explicitly rather than aliasing every Apple segment to one Linux
object.

The model now emits Linux mapping candidates: `core-code` and `core-data` map
to `FW_COREMEM_CODE`/`FW_COREMEM_DATA` as candidates, while the low/global and
global-alias buckets remain explicitly unresolved. This is intentional: those
aliases can select different Apple segment owners, and guessing `FW_CODE` or
`FW_DATA` would make a later firmware test unsafe.

The new allocation model computes the metadata-only bucket extents:

| Bucket | Regions | Total bytes | Address span |
|---|---:|---:|---|
| low/local-global | 57 | 74,936 | `0x10000000`–`0x20003898` |
| global alias | 9 | 4,152 | `0xc0000000`–`0xe0002000` |
| core code | 6 | 20,920 | `0x80000000`–`0x8000c288` |

It produces 3 `skip` and 11 `zero` actions under the Apple 8.1 guard. These
are allocation requirements and policy decisions only; the model deliberately
does not choose physical backing, translate addresses, or start threads.

## Decision

This is enough to start an offline Apple-host-layout adapter and comparison
harness. It is not enough to upload the image: address-domain translation,
thread-start semantics, shared-memory ownership, and the firmware-alive
handshake remain unresolved. No device operation is justified by this result.

