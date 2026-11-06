# J81 SGX ADT: negative DART binding result

The recovered iOS 8.1 J81 device tree (`artifacts/live/private/gpu-offline/ios81-dt.json`)
contains one `arm-io/sgx` node with `compatible = "gpu,t7001"` and two register windows:

| ADT offset | size | resolved physical window |
| ---: | ---: | ---: |
| `0x01000000` | `0x00100000` | `0x201000000..0x201100000` (GPU core) |
| `0x01e00000` | `0x00100000` | `0x201e00000..0x201f00000` (GPC/Fender) |

Unlike the display, scaler, ISP, JPEG, and PCIe nodes, `sgx` has no `iommu-parent`,
DART phandle, VM offset, VM size, or stream/RID property. This is a negative
architectural result: the public ADT does not describe a GPU DART client. The
four iOS firmware allocations therefore cannot be assigned a Linux DART stream
or aperture from ADT evidence alone.

Keep the G4G/DART plan validation-only and execution-disabled. Do not add a
guessed `apple-dart` node or program a DART table until a firmware-owned path is
identified in AGX or a controlled hardware observation proves one exists.

Evidence: `ios81-dt.json`, `ios81-init-caller.c`, `ios81-memory-registration.c`,
and `research/2026-11-04-j81-gpu-offline-trace.md`.
