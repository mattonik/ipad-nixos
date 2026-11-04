#!/usr/bin/env python3
"""Test capture ordering and failures without connecting to the iPad."""
from pathlib import Path
import socket
import tempfile
import threading

from gpu_pmgr_capture import READY, capture

DONE = b"stage=after-pmgr-read raw=0x000000f0 target=0 actual=15 auto=0 reset=0\r\n"

with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "capture.log"
    host, device = socket.socketpair()
    errors = []

    def peer():
        try:
            assert device.recv(128) == b"/tmp/gpu-pmgr-peek\n"
            device.sendall(READY[:18])
            device.sendall(READY[18:] + b"\r\n")
            assert device.recv(128) == b"READ\n"
            assert READY in path.read_bytes()
            device.sendall(DONE)
        except BaseException as error:
            errors.append(error)
        finally:
            device.close()

    thread = threading.Thread(target=peer)
    thread.start()
    with host:
        capture(host, path, 3)
    thread.join()
    assert not errors, errors
    assert DONE in path.read_bytes()
    assert path.stat().st_mode & 0o777 == 0o600

    host, device = socket.socketpair()
    device.close()
    try:
        with host:
            capture(host, path, 1)
    except FileExistsError:
        pass
    else:
        raise AssertionError("existing logs must not be overwritten")

    host, device = socket.socketpair()
    def incomplete_peer():
        device.recv(128)
        device.sendall(b"no stage marker\n")
        device.close()
    thread = threading.Thread(target=incomplete_peer)
    thread.start()
    try:
        with host:
            capture(host, Path(directory) / "incomplete.log", 1)
    except RuntimeError:
        pass
    else:
        raise AssertionError("incomplete capture must fail")
    thread.join()

    host, device = socket.socketpair()
    def stale_peer():
        device.recv(128)
        device.sendall(DONE + READY + b"\r\n")
        assert device.recv(128) == b"READ\n"
        device.close()
    thread = threading.Thread(target=stale_peer)
    thread.start()
    try:
        with host:
            capture(host, Path(directory) / "stale.log", 1)
    except RuntimeError:
        pass
    else:
        raise AssertionError("completion before acknowledgement must not succeed")
    thread.join()
print("PASS: marker persisted before acknowledgement; incomplete capture fails")
