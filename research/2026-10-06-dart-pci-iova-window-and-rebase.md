# DART PCI IOVA window and Apple rebase: test candidates 0063/0064 (plan phase 2), built offline only

Date: 2026-10-06. Implements the "isolated test mapping model" of plan phase 2, after the static
trace in `2026-10-06-pcie-msi-delivery-review.md`: Apple's DART uses `vm-offset`/`vm-size` as a
software allocator window and subtracts `vm-offset` before every page-table operation (endpoint
`0x80000000` is DART page 0). **Nothing was booted. These are proposals; `0060` is superseded by
`0063` (do not combine; both define `apple,iova-window`).**

## Finding that shaped the design

Hoolock's `apple-dart` already supports this for `apple,s5l8960x-dart`: the DMA aperture comes
from the iommu specifier (`<sid dma_min_hi dma_min_lo len_hi len_lo>`), the domain geometry is forced
to it, and `mask = ~dma_min` clears `dma_min`'s bits before the page-table call, which is exactly
Apple's subtraction when the window lies inside the block opened by `dma_min`'s lowest set bit
(`0x80000000`). But a PCI device behind `iommu-map` carries only one specifier cell, so Linux
never gets a window for J81's endpoint: today it uses `dma_min = 0` (no rebase, aperture the whole
32-bit space).

## The patches

- `0063-apple-dart-pci-iova-window.patch` (driver + DT + binding): `apple,iova-window = <start end>`
  on the PCIe controller node (`<0x0 0x80000000 0x0 0xbffff000>` on J81). In `apple_dart_of_xlate()`
  a PCI device behind a controller with that property gets `dma_min/dma_max` from it (validated:
  page aligned, non-empty, inside the DART's address bits), so the existing code forces the
  aperture. Without `apple,iova-rebase` (below) the PTE index stays raw: `mask = full ias`.
  With the rebase, the existing `mask = ~dma_min` applies, guarded by `apple_dart_rebase_valid()`
  (the aperture must lie inside the block of `dma_min`'s lowest set bit, else finalize fails with
  `-EINVAL` instead of silently aliasing pages). Property-gated and PCI-only: other DART users and
  the existing S5L8960X `~dma_min` behaviour are untouched; the MSI doorbell reservation from `0055`
  is unchanged; no DART register is touched.
- `0064-t7001-air2-pcie-iova-rebase.patch` (DT + binding only): the boolean `apple,iova-rebase`.

Two models, one kernel difference:

| Model | Patches | Endpoint-visible `0x80000000` | PTE page |
| --- | --- | --- | --- |
| A, Apple rebase | `0063` + `0064` | window start | 0 |
| B, raw | `0063` only | window start | `0x80000` |

These are the two hypotheses plan phase 3 must discriminate with a real DMA-capable endpoint
(the APCIe-to-DART address conversion is the one boundary static analysis could not settle).

## Offline evidence

`kernel/test_apple_dart_pci_window_patch.py` (registered in `tools/check_offline.py`): text
contract (property-gated, PCI-only, no register access, no reserved-region approach, existing masks
kept as fallbacks and ordered after the new raw branch, rebase check only for window users, `0064`
touches no kernel code); zero-fuzz apply of `0063`+`0064` and of `0063` alone on the `0057` tree;
the two pure helpers compiled on the host: J81 window gives `[0x80000000, 0xbfffefff]`, the
rebase equals subtraction for every page of the window and puts the first window page at 0, the
raw mask leaves the IOVA unchanged, empty/reversed/unaligned/beyond-ias windows are refused, and
an aperture that would alias under the bit-clear rebase is rejected. Five deliberate bugs in the
helpers are caught. Payload verifier modes `--dma-rebase` and `--dma-raw` check the DTB window
`<0 0x80000000 0 0xbffff000>` and the presence/absence of `apple,iova-rebase`, and that the probe
and self-test drivers are absent. Offline suite: 39 passed, 0 failed, 7 skipped.

Not covered offline: that the kernel accepts the code on real DART hardware, the IOMMU core's
behaviour with a PCI aperture on this endpoint, and which model the fabric implements.

## Build gates (this note is updated with the results)

Kernel/payload outputs: `m1n1-hoolock-pcie-j81-dma-rebase` (model A) and
`m1n1-hoolock-pcie-j81-dma-raw` (model B). Only model A is built now (compile gate for the shared
driver change); neither is booted. Boot decisions belong to the DMA discrimination in plan phase 3,
which needs the firmware/NVRAM input from the proven OTP identity first.

## Build result (2026-10-06)

The first model A build failed to compile: `apple_dart_rebase_valid()` was defined after its first
use in `apple_dart_finalize_domain()` (the host harness cannot see use-before-define). Fixed in
`0063` (helper moved above its first use) and the test now asserts helper ordering. The rebuild
compiled cleanly:
`/nix/store/hplr7fcixmhbvwzc4isw2g3x87iyg1ca-ipad-air2-m1n1-hoolock-pcie-j81-dma-rebase`.
`--dma-rebase` passes (DTB `apple,iova-window` and `apple,iova-rebase` present, no probe drivers);
`--dma-raw` correctly rejects it. Model B (`m1n1-hoolock-pcie-j81-dma-raw`) is defined but not
built. Nothing booted.
