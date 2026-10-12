#!/usr/bin/env python3
"""Serve the NixOS-in-RAM root to the iPad's stage-1 hand-off (boot/nixos-handoff.sh) over the USB link.

  boot/nixos_ram_serve.py [--rootfs artifacts/live/gcroot-nixos-ram-rootfs] [--toplevel artifacts/live/gcroot-nixos-ram-toplevel] [--bind 172.16.42.2] [--port 8000]

Serves exactly two files and nothing else: `/root.squashfs` (the zstd squashfs of the system's Nix store) and `/toplevel` (one line: the store path of the system, read from the
toplevel GC root's link target). Read-only, no directory listing, no other path. Private files (firmware, Wi-Fi credentials, ssh keys) are NOT served: the iPad takes them from the
private payload it booted with. Start it before booting a payload whose kernel command line has j81.nixos=http://172.16.42.2:8000/ (m1n1-hoolock-wifi-nixos).
"""
import argparse
import http.server
import os
import pathlib
import sys
import time


def make_handler(rootfs, toplevel_line):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            sys.stderr.write("nixos-ram-serve: %s - %s\n" % (self.address_string(), fmt % args))

        def do_GET(self):
            if self.path == "/toplevel":
                body = (toplevel_line + "\n").encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/root.squashfs":
                size = os.path.getsize(rootfs)
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(size))
                self.end_headers()
                with open(rootfs, "rb") as f:
                    while True:
                        chunk = f.read(1 << 20)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
            else:
                self.send_error(404)

        do_HEAD = None  # the stage-1 client only does GET

    return Handler


def resolve(rootfs_path, toplevel_path):
    rootfs = pathlib.Path(rootfs_path).resolve()
    if rootfs.is_dir():
        imgs = sorted(rootfs.glob("*.img")) or sorted(rootfs.glob("*.squashfs"))
        if not imgs:
            raise SystemExit(f"no squashfs image in {rootfs}")
        rootfs = imgs[0]
    top = os.path.realpath(toplevel_path)
    if not top.startswith("/nix/store/"):
        raise SystemExit(f"{toplevel_path} does not resolve to a /nix/store path ({top})")
    return rootfs, top


def main(argv=None):
    root = pathlib.Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rootfs", default=str(root / "artifacts/live/gcroot-nixos-ram-rootfs"))
    ap.add_argument("--toplevel", default=str(root / "artifacts/live/gcroot-nixos-ram-toplevel"))
    ap.add_argument("--bind", default="172.16.42.2")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args(argv)
    rootfs, top = resolve(a.rootfs, a.toplevel)
    print(f"serving {rootfs} ({rootfs.stat().st_size / 1e6:.0f} MB) and toplevel {top} on http://{a.bind}:{a.port}/", flush=True)
    # The Mac's 172.16.42.2 only exists once the iPad's USB gadget has enumerated, so retry the bind until then (start this before or right after the DFU load).
    while True:
        try:
            httpd = http.server.ThreadingHTTPServer((a.bind, a.port), make_handler(rootfs, top))
            break
        except OSError as error:
            print(f"waiting for {a.bind} ({error.strerror}); the iPad's USB link is not up yet", flush=True)
            time.sleep(3)
    print("listening", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
