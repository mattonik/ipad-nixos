#!/usr/bin/env python3
"""Exercise the supervised bridge-peek collector without hardware."""
import socket
import tempfile
import threading
import time
from pathlib import Path
import gpu_bridge_peek_capture as m

def run(fail_at=None):
    host, device = socket.socketpair()
    errors = []
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "peek.log"
        def peer():
            try:
                command = device.recv(1024)
                assert b"--bridge-peek " + b"a" * 64 in command
                assert b"= " + b"b" * 64 in command and b"= " + b"c" * 64 in command
                stages = [
                    (b"stage=before-watchdog-open\r\n", b"ARM\n"),
                    (b"stage=watchdog-armed timeout=20\r\n", None),
                    (m.PMGR_BEFORE + b"\r\n", b"READ\n"),
                    (m.PMGR_AFTER + b"\r\n", b"FEED 1\n"),
                    (b"stage=before-gpc-state address=0x201e01000 op=read value=0x00000000\r\n", b"ACCESS\n"),
                    (b"stage=after-gpc-state value=0x00000000\r\n", b"FEED 2\n"),
                    (b"stage=before-bridge-peek address=0x201f00018 op=read value=0x00000000\r\n", b"ACCESS\n"),
                    (b"stage=after-bridge-peek value=0x12345678\r\n", b"FEED 3\n"),
                    (b"stage=finished rc=0\r\n", None),
                    (b"stage=watchdog-disarmed\r\n", None),
                ]
                for index, (line, ack) in enumerate(stages):
                    if fail_at == index:
                        device.sendall(b"stage=unexpected\r\n"); return
                    device.sendall(line)
                    if ack: assert device.recv(32) == ack
            except BaseException as error:
                errors.append(error)
            finally: device.close()
        thread = threading.Thread(target=peer); thread.start()
        try:
            value = m.capture(host, path, "a" * 64, "b" * 64, "c" * 64, 2)
            assert value == "12345678" and fail_at is None
        except RuntimeError: assert fail_at is not None
        thread.join(); assert not errors, errors
        assert path.stat().st_mode & 0o777 == 0o600
        if fail_at is None: assert b"host-verified stage=after-bridge-peek value=0x12345678" in path.read_bytes()

run(); run(6)
host, device = socket.socketpair()
with tempfile.TemporaryDirectory() as directory:
    thread = threading.Thread(target=lambda: (device.recv(1024), time.sleep(0.05)), daemon=True)
    thread.start()
    try:
        m.capture(host, Path(directory) / "stall.log", "a" * 64, "b" * 64, "c" * 64, 1)
    except (RuntimeError, TimeoutError):
        pass
    else:
        raise AssertionError("stalled child accepted")
    device.close()
for value in ("bad", "0" * 63):
    try: m.capture(socket.socketpair()[0], Path("/tmp/unused"), value, "b" * 64, "c" * 64)
    except ValueError: pass
    else: raise AssertionError("invalid hash accepted")
print("PASS: supervised bridge-peek checkpoints, persistence, ordering and validation")
