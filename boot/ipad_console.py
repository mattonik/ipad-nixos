#!/usr/bin/env python3
"""Menu-driven diagnostic console for the postmarketOS debug shell running
on the iPad, over the USB network link established once
m1n1-hoolock-control has booted (see docs/software-only-control.md's
"Round 10"). No need to remember raw shell commands or sysfs paths --
pick a numbered item.

Usage:
    nix develop -c python3 boot/ipad_console.py

Requires the Mac side of the USB link already configured (a static IP in
172.16.42.0/24 on the "Sony Xperia Z5" interface -- see the runbook for
the exact `networksetup -setmanual` command) and the iPad sitting at the
debug shell.

Adding a new test: write a function taking one argument (the IPadShell
connection) that prints whatever it wants, then add
("Menu label", your_function) to ACTIONS below. That's the whole
extension point -- no other wiring needed.
"""
import os
import re
import socket
import sys
import time
from collections.abc import Callable

HOST = "172.16.42.1"
PORT = 23

# https://no-color.org/, plus the --no-color flag the article below also
# calls out: https://evilmartians.com/chronicles/cli-ux-best-practices-3-patterns-for-improving-progress-displays
# Screen-clearing is gated on isatty() alone (unrelated to color), since
# emitting it into a pipe or redirected file would just be garbage bytes.
_IS_TTY = sys.stdout.isatty()
_COLOR = _IS_TTY and "NO_COLOR" not in os.environ and "--no-color" not in sys.argv


def _c(code: str) -> str:
    return code if _COLOR else ""


GREEN = _c("\033[32m")
RED = _c("\033[31m")
BOLD = _c("\033[1m")
RESET = _c("\033[0m")
CLEAR = "\033[2J\033[H" if _IS_TTY else ""
CLEAR_LINE = "\r\033[K" if _IS_TTY else "\r"  # overwrite in place regardless of old/new length
CHECK = "✓"  # only ASCII/BMP glyphs; keep it usable over a plain telnet-era terminal
CROSS = "✗"
_SPINNER_FRAMES = "|/-\\"

BACKLIGHT = "/sys/class/backlight/20a110000.i2c:pmic@3c:backlight@600"
RTC = "/sys/class/rtc/rtc0"

# BT-1 (docs/plans/2026-09-08-j81-bluetooth-battery-adt.md): UART3's tty
# node and the BCM43540's transport-speed, both independently decoded from
# the real J81 ADT and confirmed on hardware -- not guessed.
BT_TTY = "/dev/ttySAC1"
BT_SPEED = "3000000"

_ANSI_RE = re.compile(rb"\x1b\[[0-9;]*[a-zA-Z]")


def _strip_iac(data: bytes) -> bytes:
    """Remove Telnet IAC option-negotiation sequences (busybox telnetd
    sends these; we never answer them, so they'd otherwise show up as
    junk bytes in the output)."""
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == 0xFF:
            if i + 1 < len(data) and data[i + 1] in (0xFB, 0xFC, 0xFD, 0xFE):
                i += 3
                continue
            if i + 1 < len(data) and data[i + 1] == 0xFF:
                out.append(0xFF)
                i += 2
                continue
            i += 2
            continue
        out.append(data[i])
        i += 1
    return bytes(out)


def _clean(data: bytes) -> str:
    data = _strip_iac(data)
    data = _ANSI_RE.sub(b"", data)
    return data.decode(errors="replace")


