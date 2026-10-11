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
    ap.add_argument("--ack-tries", type=int, default=6, help="repeat the ACK query up to N times (1..10) on a 0/2/10/50/200/1000 ms schedule; the packet is never resent")
    ap.add_argument("--spi-hz", type=int, default=1984000, help="SPI clock for the whole run (10000..8000000); the first two runs used 1984000")
    ap.add_argument("--chunk", type=int, default=0, help="cut the packet into transfers of this many bytes inside ONE message (chip select stays asserted); 0 = one transfer")
    ap.add_argument("--spi-msb", action="store_true", help="old spidev default (MSB first) for comparison; Apple uses LSB first, which is now the default")
    ap.add_argument("--spi-mode", type=int, default=2, help="SPI mode 0..3 (touch-diag's old default 2; Apple's decoded mode is 0)")
    ap.add_argument("--detect-only", action="store_true", help="power up and send only the detect/handshake frames, NO firmware (no --upload-fw)")
    ap.add_argument("--apple", action="store_true", help="follow Apple's recovered order: LDO14, GPIO95, 5 ms, clock, 15 ms, wake 19 c1, ..., a 30 ms wait after the detect, then a transmit-only packet immediately followed by the ACK query, the pair retried up to 5 times")
    ap.add_argument("--display-sync", action="store_true", help="also select peripheral function 1 on GPIO55 (Apple's display_sync enable, a PINMUX change restored on exit) before the first SPI frames after power-up")
    ap.add_argument("--word-delay-us", type=int, default=0, help="inter-word delay in us (needs the 0096 kernel; Apple uses 5; 0..255)")
    ap.add_argument("--upload-rx", action="store_true", help="with --apple: send the packet full duplex and print a summary of the ROM's reply during the transfer (never the packet)")
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
        print(run(f"cd /tmp/t && ./touch-diag spi-check --spi-dev {dev} --spi-hz {a.spi_hz} --spi-mode {a.spi_mode} {'--spi-msb' if a.spi_msb else ''}", timeout=60)[0])
        if not a.go:
            print("dry run finished; add --go to power the controller and send the firmware packet")
            return
        apple = ("--apple-order --apple-upload" if a.apple else "") + (" --upload-rx" if a.upload_rx else "") + (" --display-sync-pinmux --approve-display-sync-pinmux" if a.display_sync else "")
        upload = "" if a.detect_only else f"--chunk {a.chunk} --upload-fw fw.bin --upload-ack ack.bin --ack-tries {5 if a.apple else a.ack_tries} --approve-firmware-upload"
        print(run(f"cd /tmp/t && ./touch-diag run --execute --approve-pmu-write --spi-dev {dev} --spi-hz {a.spi_hz} --spi-mode {a.spi_mode} --word-delay-us {a.word_delay_us} {'--spi-msb' if a.spi_msb else ''} {apple} {upload}; "
                  "echo EXIT=$?; rm -f fw.bin", timeout=180)[0])
    finally:
        srv.shutdown()
        run("rm -f /tmp/t/fw.bin /tmp/t/ack.bin", timeout=20)


main()
