#!/usr/bin/env python3
"""Live Bluetooth bring-up on the RUNNING iPad (NixOS payload over ssh): UART3 TX/RTS on function 1, power up, btattach -P bcm, patchram, count a scan.

Why (2026-11-02, research/2026-11-02-bt-uart3-pinmux-lead.md): with GPIO 14/32 on function 1 the BCM4350C2 answered HCI Reset at 115,200. This run
lets the kernel's hci_bcm drive the rest (version read, firmware download) through btattach's line discipline, at 115,200 only (no 3 Mbaud by hand).

Writes, each read back and restored in a finally block (owner-approved 2026-11-02): GPIO 14/32 PERIPH 2 -> 1, GPIO164 (BT_WAKE) high, PMU 0x0402
0x09 -> 0x0b, /sys/module/firmware_class/parameters/path -> /tmp/fw. The patchram goes to the iPad's RAM (/tmp/fw/brcm/<name the kernel asked for>)
and is deleted afterwards; it never enters Git or the Nix store.

  boot/bt_live_bringup.py --fw <private BCM.apple,j81.hcd> [--scan 20]

Needs /tmp/bt/{pinpoke (with `func`),i2ctransfer,uartpoke,btattach,hciscan} on the iPad. Output has no BD_ADDR: hciscan prints counts only and
MAC-shaped strings in dmesg are masked.
"""
import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KEYS = [REPO / "artifacts/live/ssh/ipad_ed25519", REPO.parent / "ipad-nixos/artifacts/live/ssh/ipad_ed25519"]
TTY = "/dev/ttySAC1"
FUNC_PINS = (14, 32)
PADS = (14, 15, 32, 33, 164)
TOOLS = ("pinpoke", "i2ctransfer", "uartpoke", "btattach", "hciscan")
MAC = re.compile(r"\b([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b")
BT_LINES = re.compile(r"bluetooth|hci|bcm|firmware|ttySAC1", re.I)


def ssh(cmd, data=None, timeout=90):
    key = next(k for k in KEYS if k.exists())
    r = subprocess.run(["ssh", "-i", str(key), "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "UserKnownHostsFile=/dev/null",
                        "-o", "StrictHostKeyChecking=no", "-o", "LogLevel=ERROR", "root@172.16.42.1", cmd],
                       input=data, capture_output=True, timeout=timeout)
    return (r.stdout + r.stderr).decode(errors="replace").strip("\n")


def bt(cmd):
    return ssh(f"cd /tmp/bt; {cmd}")


def rd(pin):
    m = re.search(r"reg (0x[0-9a-f]+)", bt(f"./pinpoke read {pin} 2>&1"))
    return int(m.group(1), 16) if m else None


def rd_pmu(hi, lo):
    return bt(f"./i2ctransfer -f -y 0 w2@0x3c {hi} {lo} r1").strip()


def periph(v):
    return (v >> 5) & 3


def state():
    return " ".join(f"{p}=0x{rd(p):08x}" for p in PADS) + f"; 0x0402 {rd_pmu('0x04', '0x02')}; 0x0010 {rd_pmu('0x00', '0x10')}; uart {bt('./uartpoke get')}"


def dmesg_since(n):
    lines = ssh("dmesg").splitlines()[n:]
    return [MAC.sub("XX:XX:XX:XX:XX:XX", l) for l in lines if BT_LINES.search(l)]


