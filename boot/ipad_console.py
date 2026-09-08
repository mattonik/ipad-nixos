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
import re
import socket
import sys
import time
from collections.abc import Callable

HOST = "172.16.42.1"
PORT = 23

GREEN = "\033[32m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"
CLEAR = "\033[2J\033[H"

BACKLIGHT = "/sys/class/backlight/20a110000.i2c:pmic@3c:backlight@600"
RTC = "/sys/class/rtc/rtc0"

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

    def _read_until(self, marker: str | None, deadline: float) -> str:
        buf = b""
        end = time.time() + deadline
        while time.time() < end:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break
            buf += chunk
            if marker and marker.encode() in buf:
                break
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
        raw = self._read_until(marker, deadline=timeout)
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
                print("Reconnected.")
            except OSError as exc:
                print(f"{RED}Reconnect failed: {exc}{RESET}")
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
    print(GREEN + "Connecting to iPad debug shell..." + RESET)
    try:
        shell.connect()
    except OSError as exc:
        print(f"{RED}Could not connect: {exc}{RESET}")
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