class IPadShell:
    """A persistent connection to the postmarketOS debug shell's telnetd."""

    def __init__(self, host: str = HOST, port: int = PORT):
        self.host = host
        self.port = port
        self.sock: socket.socket | None = None

    def connect(self, timeout: float = 5) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=timeout)
        self.sock.settimeout(0.5)
        time.sleep(0.5)
        self._read_until(None, deadline=1.5)  # drain the login banner
        # Without this, the shell's pty echoes back everything we send,
        # wrapped at its terminal width -- doubling every command in the
        # output and sometimes splitting it mid-word. Only real command
        # output should appear from here on.
        self.sock.sendall(b"stty -echo\n")
        time.sleep(0.3)
        self._read_until(None, deadline=1.0)

    def close(self) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None

    def _read_until(self, marker: str | None, deadline: float, spin_label: str | None = None) -> str:
        """Read until `marker` appears or `deadline` elapses. When
        `spin_label` is given, animate a spinner in place while waiting
        (each recv() naturally ticks it every ~0.5s via the socket
        timeout) so a slow or hung command is visibly still "alive"
        rather than leaving a frozen terminal -- the CLI-UX anti-pattern
        of silent output for anything that isn't instant.
        """
        buf = b""
        end = time.time() + deadline
        frame = 0
        spinning = spin_label is not None and _IS_TTY
        if spinning:
            sys.stdout.write(f"{GREEN}{_SPINNER_FRAMES[frame]} {spin_label}{RESET}")
            sys.stdout.flush()
        while time.time() < end:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                if spinning:
                    frame = (frame + 1) % len(_SPINNER_FRAMES)
                    sys.stdout.write(f"{CLEAR_LINE}{GREEN}{_SPINNER_FRAMES[frame]} {spin_label}{RESET}")
                    sys.stdout.flush()
                continue
            if not chunk:
                break
            buf += chunk
            if marker and marker.encode() in buf:
                break
        if spinning:
            sys.stdout.write(CLEAR_LINE)
            sys.stdout.flush()
        return _clean(buf)

    def run(self, cmd: str, timeout: float = 10) -> str:
        """Run one command and return its output, without the echoed
        input line or shell prompts. Detects completion via a unique
        marker instead of a fixed sleep, so it neither clips slow
        commands nor waits longer than it has to for fast ones."""
        if self.sock is None:
            self.connect()
        marker = f"__done_{time.time_ns()}__"
        self.sock.sendall(cmd.encode() + b"\n")
        self.sock.sendall(f"echo {marker}\n".encode())
        raw = self._read_until(marker, deadline=timeout, spin_label="waiting for device...")
        body = raw.split(marker)[0]
        # The shell prints its "/ # " prompt with no trailing newline, so
        # a command's first output line often lands right after it on the
        # same physical line -- strip a leading prompt from every line,
        # not just lines that are only the prompt.
        body = re.sub(r"(?m)^/\s*#\s*", "", body)
        lines = [
            line
            for line in body.splitlines()
            if line.strip() and line.strip() not in (cmd.strip(), f"echo {marker}")
        ]
        return "\n".join(lines).strip()


# --- Individual tests -------------------------------------------------
# Each takes the live IPadShell and prints whatever's useful. Keep them
# short; the menu loop handles headers, errors, and "press enter".


def action_kernel_info(shell: IPadShell) -> None:
    print(shell.run("uname -a"))
    print()
    print(shell.run("cat /proc/version"))


def action_network_stats(shell: IPadShell) -> None:
    print(shell.run("cat /proc/net/dev"))


def action_backlight_show(shell: IPadShell) -> None:
    print("max:    " + shell.run(f"cat {BACKLIGHT}/max_brightness"))
    print("actual: " + shell.run(f"cat {BACKLIGHT}/actual_brightness"))


def action_backlight_set(shell: IPadShell) -> None:
    maxb = shell.run(f"cat {BACKLIGHT}/max_brightness").strip()
    raw = input(f"New brightness (0-{maxb}): ").strip()
    try:
        val = int(raw)
    except ValueError:
        print("Not a number, cancelled.")
        return
    shell.run(f"echo {val} > {BACKLIGHT}/brightness")
    print(f"Set to {val}.")


def action_rtc_show(shell: IPadShell) -> None:
    print(shell.run("date"))
    print(shell.run("hwclock -r"))


def action_dmesg_tail(shell: IPadShell) -> None:
    print(shell.run("dmesg | tail -n 40"))


def action_usb_dmesg(shell: IPadShell) -> None:
    print(shell.run("dmesg | grep -iE 'dwc2|usb|gadget|ecm' | tail -n 30"))


def action_bt_dmesg(shell: IPadShell) -> None:
    # 20a0cc000 is UART3's own register base (see
    # docs/plans/2026-09-08-j81-bluetooth-battery-adt.md's "BT-1") --
    # included explicitly so a probe failure for *this* UART instance
    # doesn't get lost among unrelated serial/tty noise from the console
    # UART or other subsystems.
    print(shell.run(
        "dmesg | grep -iE '20a0cc000|serial3|ttysac3|samsung-uart|bluetooth|hci|bcm43' "
        "| tail -n 30"
    ))


