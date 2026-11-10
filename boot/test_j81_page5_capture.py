#!/usr/bin/env python3
"""Exercise page-5 capture ordering without connecting to a device."""
import socket
import tempfile
import threading
from pathlib import Path

from j81_page5_capture import capture

H = "a" * 64
BOOT = "12345678-1234-1234-1234-123456789abc"
STAGES = [
    (b"stage=before-watchdog-open\r\n", b"ARM\n"),
    (b"stage=watchdog-armed timeout=20\r\n", None),
    (b"stage=before-page5-read address=0x20e005000 width=32\r\n", b"READ\n"),
    (b"stage=after-page5-read address=0x20e005000 value=0x12345678\r\n", b"FEED 1\n"),
    (b"stage=finished rc=0\r\n", None),
    (b"stage=watchdog-disarmed\r\n", None),
]

with tempfile.TemporaryDirectory() as td:
    host, device = socket.socketpair()
    path = Path(td) / "page5.log"
    errors = []

    def peer():
        try:
            command = device.recv(4096)
            assert b"--page5-read-once " + H.encode() + b" " + H.encode() + b" " + BOOT.encode() in command
            device.sendall(command + b"\r\n")  # telnet shell echo
            for line, ack in STAGES:
                device.sendall(line)
                if ack:
                    got = device.recv(32)
                    assert got == ack, (got, ack)
                    if line.startswith(b"stage=before-page5-read"):
                        assert b"host-verified stage=before-page5-read" in path.read_bytes()
            device.sendall(b"\r\n# ")  # post-command shell prompt
        except BaseException as error:
            errors.append(error)
        finally:
            device.close()

    thread = threading.Thread(target=peer)
    thread.start()
    with host:
        result = capture(host, path, H, H, BOOT, H, H, 0, 3)
    thread.join()
    assert not errors, errors
    assert result == "stage=after-page5-read address=0x20e005000 value=0x12345678"
    assert path.stat().st_mode & 0o777 == 0o600
    assert b"host-verified stage=watchdog-disarmed" in path.read_bytes()

    host, device = socket.socketpair()
    def early_exit():
        device.recv(4096)
        device.sendall(b"stage=finished rc=0\r\n")
        device.close()
    thread = threading.Thread(target=early_exit)
    thread.start()
    try:
        with host:
            capture(host, Path(td) / "early.log", H, H, BOOT, H, H, 0, 1)
    except RuntimeError:
        pass
    else:
        raise AssertionError("early completion must fail closed")
    thread.join()
    for offset in (4, 8):
        host, device = socket.socketpair()
        address = f"0x{0x20e005000 + offset:x}"
        def peer_offset():
            command = device.recv(4096)
            assert command.rstrip().endswith(str(offset).encode())
            for line, ack in STAGES:
                device.sendall(line.replace(b"0x20e005000", address.encode()))
                if ack:
                    assert device.recv(32) == ack
            device.close()
        thread = threading.Thread(target=peer_offset)
        thread.start()
        with host:
            result = capture(host, Path(td) / f"page5-{offset}.log", H, H, BOOT, H, H, offset, 3)
        thread.join()
        assert result == f"stage=after-page5-read address={address} value=0x12345678"
    host, device = socket.socketpair()
    try:
        try:
            capture(host, Path(td) / "invalid.log", H, H, BOOT, H, H, 12, 1)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid offset accepted")
    finally:
        host.close()
        device.close()
print("PASS: page-5 host acknowledgement precedes the actual read and completion")
