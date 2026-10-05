# J81 PCIe DART: no `0xbffff000` whitelist, but the doorbell sits just above the DART's IOVA window

Date: 2026-10-05. Static only (kernelcache 12B410 `AppleS5L8960XDART`/`IODARTFamily`, plus the
saved J81 ADT); follow-up to `2026-10-05-j81-msi-message-provider-trace.md`. Question: does the
DART kext whitelist or special-case `0xbffff000`?

## Result 1: no whitelist in the DART kext

- No literal `0xbffff000` (or `0xbffff0xx`) anywhere in the 14 MB `__PRELINK_TEXT` as data. The
  only `movz #0xbfff, lsl #16` hits (5) are in unrelated kexts far from the DART code
  (`0x29abe70`, `0x2c9afe8`, `0x2cb15d8`, `0x2cb81d0`, `0x2cbc044`); none lies in the DART kext
  range (about `0x26b0000-0x26d0000`).
- The DART kext's J81-relevant properties are only: `vm-size`, `vm-offset`, `manual-availability`,
  `fetch-config`, `diag-config`, `error-reflector`, `bypass-address`, `dart_version`,
  `no-fault-clients`, `soft-fault-clients`. None names an MSI address.

## Result 2 (new, structural): the doorbell is the page right above the DART window

The saved J81 ADT node `dart-apcie1` has `vm-offset` = `0x80000000` (first dword of
`00 00 00 80 00 00 00 08`) and `vm-size` = `0x3ffff000`. The kext's `start` (`FUN_ffffff80026c316c`,
properties read at `0x26c353c`/`0x26c35c4`) turns both into 4 KiB page counts (`value >> 12`) for
its VM space. So Apple's translated IOVA window for this controller is

```
[0x80000000, 0x80000000 + 0x3ffff000) = [0x80000000, 0xbffff000)
```

and `0xbffff000` (the ADT `msi-address`) is **exactly its end**: the last 4 KiB page of the 1 GiB
region `0x80000000-0xc0000000` is the MSI doorbell, everything below it is DART-translated. That
explains why no register or whitelist is needed: the doorbell is carved out by address layout (the
PCIe inbound decode / DART window), consistent with design reading 2 (hardware-fixed).

Caveat: the second dword of `vm-offset` (`0x08000000`) is unexplained (the kext reads one 32-bit
value and requires a 4-byte property), and the exact fabric point that routes the page was not
found statically. The window arithmetic is solid; the routing mechanism is still inferred.

## Consequence for the Linux driver (open, needs a decision)

- `0055` reserves only the doorbell page (`IOMMU_RESV_MSI` at `0xbffff000`). Stock `apple-dart`
  otherwise lets the DMA layer allocate IOVAs anywhere in its 32-bit space (it reported
  `AS 32 -> 36`), and dma-iommu allocates top-down, i.e. near `0xffffffff`. On J81 that is
  **outside Apple's window**; whether such IOVAs would still translate is unknown, but Apple never
  uses them.
- Safest model: restrict the J81 PCIe DART's aperture to `[0x80000000, 0xbffff000)` (e.g. extra
  `IOMMU_RESV_RESERVED` regions for `[0, 0x80000000)` and `[0xc0000000, 4 GiB)` from the same
  per-controller DT hook that `0055` added, or an explicit geometry). This matters before any DMA
  (the future `brcmfmac` firmware gate), not for the MSI configuration path tested so far.
- No hardware needed to write the patch, but it must be validated by a DMA-capable endpoint test;
  until then treat it as a proposal (`0060`).

## Method note

DART property reads were located with `tools/ghidra/find_adr_refs.py` (string references use
`ADR`), then `tools/ghidra/DecompTo.java`.

## `0060` drafted (2026-10-05, proposal; not hardware-tested)

`kernel/patches/0060-apple-dart-per-controller-iova-window.patch` (on top of `0055`/`0057`):

- new controller DT property `apple,iova-window = <start_hi start_lo end_hi end_lo>` (J81:
  `<0x0 0x80000000 0x0 0xbffff000>`), binding documented as `uint64-array`, 2 items;
- `apple_dart_get_resv_regions()` additionally reserves, as `IOMMU_RESV_RESERVED`, everything in
  `[0, 2^ias)` outside the window for PCI devices behind that controller: `[0, 0x80000000)` and
  `[0xc0000000, 4 GiB)` (the upper gap starts above the doorbell page, which keeps its own
  `IOMMU_RESV_MSI` region from `0055`, so reservations never overlap);
- without the property nothing changes (M1 and the global-doorbell fallback keep their behaviour);
  the DART hardware is not touched.

Host evidence: the pure gap helper is extracted from the patched driver and compiled; window +
doorbell page + gaps tile `[0, 4 GiB)` exactly for J81, and degenerate inputs (empty, reversed,
past-top window) produce no reservation (`kernel/test_apple_dart_iova_window_patch.py`, 9 cases,
registered in `tools/check_offline.py` via `--pcie-j81-selftest-source`). Kernel
variant: `hoolock-pcie-j81-iova-kernel` (0052-0057 + 0060), a compile gate only.

Not established: that IOVAs outside Apple's window really fail on J81 (the premise), or that
the window is exactly 1 GiB-minus-a-page in hardware rather than only Apple's software
allocation range. Validation needs a DMA-capable endpoint test (the firmware gate); do not
merge into the production payload before that.

### `0060` compile result (2026-10-05)

`hoolock-pcie-j81-iova-kernel` (0052-0057 + 0060) builds cleanly; `apple-dart.o` compiles against
the real kernel headers and the kernel `Image` contains the `apple,iova-window` lookup. The first
attempt failed only because the builder's disk was full (`rsync` broken pipe during install);
a plain retry after Nix's auto-GC succeeded. Still a proposal: no payload built, nothing booted.