def action_tty_devices(shell: IPadShell) -> None:
    # Confirms whether the kernel actually created a tty node for UART3
    # (independent of Bluetooth-specific concerns) -- the first thing to
    # check before anything HCI-related can be attempted at all.
    print(shell.run("ls -la /dev/tty[A-Z]* 2>&1"))  # covers ttySAC*, ttyS*, etc. -- no overlap
    print()
    # "s3c2410_serial" is drivers/tty/serial/samsung_tty.c's own
    # registered driver_name (checked in the source, not guessed) --
    # ttySAC is just the /dev/ node prefix, a separate field.
    print(shell.run("cat /proc/tty/driver/s3c2410_serial 2>&1 || echo '(no s3c2410_serial entry)'"))


def action_bt_status(shell: IPadShell) -> None:
    print(shell.run("ls -la /sys/class/bluetooth/ 2>&1"))


def action_bt_probe(shell: IPadShell) -> None:
    # Keep this import lazy so the existing console remains usable as a single
    # file, while the standalone probe can also be run from a shell.
    from bt_probe import collect_snapshot

    print(collect_snapshot(shell), end="")


def action_bt_attach(shell: IPadShell) -> None:
    # btattach (BlueZ tools/btattach.c) has no daemonize flag -- it blocks
    # in its own event loop until killed, so it has to be launched
    # backgrounded rather than run to completion like the console's other
    # commands. The current transport-only DT has no Bluetooth serdev child,
    # so this manual attach keeps the raw UART test independent of DT binding.
    existing = shell.run("ls /sys/class/bluetooth 2>&1")
    if "hci0" in existing:
        print(f"hci0 already attached:\n{existing}")
        return
    shell.run(
        f"nohup btattach -B {BT_TTY} -P bcm -S {BT_SPEED} "
        ">/tmp/btattach.log 2>&1 & disown",
        timeout=5,
    )
    print(f"Started btattach against {BT_TTY} @ {BT_SPEED} baud, waiting...")
    time.sleep(2)
    print(shell.run("ls -la /sys/class/bluetooth/ 2>&1"))
    print()
    print(shell.run("cat /tmp/btattach.log 2>&1"))
    print()
    print(shell.run(
        "dmesg | grep -iE '20a0cc000|ttysac1|bluetooth|hci|bcm43' | tail -n 20"
    ))


PMU_I2C_BUS = 0
PMU_I2C_ADDR = "0x3c"  # pmu,d2207 (BT-3): confirmed at /sys/bus/i2c/devices/0-003c


def action_pmu_read(shell: IPadShell) -> None:
    # BT-3 (docs/plans/2026-09-08-j81-bluetooth-battery-adt.md): read-only
    # register scan of the PMU chip that also backs RTC/backlight, looking
    # for the GPIO2 control register power_enable needs. -f: the kernel's
    # own apple,i2c-pmic driver already owns this address, so i2c-dev
    # treats it as "reserved" without it -- harmless for a plain read.
    raw = input("Register address (hex, e.g. 0x300): ").strip()
    try:
        addr = int(raw, 16)
    except ValueError:
        print("Not a valid hex address, cancelled.")
        return
    length_raw = input("Bytes to read [16]: ").strip() or "16"
    try:
        length = int(length_raw)
    except ValueError:
        print("Not a number, cancelled.")
        return
    hi, lo = (addr >> 8) & 0xFF, addr & 0xFF
    cmd = (
        f"i2ctransfer -f -y {PMU_I2C_BUS} w2@{PMU_I2C_ADDR} "
        f"0x{hi:02x} 0x{lo:02x} r{length}"
    )
    print(f"$ {cmd}")
    print(shell.run(cmd, timeout=8))


def action_uptime_mem(shell: IPadShell) -> None:
    print(shell.run("uptime"))
    print(shell.run("free 2>&1 || head -5 /proc/meminfo"))


def action_raw_command(shell: IPadShell) -> None:
    cmd = input("Command to run: ")
    if not cmd.strip():
        return
    print(shell.run(cmd, timeout=15))


