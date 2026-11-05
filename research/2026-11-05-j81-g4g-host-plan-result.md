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

## Decision

This is enough to start an offline Apple-host-layout adapter and comparison
harness. It is not enough to upload the image: address-domain translation,
thread-start semantics, shared-memory ownership, and the firmware-alive
handshake remain unresolved. No device operation is justified by this result.

