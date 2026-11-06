#!/usr/bin/env python3
"""Check the one-shot host handshake without connecting to a device."""
from pathlib import Path
import socket
import tempfile
import threading

from gpu_power_capture import capture, PEEK_READY

MODULE = "a" * 64
NOTES = "b" * 64
READY = f"stage=before-gfx-power module={MODULE} kernel_notes={NOTES}\r\n".encode()
DONE = b"stage=after-gfx-power rc=0\r\n"
PEEK_DONE = b"stage=after-pmgr-read raw=0x00000300 target=0 actual=0 auto=0 reset=0\r\n"


def exercise(path, mode):
    host, device = socket.socketpair()
    errors = []
    finished = threading.Event()

    def peer():
        try:
            command = device.recv(512)
            assert command == f"/tmp/gpu-pmgr-once-run {MODULE} {NOTES}\n".encode()
            if mode == "stale":
                device.sendall(DONE)
                return
            if mode == "stale-pmgr":
                device.sendall(PEEK_DONE)
                return
            device.sendall(PEEK_READY + b"\r\n")
            assert device.recv(128) == b"READ\n"
            assert PEEK_READY in path.read_bytes()
            if mode == "wrong-state":
                device.sendall(PEEK_DONE.replace(b"0x00000300", b"0x0000030f"))
                return
            device.sendall(PEEK_DONE + READY[:31])
            device.sendall(READY[31:])
            assert device.recv(128) == b"POWER\n"
            assert READY in path.read_bytes()
            if mode == "success":
                device.sendall(DONE)
            elif mode == "error":
                device.sendall(b"stage=after-gfx-power rc=1\r\n")
            elif mode == "timeout":
                finished.wait(4)
        except BaseException as error:
            errors.append(error)
        finally:
            device.close()

    thread = threading.Thread(target=peer)
    thread.start()
    try:
        with host:
            capture(host, path, MODULE, NOTES, 2)
        assert mode == "success", mode
    except RuntimeError:
        assert mode != "success", mode
    finally:
        finished.set()
    thread.join()
    assert not errors, errors
    assert path.stat().st_mode & 0o777 == 0o600


with tempfile.TemporaryDirectory(prefix="gpu-capture-") as tmp:
    for mode in ("success", "error", "stale", "stale-pmgr", "incomplete", "wrong-state", "timeout"):
        exercise(Path(tmp) / mode, mode)
    host, device = socket.socketpair()
    try:
        with host:
            try:
                capture(host, Path(tmp) / "bad-hash", "x" * 64, NOTES, 1)
            except ValueError:
                pass
            else:
                raise AssertionError("invalid hash accepted")
    finally:
        device.close()
print("PASS: durable checkpoint, fresh completion, errors and disconnects")
