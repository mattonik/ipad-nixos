#!/usr/bin/env python3
"""Test persisted GPC markers and failure handling without hardware."""
import socket
import tempfile
import threading
from pathlib import Path
from gpu_gpc_capture import STAGES, capture


def run_peer(path, payloads, expected, state_only=False):
    host, device = socket.socketpair()
    errors = []
    def peer():
        try:
            assert device.recv(256) == b"/tmp/gpu-gpc-peek-run " + b"a" * 64 + b"\n"
            for data, acknowledge in payloads:
                device.sendall(data)
                if acknowledge:
                    assert device.recv(128) == b"READ\n"
                    assert data.strip() in path.read_bytes()
        except BaseException as error:
            errors.append(error)
        finally:
            device.close()
    thread = threading.Thread(target=peer)
    thread.start()
    failed = False
    try:
        with host:
            capture(host, path, "a" * 64, 3, state_only)
    except RuntimeError:
        failed = True
    thread.join()
    assert failed == expected
    assert not errors, errors


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    pmgr, state, control = (item[0] + b"\r\n" for item in STAGES)
    pmgr_result = b"stage=after-pmgr-read raw=0x000003ff target=15 actual=15 auto=0 reset=0\r\n"
    prefix = [(pmgr, True), (pmgr_result, False)]
    result1 = b"stage=after-gpc-state raw=0x00000001\r\n"
    result2 = b"stage=after-gpc-control raw=0x20000000\r\n"
    run_peer(root / "ok", prefix + [(state, True), (result1, False), (control, True), (result2, False)], False)
    assert (root / "ok").stat().st_mode & 0o777 == 0o600
    run_peer(root / "state-only", prefix + [(state, True), (result1.replace(b"00000001", b"00000000"), False)], False, True)
    run_peer(root / "stale", prefix + [(result1, False)], True)
    run_peer(root / "wrong", prefix + [(control, False)], True)
    run_peer(root / "pipelined", prefix + [(state + result1, False)], True)
    run_peer(root / "bad-state", prefix + [(state, True), (result1.replace(b"00000001", b"00000010"), False)], True)
    run_peer(root / "bad-pmgr", [(pmgr, True), (pmgr_result.replace(b"003ff", b"00300"), False)], True)
    run_peer(root / "partial", prefix + [(state, True)], True)
print("PASS: GPC capture checkpoint order and incomplete capture handling")
