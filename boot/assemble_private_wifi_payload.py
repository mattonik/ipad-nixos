#!/usr/bin/env python3
"""Assemble the PRIVATE Wi-Fi H1B test payload locally (stdlib only).

Takes the public base payload (built by Nix: kernel + DTB + initramfs, no firmware) and adds a
private initramfs overlay with the proven BCM4350 C2 `rieslinga` firmware, CLM, TxCap and the
selected NVRAM, under the canonical names the pinned brcmfmac loader requests when no
`brcm,board-type` exists in the device tree:

    lib/firmware/brcm/brcmfmac4350c2-pcie.bin         <- rieslinga.trx
    lib/firmware/brcm/brcmfmac4350c2-pcie.clm_blob    <- rieslinga.clmb
    lib/firmware/brcm/brcmfmac4350c2-pcie.txcap_blob  <- rieslinga.txcb
    lib/firmware/brcm/brcmfmac4350c2-pcie.txt         <- the tuple-selected NVRAM (whitespace-normalised)

The selection is made here, explicitly, from the OTP-proven identity (research/2026-10-06-bcm4350-otp-
parser-result.md); the driver is not asked to choose. The output (firmware, NVRAM, hashes, run token)
is private: it is only ever written under the Git-ignored artifacts/live/private/, never into the
repository or the Nix store, with exclusive creation and mode 0600.

Usage:
  assemble_private_wifi_payload.py --public PAYLOAD_DIR --assets ASSET_DIR --out OUT_DIR
  assemble_private_wifi_payload.py --verify OUT_DIR
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from verify_pcie_j81_reg_on_payload import cpio_entries  # noqa: E402

BASE = "brcmfmac4350c2-pcie"
FW_DIR = "lib/firmware/brcm"
# Apple source name -> (staged name, expected SHA-256 recorded in research/j81-private-firmware-assets.md).
# The NVRAM hash is intentionally not recorded in Git (device-selected); it is checked structurally.
BINARIES = {
    "rieslinga.trx": (BASE + ".bin", "e42b32ab33fcadfaa34414a8ea2c6f90f7931c9a194dad207095275fe3493177", 566531),
    "rieslinga.clmb": (BASE + ".clm_blob", "f1a77b5d933be97f472530c10c9c8d3ae204e8977c32275a113798c00cb2fa66", 9001),
    "rieslinga.txcb": (BASE + ".txcap_blob", "9d270addd113628f9d30fe89a7cbd27ce127503343b5e7bb1ba7b1072cd1722a", 316),
}
NVRAM_NAME = "P-rieslinga_M-CIDR_V-u__m-2.1.txt"
NVRAM_STAGED = BASE + ".txt"
FORBIDDEN_WIFI_TOOLS = {"wpa_supplicant", "wpa_cli", "hostapd", "iw", "iwctl", "iwd", "NetworkManager",
                        "nmcli", "connmand", "wpa_passphrase"}
PRIVATE_SUBDIR = ("artifacts", "live", "private")
# Test-only boot arguments the run may add (kernel toggles of patch 0067); anything else is refused.
EXTRA_BOOTARG_ALLOWED = (r"pcie_apple_t7000\.device_wake=[01]", r"brcmfmac\.h1b_ds_ack=[012]", r"brcmfmac\.h1b_apple_shared=[0-7]", r"brcmfmac\.h1b_hold=[01]", r"brcmfmac\.h1b_ring_ids=[01]", r"brcmfmac\.h1b_defer_s=[0-9]{1,3}", r"apple_dart\.pci_rebase=[01]", r"apple_dart\.pci_alias=[01]", r"apple_dart\.ios_pte=[01]", r"brcmfmac\.h1b_feed=[0-7]", r"brcmfmac\.h1b_rxpost=[0-9]{1,3}", r"brcmfmac\.h1b_sync_ms=[0-9]{1,4}", r"brcmfmac\.h1b_fast_poll_us=[0-9]{2,5}", r"brcmfmac\.h1b_step_s=[0-9]{1,2}", r"brcmfmac\.h1b_tcm_idx=[01]", r"brcmfmac\.h1b_bell_only=[01]", r"brcmfmac\.h1b_no_bell=[01]", r"apple_dart\.h1b_apple_init=[01]", r"io_pgtable_dart\.ios_leaf_bits=[0-9]{1,4}",
                         r"pcie_aspm\.policy=(default|performance|powersave|powersupersave)", r"pcie_aspm=off")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def normalize_nvram(raw):
    """Asahi-style: strip whitespace around keys/values and line ends; keep comments and key order."""
    text = raw.decode("ascii")                      # non-ASCII or NUL data is refused by the caller
    out = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            out.append(line)
            continue
        key, sep, value = line.partition("=")
        out.append(key.strip() + sep + value.strip())
    return ("\n".join(out) + "\n").encode("ascii")


MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")


def check_macaddr(mac):
    """A test MAC for the firmware's required `macaddr` NVRAM key: unicast, locally administered, not all zero."""
    mac = mac.lower()
    if not MAC_RE.match(mac):
        raise SystemExit(f"--nvram-macaddr must look like 02:xx:xx:xx:xx:xx, got {mac!r}")
    first = int(mac[:2], 16)
    if first & 1 or not first & 2:
        raise SystemExit("--nvram-macaddr must be unicast and locally administered (first octet bit0=0, bit1=1)")
    if mac == "02:00:00:00:00:00" or set(mac.replace(":", "")) == {"0"}:
        raise SystemExit("--nvram-macaddr must not be all zero")
    return mac


