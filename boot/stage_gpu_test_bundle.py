#!/usr/bin/env python3
"""Stage selected GPU bundle files into the iPad's RAM filesystem; never execute them."""

import argparse
import base64
import gzip
import hashlib
import json
import socket
import time
from pathlib import Path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stage(host: str, remote: str, data: bytes) -> None:
    encoded = base64.b64encode(gzip.compress(data, 9)).decode()
    scratch = "/tmp/" + remote.rsplit("/", 1)[-1] + ".gz.b64"
    expected = sha256(data)
    with socket.create_connection((host, 23), 5) as sock:
        sock.settimeout(0.2)
        time.sleep(0.25)
        try:
            while sock.recv(65536):
                pass
        except (TimeoutError, socket.timeout):
            pass
        sock.sendall(f": > {scratch}\n".encode())
        for pos in range(0, len(encoded), 768):
            sock.sendall(f"printf %s {encoded[pos:pos + 768]} >> {scratch}\n".encode())
            time.sleep(0.01)
        time.sleep(1)
        sock.sendall(f"base64 -d {scratch} | gzip -dc > {remote} && chmod 700 {remote} && sha256sum {remote}\n".encode())
        output = b""
        deadline = time.monotonic() + max(20, len(encoded) / 1000)
        while time.monotonic() < deadline and expected.encode() not in output:
            try:
                chunk = sock.recv(65536)
            except (TimeoutError, socket.timeout):
                continue
            if not chunk:
                break
            output += chunk
    if expected.encode() not in output:
        raise SystemExit(f"staging failed for {remote}: {output[-500:].decode(errors='replace')}")
    print(f"staged {remote} sha256={expected}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=Path("artifacts/live/gpu-test-bundle-20261106-v2"))
    parser.add_argument("--host", default="172.16.42.1")
    parser.add_argument("names", nargs="+", help="bundle paths such as bin/gpu-id-once wrappers/gpu-id-once-run.sh")
    args = parser.parse_args()
    manifest = json.loads((args.bundle / "MANIFEST.json").read_text())
    allowed = set()
    for group in ("binaries", "modules", "wrappers", "data"):
        allowed.update(f"{group}/{name}" for name in manifest[group])
    for name in args.names:
        canonical = name.replace("bin/", "binaries/", 1) if name.startswith("bin/") else name
        if canonical not in allowed:
            parser.error(f"not in bundle manifest: {name}")
        group, item = canonical.split("/", 1)
        directory = "bin" if group == "binaries" else group
        path = args.bundle / directory / item
        remote_name = path.stem if group == "wrappers" and path.suffix == ".sh" else path.name
        stage(args.host, "/tmp/" + remote_name, path.read_bytes())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