def attach(wait):
    """Start btattach detached and give hci_bcm `wait` seconds (setup + a 72 KB download at 115,200 takes ~10 s); stop early on a failure line."""
    start = len(ssh("dmesg").splitlines())
    bt(f"nohup ./btattach -B {TTY} -P bcm -S 115200 > /tmp/bt/btattach.log 2>&1 < /dev/null &")
    t0 = time.time()
    while time.time() - t0 < wait:
        time.sleep(3)
        if any(re.search(r"not found|failed|timeout", l, re.I) for l in dmesg_since(start)):
            time.sleep(3)
            break
    return start


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fw", type=Path, required=True, help="private patchram (Orchard bluetool-hcd output); pushed to iPad RAM only")
    ap.add_argument("--scan", type=int, default=20)
    args = ap.parse_args()
    fw = args.fw.read_bytes()

    print("uname:", ssh("uname -a"))
    print("cmdline:", ssh("cat /proc/cmdline"))
    for tool in TOOLS:
        if "x" not in bt(f"ls -l {tool} 2>&1 | cut -c1-4"):
            sys.exit(f"/tmp/bt/{tool} is missing on the iPad")
    if "function must be 1 or 2" not in bt("./pinpoke func 14 0 2>&1"):
        sys.exit("/tmp/bt/pinpoke has no `func` command")
    if ssh("ps -e | grep -c '[b]tattach'; ls /sys/class/bluetooth | wc -l").split() != ["0", "0"]:
        sys.exit("btattach is running or an hci device exists; stop it first")
    orig = {p: rd(p) for p in PADS}
    g2, usb = rd_pmu("0x04", "0x02"), rd_pmu("0x00", "0x10")
    orig_uart = bt("./uartpoke get")
    mu = re.search(r"\+0x04=(0x\w+) \+0x08=(0x\w+) \+0x28=(0x\w+) \+0x34=(0x\w+) \+0x38=(0x\w+)", orig_uart)
    orig_fwpath = ssh("cat /sys/module/firmware_class/parameters/path")
    print("baseline:", state(), "; firmware path", repr(orig_fwpath))
    if None in orig.values() or g2 != "0x09" or usb != "0x00" or not mu or any(periph(orig[p]) != 2 for p in FUNC_PINS):
        sys.exit("unexpected baseline; nothing was written")
    o04, o08, o28, o34, o38 = mu.groups()
    try:
        for p in FUNC_PINS:
            bt(f"./pinpoke func {p} 1")
        bt("./pinpoke high 164")
        bt("./i2ctransfer -f -y 0 w3@0x3c 0x04 0x02 0x0b")
        time.sleep(1)
        print("powered:", state())
        if any(periph(rd(p)) != 1 for p in FUNC_PINS) or not rd(164) & 1 or rd_pmu("0x04", "0x02") != "0x0b":
            print("a write did not take; skipping btattach")
            return
        print("--- ATTACH 1 (no patchram reachable)")
        n = attach(25)
        first = dmesg_since(n)
        print("\n".join(first) or "(no Bluetooth dmesg lines)")
        names = re.findall(r"'(brcm/[^']+\.hcd)'", "\n".join(first)) or re.findall(r"(brcm/\S+\.hcd)", "\n".join(first))
        names = list(dict.fromkeys(names))
        if not names:
            print("kernel named no patchram file; stopping before firmware")
            return
        print("kernel asked for:", ", ".join(names))
        bt("killall btattach; sleep 2")
        for name in names:
            ssh(f"mkdir -p /tmp/fw/{Path(name).parent} && cat > /tmp/fw/{name}", data=fw)
        ssh("echo -n /tmp/fw > /sys/module/firmware_class/parameters/path")
        print("--- ATTACH 2 (patchram at /tmp/fw)")
        n = attach(60)
        print("\n".join(dmesg_since(n)) or "(no Bluetooth dmesg lines)")
        print("btattach log:", MAC.sub("XX:XX:XX:XX:XX:XX", bt("cat btattach.log")))
        if ssh("ls /sys/class/bluetooth"):
            print("--- SCAN")
            print(bt(f"./hciscan 0 {args.scan} 2>&1"))
        else:
            print("no hci device after attach 2; no scan")
    finally:
        print("--- RESTORE")
        bt("killall btattach 2>/dev/null; sleep 2")
        ssh(f"echo -n '{orig_fwpath}' > /sys/module/firmware_class/parameters/path; rm -rf /tmp/fw")
        bt("./i2ctransfer -f -y 0 w3@0x3c 0x04 0x02 0x09")
        bt(f"./pinpoke restore 164 0x{orig[164]:08x}")
        bt(f"exec 3<>{TTY}; stty -F {TTY} raw -echo -crtscts clocal cs8 -cstopb -parenb 115200; ./uartpoke ucon {o04} >/dev/null; ./uartpoke ufcon {o08} >/dev/null; "
           f"./uartpoke set {o28} {o34} {o38} >/dev/null; exec 3<&-")
        for p in FUNC_PINS:
            bt(f"./pinpoke func {p} {periph(orig[p])}")
        final_uart = bt("./uartpoke get")
        bad = [p for p in PADS if rd(p) != orig[p]]
        g2f, fwp = rd_pmu("0x04", "0x02"), ssh("cat /sys/module/firmware_class/parameters/path; ls /tmp/fw 2>&1 | head -1")
        print("final:", state(), "; firmware path", repr(fwp))
        if g2f != "0x09" or bad or final_uart != orig_uart or ssh("ps -e | grep -c '[b]tattach'") != "0":
            print(f"!!! RESTORE FAILED (pins {bad}, 0x0402 {g2f}, uart {final_uart}): check by hand")
            sys.exit(1)
        print("restored OK")


if __name__ == "__main__":
    main()
