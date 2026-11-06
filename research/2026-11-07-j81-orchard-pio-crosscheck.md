# J81 physical-window cross-check from Orchard transport code

The local Orchard transport patch (`artifacts/live/private/gpu-offline/orchard-g5p-transport.patch`)
independently names the same physical windows seen in Apple's J81 resource
table.  Its PIO setup uses:

| Orchard PIO role | physical base | mapped size |
|---|---:|---:|
| Fender/GPC pages | `0x201e00000` | `0x5000` |
| AIC timer-side window | `0x20e100000` | `0x4000` |
| AIC software-interrupt window | `0x20e104000` | `0x4000` |
| GPU core window | `0x201000000` | `0x20000` |

This is consistent with Apple's four active `0x90007` resource records plus
the explicitly skipped `0x201000000` core record: the first two Apple GPC
records are adjacent pages that Orchard groups into one PIO span, while the
two `0x20e1…` records remain separate controller-side windows.  The Orchard
patch therefore strengthens address ownership and resource classification,
but it does not establish that its G5P transport, firmware, or PIO offsets
apply to J81's G4G/META path.

The cross-check is useful for Linux memory accounting only: keep the core
window separate from the four Apple firmware/resource descriptors, and do not
derive a DART aperture or GPU IOVA from these physical addresses.  No device
access or firmware execution was performed.

Evidence: Orchard patch sections around `g5p_make_init()` and the `c80758`
PIO mapping loop, plus `ios81-memory-registration.c` and the J81 resource
table documented in `research/2026-11-07-j81-resource-table-and-descriptor-dispatch.md`.
