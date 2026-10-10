#!/usr/bin/env python3
"""Raw HCI-reset probe of the iPad's Bluetooth UART, run on the iPad through the telnet recovery shell (boot/ipad_telnet_run.py).

For each (baud, flow-control) combination it configures /dev/ttySAC1 raw, starts a reader, sends one HCI Reset command (01 03 0c 00) and reports the bytes that
come back within a few seconds. A live Broadcom controller answers with a Command Complete event (04 0e 04 01 03 0c 00); silence means the chip does not respond
at that setting. The probe sends only that 4-byte standard command; it changes no PMIC or GPIO register and never touches Wi-Fi.

  boot/bt_uart_probe.py [--tty /dev/ttySAC1] [--speeds 115200,921600,3000000] [--wait 3]

Requires nothing on the iPad but busybox (stty, od, wc) and that no HCI line discipline is attached (kill btattach first).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ipad_telnet_run import run  # noqa: E402

HCI_RESET = r"\001\003\014\000"


def probe(tty, speed, flow, wait):
    fc = "crtscts" if flow else "-crtscts"
    cmd = (
        f"stty -F {tty} raw -echo {fc} {speed} 2>&1 | head -1; : > /tmp/bt/rx.bin; "
        f"cat {tty} > /tmp/bt/rx.bin & p=$!; sleep 0.5; printf '{HCI_RESET}' > {tty}; sleep {wait}; kill $p 2>/dev/null; "
        "echo \"rx_bytes=$(wc -c < /tmp/bt/rx.bin) $(od -An -tx1 /tmp/bt/rx.bin | head -2 | tr -s ' ' | tr '\\n' ' ')\""
    )
    out, rc = run(cmd, timeout=wait + 20)
    return out.strip().splitlines()[-1] if out.strip() else f"no output (rc={rc})"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tty", default="/dev/ttySAC1")
    ap.add_argument("--speeds", default="115200,921600,3000000")
    ap.add_argument("--wait", type=float, default=3)
    a = ap.parse_args()
    out, _ = run("ls /sys/class/bluetooth 2>&1 | head -2; ps | grep -c '[b]tattach'")
    if "hci" in out or out.strip().splitlines()[-1] != "0":
        sys.exit("an HCI device or btattach is active; stop it first (killall btattach)")
    for speed in [s for s in a.speeds.split(",") if s]:
        for flow in (False, True):
            print(f"speed {speed:>8} {'rtscts' if flow else 'no-fc '}: {probe(a.tty, speed, flow, a.wait)}", flush=True)


if __name__ == "__main__":
    main()
