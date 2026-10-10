#!/usr/bin/env python3
"""Bluetooth bring-up experiment for the RUNNING iPad: drive BT_WAKE (AP GPIO 164) and power-enable (PMU GPIO2), probe the Bluetooth UART, then ALWAYS restore both.

Approved by the user in chat (2026-10-10): the single GPIO2 write `0x0402: 0x09 -> 0x0b` and driving AP GPIO 164 high, each with readback and revert. The script touches nothing else.
It talks to the iPad through the telnet recovery shell (boot/ipad_telnet_run.py) and expects /tmp/bt/{pinpoke,i2ctransfer,btattach} already on the iPad (pushed over the USB link).

  boot/bt_wake_experiment.py [--speeds 115200,921600,3000000]

Sequence (any failure or exception goes straight to the restore step):
  1. baseline reads: pin 164 pad register, PMU 0x0402 (must be 0x09), 0x0010 (must be 0x00), battery state;
  2. pinpoke high 164            -> readback must show DATA=1;
  3. i2ctransfer 0x0402 <- 0x0b  -> readback must be 0x0b;
  4. raw HCI Reset probe of /dev/ttySAC1 (boot/bt_uart_probe.py) at each speed, with and without RTS/CTS;
  5. btattach -P bcm for a few seconds, log and dmesg lines;
  6. restore: 0x0402 <- 0x09, pinpoke restore 164 <original>, verify both and that charging is untouched.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ipad_telnet_run import run  # noqa: E402
import bt_uart_probe  # noqa: E402

PMU = "w2@0x3c"


def sh(cmd, timeout=40):
    out, rc = run(cmd, timeout=timeout)
    return out.strip()


def rd_pmu(hi, lo):
    return sh(f"cd /tmp/bt; ./i2ctransfer -f -y 0 {PMU} {hi} {lo} r1@0x3c 2>&1").splitlines()[-1].strip()


def rd_pin(pin=164):
    out = sh(f"cd /tmp/bt; ./pinpoke read {pin} 2>&1")
    m = re.search(r"reg (0x[0-9a-f]+)", out)
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--speeds", default="115200,921600,3000000")
    a = ap.parse_args()

    for tool in ("pinpoke", "i2ctransfer", "btattach"):
        if "x" not in sh(f"ls -l /tmp/bt/{tool} 2>&1 | cut -c1-4"):
            sys.exit(f"/tmp/bt/{tool} is missing on the iPad")

    orig_pin = rd_pin()
    base_gpio2 = rd_pmu("0x04", "0x02")
    base_usb = rd_pmu("0x00", "0x10")
    print(f"baseline: pin164 reg {orig_pin}, 0x0402 {base_gpio2}, 0x0010 {base_usb}")
    if orig_pin is None or base_gpio2 != "0x09" or base_usb != "0x00":
        sys.exit("unexpected baseline (need 0x0402 = 0x09 and 0x0010 = 0x00); nothing was written")
    print("battery:", sh("tablet-status | sed -n 2,3p | tr '\\n' ' '"))

    ok = True
    try:
        print("--- BT_WAKE high")
        print(sh("cd /tmp/bt; ./pinpoke high 164"))
        after = rd_pin()
        print("pin164 readback:", after)
        if after is None or (int(after, 16) & 1) != 1:
            print("BT_WAKE did not go high; stopping")
            ok = False
        if ok:
            print("--- GPIO2 power-enable 0x0402 <- 0x0b")
            print(sh("cd /tmp/bt; ./i2ctransfer -f -y 0 w3@0x3c 0x04 0x02 0x0b; echo write_rc=$?"))
            g2 = rd_pmu("0x04", "0x02")
            print("0x0402 readback:", g2)
            if g2 != "0x0b":
                print("0x0402 did not hold 0x0b; stopping")
                ok = False
        if ok:
            print("--- raw HCI Reset probe (both lines asserted)")
            print(sh("sleep 1; ls /sys/class/bluetooth 2>&1 | head -2; ps | grep -c '[b]tattach'"))
            for speed in [s for s in a.speeds.split(",") if s]:
                for flow in (False, True):
                    print(f"speed {speed:>8} {'rtscts' if flow else 'no-fc '}: {bt_uart_probe.probe('/dev/ttySAC1', speed, flow, 3)}", flush=True)
            print("--- btattach -P bcm (6 s)")
            print(sh("cd /tmp/bt; (nohup ./btattach -B /dev/ttySAC1 -P bcm -S 3000000 >/tmp/btattach.log 2>&1 &); sleep 6; cat /tmp/btattach.log; "
                     "ls /sys/class/bluetooth 2>&1 | head -2; dmesg | grep -E 'hci0|BCM:' | tail -6 | cut -c1-120; killall btattach 2>/dev/null; sleep 1", timeout=60))
    finally:
        print("--- RESTORE")
        sh("killall btattach 2>/dev/null")
        print(sh("cd /tmp/bt; ./i2ctransfer -f -y 0 w3@0x3c 0x04 0x02 0x09; echo gpio2_restore_rc=$?"))
        print(sh(f"cd /tmp/bt; ./pinpoke restore 164 {orig_pin}"))
        g2, pin, usb, lim = rd_pmu("0x04", "0x02"), rd_pin(), rd_pmu("0x00", "0x10"), rd_pmu("0x04", "0xc0")
        print(f"final: 0x0402 {g2} (want 0x09), pin164 {pin} (want {orig_pin}), 0x0010 {usb} (want 0x00), 0x04c0 {lim}")
        print("battery:", sh("tablet-status | sed -n 2,3p | tr '\\n' ' '"))
        if g2 != "0x09" or pin != orig_pin:
            print("!!! RESTORE FAILED: check the registers by hand before continuing")
            sys.exit(1)
        print("restored OK")


if __name__ == "__main__":
    main()