ACTIONS: list[tuple[str, Callable[["IPadShell"], None]]] = [
    ("Kernel info (uname, version)", action_kernel_info),
    ("Network stats (usb0)", action_network_stats),
    ("Backlight: show brightness", action_backlight_show),
    ("Backlight: set brightness", action_backlight_set),
    ("RTC: show date/time", action_rtc_show),
    ("Kernel log: last 40 lines", action_dmesg_tail),
    ("Kernel log: USB/gadget only", action_usb_dmesg),
    ("Kernel log: UART3/Bluetooth only", action_bt_dmesg),
    ("Bluetooth: UART3 tty device check", action_tty_devices),
    ("Bluetooth: hci0 status", action_bt_status),
    ("Bluetooth: safe read-only snapshot", action_bt_probe),
    ("Bluetooth: attach HCI UART (btattach)", action_bt_attach),
    ("PMU: read I2C register (pmu,d2207 @ 0x3c)", action_pmu_read),
    ("Uptime & memory", action_uptime_mem),
    ("Run a raw shell command", action_raw_command),
]


# --- Menu loop ----------------------------------------------------------


def _print_header(connected: bool) -> None:
    status = f"{GREEN}CONNECTED{RESET}" if connected else f"{RED}DISCONNECTED{RESET}"
    print(CLEAR, end="")
    print(GREEN + BOLD + "=" * 56 + RESET)
    print(GREEN + BOLD + "   IPAD AIR 2 / T7001 -- DIAGNOSTIC CONSOLE" + RESET)
    print(GREEN + BOLD + "=" * 56 + RESET)
    print(f" link: {HOST}:{PORT}   status: {status}")
    print(GREEN + "-" * 56 + RESET)


def _pause() -> None:
    input("\nPress Enter to continue...")


def main_menu(shell: IPadShell) -> None:
    while True:
        _print_header(shell.sock is not None)
        for i, (label, _fn) in enumerate(ACTIONS, start=1):
            print(f"  {GREEN}[{i:2}]{RESET} {label}")
        print(f"  {GREEN}[ r]{RESET} Reconnect")
        print(f"  {GREEN}[ q]{RESET} Quit")
        print(GREEN + "-" * 56 + RESET)

        try:
            choice = input("select> ").strip().lower()
        except EOFError:
            break
        if choice == "q":
            break
        if choice == "r":
            try:
                shell.close()
                shell.connect()
                print(f"{GREEN}{CHECK} Reconnected.{RESET}")
            except OSError as exc:
                print(f"{RED}{CROSS} Reconnect failed: {exc}{RESET}")
            _pause()
            continue

        try:
            idx = int(choice) - 1
            if not 0 <= idx < len(ACTIONS):
                raise ValueError
        except ValueError:
            print(f"{RED}Invalid choice.{RESET}")
            _pause()
            continue

        label, fn = ACTIONS[idx]
        print(CLEAR, end="")
        print(GREEN + BOLD + f">>> {label}" + RESET)
        print(GREEN + "-" * 56 + RESET)
        try:
            fn(shell)
        except (OSError, socket.timeout) as exc:
            print(f"\n{RED}[connection error: {exc}]{RESET}")
            shell.close()
        except Exception as exc:  # noqa: BLE001 -- keep the menu alive either way
            print(f"\n{RED}[error: {exc}]{RESET}")
        print(GREEN + "-" * 56 + RESET)
        _pause()


def main() -> int:
    shell = IPadShell()
    print(CLEAR, end="")
    # Gerund while working, past tense (with a clear pass/fail marker) once
    # settled, overwriting the same line rather than leaving a stale
    # "...ing" message behind once the outcome is known.
    sys.stdout.write(f"{GREEN}Connecting to iPad debug shell...{RESET}")
    sys.stdout.flush()
    try:
        shell.connect()
        sys.stdout.write(f"{CLEAR_LINE}{GREEN}{CHECK} Connected to iPad debug shell.{RESET}\n")
    except OSError as exc:
        sys.stdout.write(f"{CLEAR_LINE}{RED}{CROSS} Could not connect: {exc}{RESET}\n")
        print("Check the USB link is up (networksetup -setmanual ... 172.16.42.2/24),")
        print("and that the iPad is sitting at the postmarketOS debug shell.")
        print("You can retry from the menu's [r] Reconnect option.")
    try:
        main_menu(shell)
    finally:
        shell.close()
    print("Bye.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