def check_nvram(raw):
    if not raw.strip():
        raise SystemExit("NVRAM is empty")
    if b"\0" in raw or any(b > 0x7E or (b < 0x20 and b not in (9, 10, 13)) for b in raw):
        raise SystemExit("NVRAM contains non-text bytes")
    staged = normalize_nvram(raw)
    pairs = [l for l in staged.decode().split("\n") if l and not l.startswith("#") and "=" in l]
    if len(pairs) < 10:
        raise SystemExit(f"NVRAM has only {len(pairs)} key=value lines: refusing to stage it")
    if any(not l.split("=", 1)[0] for l in pairs):
        raise SystemExit("NVRAM has an empty key")
    return staged, len(pairs)


def newc_entry(name, mode, data=b"", nlink=1):
    """One cpio newc entry (070701), padded; names are relative, as in the existing overlay."""
    name_b = name.encode() + b"\0"
    header = "070701" + "".join(f"{v:08X}" for v in (
        0, mode, 0, 0, nlink, 0, len(data), 0, 0, 0, 0, len(name_b), 0))
    out = header.encode() + name_b
    out += b"\0" * (-len(out) % 4)
    out += data
    out += b"\0" * (-len(data) % 4)
    return out


def build_overlay(files, extra=()):
    """`files` are firmware files under FW_DIR; `extra` are (path, mode, data) entries anywhere (the Wi-Fi userland, see wifi_userland_entries)."""
    dirs = ["lib", "lib/firmware", FW_DIR]
    for path, _mode, _data in extra:
        parent = ""
        for part in path.split("/")[:-1]:
            parent = f"{parent}/{part}" if parent else part
            if parent not in dirs:
                dirs.append(parent)
    parts = [newc_entry(d, 0o040755, nlink=2) for d in dirs]
    for name, data in files:
        parts.append(newc_entry(f"{FW_DIR}/{name}", 0o100644, data))
    for path, mode, data in extra:
        parts.append(newc_entry(path, mode, data))
    parts.append(newc_entry("TRAILER!!!", 0))
    return b"".join(parts)


def read_parts(public):
    names = ("m1n1.bin", "bootargs", "t7001-j81.dtb", "Image.gz", "initramfs.gz")
    parts = {n: (public / n).read_bytes() for n in names}
    if (public / "m1n1-linux.bin").read_bytes() != b"".join(parts[n] for n in names):
        raise SystemExit("public m1n1-linux.bin is not the concatenation of its parts")
    for line in (public / "SHA256SUMS").read_text().splitlines():
        digest, path = line.split()
        if sha256(Path(path).read_bytes()) != digest:
            raise SystemExit(f"public payload checksum mismatch: {path}")
    return names, parts


def compose(parts, names, overlay, token, extra=()):
    initramfs = gzip.compress(gzip.decompress(parts["initramfs.gz"]) + overlay, mtime=0)
    for arg in extra:
        if not any(re.fullmatch(p, arg) for p in EXTRA_BOOTARG_ALLOWED):
            raise SystemExit(f"boot argument {arg!r} is not an allowed test toggle")
    bootargs = parts["bootargs"].rstrip(b"\n") + b"".join(f" {a}".encode() for a in extra) + f" j81.run_id={token}".encode() + b"\n"
    final = dict(parts, **{"initramfs.gz": initramfs, "bootargs": bootargs})
    return final, b"".join(final[n] for n in names)


