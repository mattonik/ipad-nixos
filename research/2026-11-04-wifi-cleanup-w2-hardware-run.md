# Wi-Fi cleanup W2: hardware run (2026-11-04)

Branch `wifi-cleanup-w2`. Patch `0123` describes the PCIe DART window with the pinned
kernel's own five-cell `iommu-map` specifier (`#iommu-cells = <5>` on `dart_apcie1`,
`iommu-map = <0x100 &dart_apcie1 0 0x0 0x80000000 0x0 0x3ffff000 1>`), as OrchardLinux's
J81 DT does, and removes `apple,iova-window`, `apple,iova-rebase` (PCIe node) and
`apple,pci-alias` (DART). The S5L8960X domain still rebases to the window start
(`mask = ~dma_min`); the raw-index alias mapping of `0080` is no longer made. The code
of `0063/0064/0076/0080` stays in the tree, unused. Plan: `research/2026-11-01-orchardlinux-org-review.md`.

## Off-device checks

- `j81-dtbs-check`: 10 warnings, 0 new after review. The one added warning is
  `pci-iommu.yaml` reading the window base as an entry length (the schema assumes a
  one-cell specifier); documented in `kernel/dtbs-check/t7001-j81.known-warnings`.
- `j81-kunit`: 23 tests, 22 passed, 1 skipped (the known echo-matcher SKIP).
- `tools/check_offline.py` on 2026-11-02 main: the same 2 failures with and without
  W2 (touch-diag frames, payload contract firmware assertion), since fixed on main.
- Built DTB: `iommu-map` = `100 1e 0 0 80000000 0 3ffff000 1`, `#iommu-cells` = 5,
  `apple,iova-window` and `apple,pci-alias` absent (fdtget).

## Hardware run

Payload `m1n1-hoolock-wifi-nixos` (public `/nix/store/mlqs6js8...-ipad-air2-m1n1-hoolock-wifi-nixos`),
assembled privately with `--production` (run id `5ad3ddabf8b1d5d1657c71a2044c5d80`),
NixOS root from the unchanged `gcroot-nixos-ram-serve`. One DFU cycle, booted by Martin.

| Check | Result |
|---|---|
| DART probe | `J81 PCIe DART options: ios-pte 1 pci-alias 0 apple-init 1` |
| NixOS hand-off | running |
| USB ssh | works |
| Association | 5 GHz, signal -60 dBm, rx 650 / tx 351 Mbit/s |
| DHCP | 192.168.0.205 |
| Download | 100 MB HTTPS in 2.7 s, about 309 Mbit/s |
| 5-minute soak | ping gateway 300/300, 0% loss, avg 2.6 ms, max 15 ms; still associated |
| dmesg | no DART fault, no brcmfmac error/timeout, no deauth/disassoc |

**Result: no regression. The raw-index alias mapping (`apple,pci-alias`, `0080`) is not
needed**, which closes the open question from the H1B work. The window works through the
pin's five-cell specifier alone. Next: delete the now-unused `0063`/`0064`/`0076`/`0080`
code (a pure cleanup, needs one more build and a short run).
