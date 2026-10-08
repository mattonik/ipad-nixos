#!/usr/bin/env python3
"""Contract for the Wi-Fi H1B base payload variant (no hardware, no build).

The first private-firmware transport run must use exactly the known-good host path (0052-0057) plus
DMA model A (0063 + 0064), with brcmfmac PCIe built in. It must not contain 0060 (the superseded
allocator-only proposal), the probe/self-test/shadow/diag drivers, or any firmware in the public
outputs.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
NIX = (ROOT / "kernel" / "hoolock-pcie-j81-wifi-h1b.nix").read_text()
NIX_RAW = (ROOT / "kernel" / "hoolock-pcie-j81-wifi-h1b-raw.nix").read_text()
FLAKE = (ROOT / "flake.nix").read_text()

EXPECTED_TAIL = [
    "0016-pcie-apple-t7000-compile-only-skeleton.patch", "0040-pcie-apple-t7000-tuning-baseline-test.patch",
    "0041-pcie-apple-t7000-dbi-ecam-read-test.patch", "0042-pcie-apple-t7000-dbi-tunables-write-test.patch",
    "0043-pcie-apple-t7000-link-state-probe-test.patch", "0044-pcie-apple-t7000-link-wait-write-test.patch",
    "0045-pcie-apple-t7000-link-speed-write-test.patch", "0052-pcie-apple-t7000-j81-reg-on.patch",
    "0053-pcie-apple-t7000-link-wait-dllla.patch", "0054-pcie-apple-t7000-clean-up.patch",
    "0055-apple-dart-per-controller-msi-doorbell.patch", "0056-pcie-apple-t7000-derive-msi-port-values.patch",
    "0057-pcie-apple-t7000-msi-domain.patch", "0063-apple-dart-pci-iova-window.patch",
    "0064-t7001-air2-pcie-iova-rebase.patch", "0065-brcmfmac-pcie-h1b-diag.patch",
    "0066-readonly-debugfs-diag-dart-and-t7000-port.patch", "0067-j81-wifi-deep-sleep-and-device-wake-toggles.patch",
    "0068-brcmfmac-h1b-console-poll-and-shared-state.patch",
    "0069-brcmfmac-h1b-chipcommon-gpio-snapshot.patch",
    "0070-brcmfmac-h1b-apple-shared-memory-parity.patch",
    "0071-brcmfmac-h1b-readonly-query-interface.patch",
    "0072-brcmfmac-h1b-ring-ids-and-safe-register-reads.patch",
    "0073-brcmfmac-h1b-query-snapshot-arm-and-gated-rom.patch",
]


def main():
    patches = re.findall(r'patch -d "\$out" -p1 < \$\{\./patches/([^}]+)\}', NIX)
    assert patches[-len(EXPECTED_TAIL):] == EXPECTED_TAIL, patches
    for banned in ("0058", "0059", "0060", "0061", "0062", "0018"):  # 0065 (brcmfmac diagnostics) is wanted
        assert not any(p.startswith(banned + "-") for p in patches), f"{banned} must not be in the Wi-Fi H1B kernel"
    m = re.search(r"patchedHoolockPcieJ81WifiH1bConfig = .*?\n          '';", FLAKE, re.S)
    assert m, "config derivation missing"
    cfg = m.group(0)
    for line in ("CONFIG_WIRELESS=y", "CONFIG_CFG80211=y", "CONFIG_WLAN=y", "CONFIG_WLAN_VENDOR_BROADCOM=y",
                 "CONFIG_BRCMUTIL=y", "CONFIG_BRCMFMAC=y", "CONFIG_BRCMFMAC_PCIE=y", "CONFIG_BRCMDBG=y",
                 "CONFIG_BRCMFMAC_PCIE_H1B_DIAG=y", "CONFIG_APPLE_DART_H1B_DIAG=y", "CONFIG_PCIE_APPLE_T7000_DEBUGFS_DIAG=y", "CONFIG_PCIE_APPLE_T7000_DEVICE_WAKE_TEST=y", "CONFIG_FW_LOADER_USER_HELPER_FALLBACK=n", "CONFIG_FW_LOADER_USER_HELPER=n"):
        assert f"echo '{line}'" in cfg, line
    for banned in ("BCM_PROBE", "MSI_SELFTEST", "DIAG_MSIADDR", "BRCMFMAC_SDIO=y", "BRCMFMAC_USB=y"):
        assert banned not in cfg, banned
    # Model B (raw) is the same list without 0064 and nothing else.
    raw = re.findall(r'patch -d "\$out" -p1 < \$\{\./patches/([^}]+)\}', NIX_RAW)
    # Model B was built before 0067/0068 existed and is the plain comparison payload: no 0064, 0067, 0068, 0069.
    assert raw == [p for p in patches if not p.startswith(("0064-", "0067-", "0068-", "0069-", "0070-", "0071-", "0072-", "0073-"))], raw
    assert not any(p.startswith("0064-") for p in raw)
    raw_pay = re.search(r"m1n1-hoolock-pcie-j81-wifi-h1b-base-raw = mkJ81BasePayload \{.*?\n        \};", FLAKE, re.S)
    assert raw_pay and "hoolockPcieJ81WifiH1bRawKernel" in raw_pay.group(0) and "brcmfmac.debug=0x001c0004" in raw_pay.group(0)
    pay = re.search(r"m1n1-hoolock-pcie-j81-wifi-h1b-base = mkJ81BasePayload \{.*?\n        \};", FLAKE, re.S)
    assert pay, "payload missing"
    body = pay.group(0)
    assert "hoolockPcieJ81WifiH1bKernel" in body and "brcmfmac.debug=0x001c0004" in body
    base = re.search(r"mkJ81BasePayload = .*?\n            '';\n", FLAKE, re.S).group(0)
    assert "firmware" not in base.lower().replace("brcmfmac", ""), "no firmware may be copied into the public payload"
    assert "rdinit=/init" in base and 'deviceinfo_usb_rndis_function="ecm.usb0"' in base, "USB recovery must stay"
    print("PASS: Wi-Fi H1B base contracts (model A and B: host path 0052-0057 + 0063 (+0064), 0065/0066 diagnostics, no 0060/probe drivers, brcmfmac PCIe, no firmware, USB recovery)")


if __name__ == "__main__":
    main()