def private_out_dir(out):
    out = Path(out).resolve()
    allowed = (ROOT.joinpath(*PRIVATE_SUBDIR)).resolve()
    try:
        out.relative_to(allowed)
    except ValueError:
        raise SystemExit(f"output must be under {allowed} (ignored, private)")
    r = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", str(out / "x")], capture_output=True)
    if r.returncode != 0:
        raise SystemExit("output directory is not ignored by Git")
    return out


def write_private(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)


WIFI_TOOLS = ("iw", "wpa_supplicant", "wpa_cli")
WIFI_SCRIPT_SRC = Path(__file__).with_name("wifi-up.sh")
WIFI_UDHCPC_SRC = Path(__file__).with_name("wifi-udhcpc.script")


def wifi_userland_entries(userland_dir, credentials_file):
    """The Wi-Fi userland of a private payload: static iw/wpa_supplicant/wpa_cli, the boot script, the udhcpc script and the private
    wpa_supplicant.conf. The credentials file is read here and only ever written into the private payload (mode 0600); the manifest records
    that it is present, never its content or hash."""
    userland_dir, credentials_file = Path(userland_dir), Path(credentials_file)
    entries, tools = [], {}
    for name in WIFI_TOOLS:
        data = (userland_dir / "bin" / name).read_bytes() if (userland_dir / "bin" / name).is_file() else (userland_dir / name).read_bytes()
        if data[:4] != b"\x7fELF":
            raise SystemExit(f"{name} is not an ELF binary")
        entries.append((f"usr/bin/{name}", 0o100755, data))
        tools[name] = sha256(data)
    entries.append(("usr/bin/wifi-up", 0o100755, WIFI_SCRIPT_SRC.read_bytes()))
    entries.append(("usr/share/wifi/udhcpc.script", 0o100755, WIFI_UDHCPC_SRC.read_bytes()))
    conf = credentials_file.read_bytes()
    if b"ssid=" not in conf or b"psk=" not in conf and b"key_mgmt=NONE" not in conf:
        raise SystemExit("the credentials file is not a wpa_supplicant configuration with an ssid and a psk")
    entries.append(("etc/wpa_supplicant.conf", 0o100600, conf))
    return entries, tools


