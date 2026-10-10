#!/usr/bin/env python3
"""The J81 base package contract (docs/plans/2026-10-08-j81-base-package.md). No hardware, no build.

Every payload meant to be run on the iPad must keep: (1) charging, (2) telnet + SSH, (3) the debug console, (4) the tablet tools,
(5) the universal probe. This test makes dropping one of them fail the offline suite:
  * BASE_KERNELS (kernel recipes used by payloads built through mkJ81BasePayload) must apply the base patch set, in order;
  * the flake's mkJ81BasePayload must install the base overlay pieces and the standard bootargs;
  * every payload output listed in BASE_PAYLOADS must be defined through mkJ81BasePayload;
  * the payload verifier's j81_base_problems() accepts a good synthetic payload and flags each missing piece.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "boot"))
import verify_pcie_j81_reg_on_payload as V  # noqa: E402

FLAKE = (ROOT / "flake.nix").read_text()
BASE_PATCHES = [
    "0001-t7001-add-uart3-node.patch", "0002-t7001-air2-enable-uart3.patch", "0003-serdev-add-stop-bit-selection.patch",
    "0004-add-bq27xxx-hdq-uart-frontend.patch", "0005-t7001-add-uart5-node.patch", "0006-t7001-air2-enable-uart5-battery.patch",
    "0010-j81-d2207-readonly-charger.patch", "0007-spi-apple-add-s5l8960x-support.patch", "0008-t7001-add-spi3-node.patch",
    "0009-t7001-air2-enable-spi3.patch", "0011-touchscreen-apple-z2-add-j81.patch",
    "0017-j81-d2207-charger-writable-input-current-limit.patch",
]
BASE_KERNELS = ("kernel/hoolock-pcie-j81-wifi-h1b.nix", "kernel/hoolock-pcie-j81-wifi-h1b-raw.nix")
BASE_PAYLOADS = ("m1n1-hoolock-pcie-j81-wifi-h1b-base", "m1n1-hoolock-pcie-j81-wifi-h1b-base-raw")


def check_kernels():
    for rel in BASE_KERNELS:
        patches = re.findall(r'patch -d "\$out" -p1 < \$\{\./patches/([^}]+)\}', (ROOT / rel).read_text())
        assert patches[:len(BASE_PATCHES)] == BASE_PATCHES, f"{rel} does not start with the J81 base patch set: {patches[:14]}"


def check_flake():
    m = re.search(r"mkJ81BasePayload = .*?\n            '';\n", FLAKE, re.S)
    assert m, "mkJ81BasePayload is missing from flake.nix"
    body = m.group(0)
    for needle in ("ssh-stage1.sh", "charging-policy.sh", "tablet-status.sh", "tablet-dashboard.sh", "ssh/authorized_keys",
                   "dropbearClosure", "deviceinfo_usb_rndis_function=\"ecm.usb0\"", "/usr/bin/charging-policy",
                   "console=tty0", "ignore_loglevel", "rdinit=/init", "PMOS_NO_OUTPUT_REDIRECT", "pd_ignore_unused",
                   "clk_ignore_unused", "20-debug-shell.sh"):
        assert needle in body, f"mkJ81BasePayload lacks {needle}"
    for banned in ("btattach", "i2cTools"):
        assert banned not in body, f"mkJ81BasePayload must not include {banned}"
    # Item 6 (Wi-Fi): the generic userland is part of the base when `wifi` is set, and comes only from the flake package (never the credentials).
    assert "wifi ? false" in body, "mkJ81BasePayload needs the optional wifi argument"
    for needle in ("wifiUserlandPkg", "wifi-up.sh", "wifi-udhcpc.script", "/usr/bin/wifi-up", "[ -x /usr/bin/wifi-up ]", "wireless-regdb"):
        assert needle in body, f"mkJ81BasePayload lacks the Wi-Fi piece {needle}"
    for secret in ("wpa_supplicant.conf", "wifi-credentials", "psk="):
        assert secret not in body, f"mkJ81BasePayload must not carry {secret}"
    for needle in ("dashboard ? false", "tablet-dashboard-screen.sh", "[ -x /usr/bin/tablet-dashboard-screen ]"):
        assert needle in body, f"mkJ81BasePayload lacks the dashboard piece {needle}"
    prod = re.search(r"m1n1-hoolock-wifi = mkJ81BasePayload \{.*?\n        \};", FLAKE, re.S).group(0)
    assert "dashboard = true;" in prod and "fbcon=font:TER16x32" in prod, "the production base must start the dashboard on a 16x32 console font"
    assert "CONFIG_FONT_TER16x32=y" in FLAKE
    assert re.search(r"m1n1-hoolock-wifi = mkJ81BasePayload \{[^}]*wifi = true;", FLAKE, re.S), "m1n1-hoolock-wifi must be the base with wifi = true"
    for name in BASE_PAYLOADS:
        assert re.search(rf"\n        {re.escape(name)} = mkJ81BasePayload \{{", FLAKE), f"{name} is not built through mkJ81BasePayload"


def check_verifier():
    hook = b"telnetd -b x\nDB=/nix/store/abc-dropbear\n/usr/bin/charging-policy >/dev/null &\nloop_forever\n"
    entries = {n: (0o100755, b"x") for n in V.J81_BASE_EXECUTABLES}
    entries["etc/postmarketos-mkinitfs/hooks/20-debug-shell.sh"] = (0o100755, hook)
    entries["root/.ssh/authorized_keys"] = (0o100600, b"ssh-ed25519 AAAA test\n")
    entries["nix/store/abc-dropbear/bin/dropbear"] = (0o100755, b"x")
    image = b"..j81-d2207-charger.."
    args = "console=tty0 loglevel=8 ignore_loglevel rdinit=/init PMOS_NO_OUTPUT_REDIRECT pd_ignore_unused clk_ignore_unused"
    assert V.j81_base_problems(entries, image, args) == []
    for name in list(entries):
        broken = dict(entries)
        del broken[name]
        assert V.j81_base_problems(broken, image, args), f"missing {name} not detected"
    assert V.j81_base_problems(entries, b"no charger", args)
    for token in V.J81_BASE_BOOTARGS:
        assert V.j81_base_problems(entries, image, args.replace(token, "")), token
    nohook = dict(entries)
    nohook["etc/postmarketos-mkinitfs/hooks/20-debug-shell.sh"] = (0o100755, b"telnetd\n")
    assert len(V.j81_base_problems(nohook, image, args)) >= 2
    notexec = dict(entries)
    notexec["usr/bin/charging-policy"] = (0o100644, b"x")
    assert V.j81_base_problems(notexec, image, args)


def main():
    check_kernels()
    check_flake()
    check_verifier()
    print("PASS")


if __name__ == "__main__":
    main()
