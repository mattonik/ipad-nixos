#!/usr/bin/env python3
"""USER-RUN touch firmware-upload experiment (research/2026-10-11-touch-firmware-upload-spec.md, "Proposed user-approved experiment"). Not run automatically.

Prerequisite: the iPad runs the m1n1-hoolock-wifi-touch payload (spidev child enabled, spidev.bufsiz=65536) and is reachable at 172.16.42.1.
Steps: (1) host-side packet checks, (2) serve the touch-diag binary and the two private packets over HTTP on the USB link, (3) on the iPad: spidev bound? bufsiz ok?
`touch-diag spi-check`, (4) only with --go: `touch-diag run --execute --approve-pmu-write --approve-firmware-upload` (power-up, one boot-IRQ wait, one 59,288-byte message,
the 2-byte ACK query, then the tool's own unwind; no retry). Only the ACK bytes are printed. Without --go it stops after step 3.

  boot/touch_upload_experiment.py [--go] [--tool artifacts/live/gcroot-touch-diag/bin/touch-diag] [--packets firmware/j81-12B410/touch/upload-packets]
"""
import argparse
import hashlib
import http.server
import pathlib
import subprocess
import sys
import threading

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ipad_telnet_run import run  # noqa: E402

PORT = 8765
HOST = "172.16.42.2"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true", help="actually power the controller and send the firmware packet")
    ap.add_argument("--tool", default=str(HERE.parent / "artifacts/live/gcroot-touch-diag/bin/touch-diag"))
    ap.add_argument("--packets", default=str(HERE.parent / "firmware/j81-12B410/touch/upload-packets"))
    a = ap.parse_args()
    pk = pathlib.Path(a.packets)
    fw, ack = (pk / "00-firmware-transfer.bin").read_bytes(), (pk / "01-data-ack-query.bin").read_bytes()
    assert fw[:2] == b"\x18\xe1" and len(fw) == 59288 and ack == b"\x1a\xa1", "packets are not the expected export"
    print(f"host: fw {len(fw)} bytes sha256 {hashlib.sha256(fw).hexdigest()[:16]}..., ack {ack.hex()}")

    stage = pathlib.Path(__file__).resolve().parents[1] / "artifacts/live/private/touch-serve"
    stage.mkdir(parents=True, exist_ok=True)
    (stage / "touch-diag").write_bytes(pathlib.Path(a.tool).read_bytes())
    (stage / "fw.bin").write_bytes(fw)
    (stage / "ack.bin").write_bytes(ack)
    handler = lambda *x, **k: http.server.SimpleHTTPRequestHandler(*x, directory=str(stage), **k)  # noqa: E731
    srv = http.server.ThreadingHTTPServer(("", PORT), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        out = run(f"mkdir -p /tmp/t && cd /tmp/t && for f in touch-diag fw.bin ack.bin; do wget -q -O $f http://{HOST}:{PORT}/$f || echo FETCHFAIL $f; done; chmod 755 touch-diag; ls -l; "
                  "cat /sys/module/spidev/parameters/bufsiz; ls /dev/spidev* 2>&1; ./touch-diag plan | head -3", timeout=120)
        print(out[0])
        if "FETCHFAIL" in out[0]:
            sys.exit("download to the iPad failed; aborting")
        dev = "/dev/spidev0.0"
        print(run(f"cd /tmp/t && ./touch-diag spi-check --spi-dev {dev}", timeout=60)[0])
        if not a.go:
            print("dry run finished; add --go to power the controller and send the firmware packet")
            return
        print(run(f"cd /tmp/t && ./touch-diag run --execute --approve-pmu-write --spi-dev {dev} --upload-fw fw.bin --upload-ack ack.bin --approve-firmware-upload; "
                  "echo EXIT=$?; rm -f fw.bin", timeout=180)[0])
    finally:
        srv.shutdown()
        run("rm -f /tmp/t/fw.bin /tmp/t/ack.bin", timeout=20)


main()