def assemble(public, assets, out, nvram_name=NVRAM_NAME, check_hashes=True, token=None, extra_bootargs=(), nvram_macaddr=None,
             wifi_userland=None, wifi_credentials=None, production=False):
    out = private_out_dir(out)
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} already exists and is not empty")
    names, parts = read_parts(Path(public))
    assets = Path(assets)
    files, manifest_assets = [], []
    for src, (staged_name, want_hash, want_size) in BINARIES.items():
        data = (assets / src).read_bytes()
        if not data:
            raise SystemExit(f"{src} is empty")
        if check_hashes and (sha256(data) != want_hash or len(data) != want_size):
            raise SystemExit(f"{src} does not match the recorded 12B410 C2 asset (size/SHA-256)")
        files.append((staged_name, data))
        manifest_assets.append({"source": src, "staged": staged_name, "size": len(data), "sha256": sha256(data)})
    raw = (assets / nvram_name).read_bytes()
    staged, npairs = check_nvram(raw)
    macaddr = None
    if nvram_macaddr:
        macaddr = check_macaddr(nvram_macaddr)
        if any(l.split("=", 1)[0].strip().lower() == "macaddr" for l in staged.decode().split("\n") if "=" in l):
            raise SystemExit("the NVRAM already has a macaddr line; refusing to add another")
        staged = staged + f"macaddr={macaddr}\n".encode("ascii")
        npairs += 1
    files.append((NVRAM_STAGED, staged))
    manifest_assets.append({"source": nvram_name, "staged": NVRAM_STAGED, "size": len(staged), "sha256": sha256(staged),
                            "source_sha256": sha256(raw), "key_value_lines": npairs, "normalised": True,
                            "macaddr_added": bool(macaddr), **({"macaddr": macaddr} if macaddr else {})})
    extra_entries, wifi_tools, wifi_source = [], None, None
    public_entries = cpio_entries(gzip.decompress(parts["initramfs.gz"]))
    public_has_wifi = all(f"usr/bin/{n}" in public_entries for n in WIFI_TOOLS + ("wifi-up",))
    if public_has_wifi:
        # The base package already carries the generic Wi-Fi userland (mkJ81BasePayload wifi = true): only the private credentials are added.
        if wifi_userland:
            raise SystemExit("the public base already carries the Wi-Fi userland; give --wifi-credentials only")
        if wifi_credentials:
            conf = Path(wifi_credentials).read_bytes()
            if b"ssid=" not in conf or b"psk=" not in conf and b"key_mgmt=NONE" not in conf:
                raise SystemExit("the credentials file is not a wpa_supplicant configuration with an ssid and a psk")
            extra_entries = [("etc/wpa_supplicant.conf", 0o100600, conf)]
        wifi_tools = {n: sha256(public_entries[f"usr/bin/{n}"][1]) for n in WIFI_TOOLS}
        wifi_source = "public base"
    else:
        if bool(wifi_userland) != bool(wifi_credentials):
            raise SystemExit("--wifi-userland and --wifi-credentials go together")
        if wifi_userland:
            extra_entries, wifi_tools = wifi_userland_entries(wifi_userland, wifi_credentials)
            wifi_source = "private overlay"
    token = token or secrets.token_hex(16)
    final_parts, blob = compose(parts, names, build_overlay(files, extra_entries), token, tuple(extra_bootargs))
    out.mkdir(parents=True, exist_ok=True)
    os.chmod(out, 0o700)
    write_private(out / "m1n1-linux.bin", blob)
    for n in ("bootargs", "initramfs.gz"):
        write_private(out / n, final_parts[n])
    manifest = {
        "tool": "boot/assemble_private_wifi_payload.py", "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "run_id": token, "public_payload": str(Path(public).resolve()),
        "public_parts_sha256": {n: sha256(parts[n]) for n in names},
        "final_m1n1_linux_sha256": sha256(blob), "final_size": len(blob),
        "bootargs": final_parts["bootargs"].decode().strip(), "extra_bootargs": list(extra_bootargs), "assets": manifest_assets,
        "production": bool(production),
        "wifi_userland": ({"tools_sha256": wifi_tools, "source": wifi_source, "credentials_present": bool(wifi_credentials),
                           "autostart": "/usr/bin/wifi-up from the boot hook"}
                          if wifi_tools else None),
        "selection": "explicit: C2 rieslinga set + tuple-selected NVRAM staged under canonical brcmfmac4350c2-pcie names",
    }
    write_private(out / "PRIVATE_MANIFEST.json", (json.dumps(manifest, indent=2) + "\n").encode())
    return manifest


