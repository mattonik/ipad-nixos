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
EXTRA_BOOTARG_ALLOWED = (r"pcie_apple_t7000\.device_wake=[01]", r"brcmfmac\.h1b_ds_ack=[012]")


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


def build_overlay(files):
    parts = [newc_entry(d, 0o040755, nlink=2) for d in ("lib", "lib/firmware", FW_DIR)]
    for name, data in files:
        parts.append(newc_entry(f"{FW_DIR}/{name}", 0o100644, data))
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


def assemble(public, assets, out, nvram_name=NVRAM_NAME, check_hashes=True, token=None, extra_bootargs=()):
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
    files.append((NVRAM_STAGED, staged))
    manifest_assets.append({"source": nvram_name, "staged": NVRAM_STAGED, "size": len(staged), "sha256": sha256(staged),
                            "source_sha256": sha256(raw), "key_value_lines": npairs, "normalised": True})
    token = token or secrets.token_hex(16)
    final_parts, blob = compose(parts, names, build_overlay(files), token, tuple(extra_bootargs))
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
    if "brcmfmac.debug=" not in bootargs.decode():
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
    tools = sorted(n for n in entries if n.rsplit("/", 1)[-1] in FORBIDDEN_WIFI_TOOLS)
    if tools:
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
                        extra_bootargs=args.extra_bootarg)
    problems, _ = verify(args.out)
    if problems:
        print("FAIL after assembly:", problems)
        return 1
    print(f"assembled {args.out} (run id {manifest['run_id']}, {manifest['final_size']} bytes); verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