def verify(out):
    out = Path(out).resolve()
    problems = []
    manifest = json.loads((out / "PRIVATE_MANIFEST.json").read_text())
    blob = (out / "m1n1-linux.bin").read_bytes()
    if sha256(blob) != manifest["final_m1n1_linux_sha256"]:
        problems.append("final payload hash differs from the manifest")
    initramfs = (out / "initramfs.gz").read_bytes()
    bootargs = (out / "bootargs").read_bytes()
    if not blob.endswith(initramfs):
        problems.append("m1n1-linux.bin does not end with the overlaid initramfs")
    if bootargs not in blob:
        problems.append("bootargs not embedded in the payload")
    token = manifest["run_id"]
    if f"j81.run_id={token}" not in bootargs.decode():
        problems.append("run token missing from the bootargs")
    if "brcmfmac.debug=" not in bootargs.decode() and not manifest.get("production"):
        problems.append("bootargs lack brcmfmac.debug")
    entries = cpio_entries(gzip.decompress(initramfs))
    for a in manifest["assets"]:
        entry = entries.get(f"{FW_DIR}/{a['staged']}")
        if entry is None:
            problems.append(f"{a['staged']} missing from the initramfs")
        elif not entry[1]:
            problems.append(f"{a['staged']} is empty")
        elif sha256(entry[1]) != a["sha256"]:
            problems.append(f"{a['staged']} differs from the manifest")
    nv = entries.get(f"{FW_DIR}/{NVRAM_STAGED}")
    if nv and len([l for l in nv[1].decode(errors="ignore").splitlines() if "=" in l]) < 10:
        problems.append("staged NVRAM is not a plausible key=value file")
    extra = sorted(n for n in entries if n.startswith(FW_DIR + "/") and n.rsplit("/", 1)[-1] not in
                   {a["staged"] for a in manifest["assets"]})
    if extra:
        problems.append(f"unexpected extra firmware files: {extra}")
    userland = manifest.get("wifi_userland")
    tools = sorted(n for n in entries if n.rsplit("/", 1)[-1] in FORBIDDEN_WIFI_TOOLS)
    if userland:
        want = {f"usr/bin/{n}" for n in WIFI_TOOLS}
        if set(tools) != want:
            problems.append(f"Wi-Fi tools differ from the recorded userland: {tools}")
        for n, h in userland["tools_sha256"].items():
            e = entries.get(f"usr/bin/{n}")
            if e is None or sha256(e[1]) != h:
                problems.append(f"{n} differs from the manifest")
        required = ["usr/bin/wifi-up", "usr/share/wifi/udhcpc.script"] + (["etc/wpa_supplicant.conf"] if userland.get("credentials_present") else [])
        for n in required:
            if n not in entries or not entries[n][1]:
                problems.append(f"{n} missing from the initramfs")
        if "etc/wpa_supplicant.conf" in entries and (entries["etc/wpa_supplicant.conf"][0] & 0o777) != 0o600:
            problems.append("etc/wpa_supplicant.conf is not mode 0600")
    elif tools:
        problems.append(f"Wi-Fi client/scan tools present: {tools}")
    if "etc/deviceinfo" not in entries or b"ecm.usb0" not in entries["etc/deviceinfo"][1]:
        problems.append("USB recovery (ECM deviceinfo) is not intact")
    if oct(os.stat(out / "m1n1-linux.bin").st_mode & 0o777) != "0o600":
        problems.append("payload file mode is not 0600")
    return problems, manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--public", type=Path)
    ap.add_argument("--assets", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--verify", type=Path)
    ap.add_argument("--nvram", default=NVRAM_NAME)
    ap.add_argument("--extra-bootarg", action="append", default=[], help="test toggle: pcie_apple_t7000.device_wake=1 | brcmfmac.h1b_ds_ack=0|1|2")
    ap.add_argument("--nvram-macaddr", help="append macaddr=<MAC> to the staged NVRAM (the firmware needs the key to attach its Wi-Fi core); unicast, locally administered, e.g. 02:6a:38:70:00:01")
    ap.add_argument("--wifi-userland", type=Path, help="directory with static iw, wpa_supplicant, wpa_cli (flake package wifi-userland-static; bin/ is accepted); starts Wi-Fi at boot with --wifi-credentials")
    ap.add_argument("--wifi-credentials", type=Path, help="private wpa_supplicant.conf (ssid/psk); installed only into the private payload, mode 0600, never recorded in the manifest")
    ap.add_argument("--production", action="store_true", help="payload of the production kernel (m1n1-hoolock-wifi): quiet brcmfmac logging, so the brcmfmac.debug bootarg is not required")
    ap.add_argument("--no-hash-check", action="store_true", help="test fixtures only (synthetic assets)")
    args = ap.parse_args()
    if args.verify:
        problems, manifest = verify(args.verify)
        if problems:
            print("FAIL")
            for p in problems:
                print(" -", p)
            return 1
        print("PASS: private payload verified (hashes, overlay, non-empty NVRAM, run token, no Wi-Fi client tools, USB recovery)")
        print(f"      payload size {manifest['final_size']}, assets {len(manifest['assets'])}; details only in the private manifest")
        return 0
    if not (args.public and args.assets and args.out):
        ap.error("--public, --assets and --out are required")
    manifest = assemble(args.public, args.assets, args.out, args.nvram, check_hashes=not args.no_hash_check,
                        extra_bootargs=args.extra_bootarg, nvram_macaddr=args.nvram_macaddr,
                        wifi_userland=args.wifi_userland, wifi_credentials=args.wifi_credentials, production=args.production)
    problems, _ = verify(args.out)
    if problems:
        print("FAIL after assembly:", problems)
        return 1
    print(f"assembled {args.out} (run id {manifest['run_id']}, {manifest['final_size']} bytes); verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
