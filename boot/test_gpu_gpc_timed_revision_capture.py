#!/usr/bin/env python3
"""Exercise the complete wrapper + probe dialogue with a simulated telnet peer."""
import socket
import tempfile
import threading
from pathlib import Path
from gpu_gpc_timed_revision_capture import STAGES, capture


def run(fault=None):
    host, peer = socket.socketpair()
    errors = []
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "capture.log"

        def device():
            try:
                command = peer.recv(2048)
                assert b"--core-revision-cycle " + b"a" * 64 in command
                peer.sendall(b"stage=before-watchdog-open\n")
                assert peer.recv(16) == b"ARM\n"
                peer.sendall(b"ARM\nstage=watchdog-armed timeout=20\n")
                results = (
                    b"stage=after-pmgr-read raw=0x000003ff target=15 actual=15 auto=0 reset=0\n",
                    b"stage=after-pmgr-read raw=0x000003ff\n",
                    b"stage=after-gpc-state raw=0x00000000\n",
                    b"stage=after-timed-sequence raw=0x00070300\n",
                )
                for index, result in enumerate(results):
                    peer.sendall(STAGES[index] + b"\n")
                    assert peer.recv(16) == b"READ\n"
                    peer.sendall(b"READ\n")
                    if fault == "bad-wrapper-pmgr" and index == 0:
                        peer.sendall(b"stage=after-pmgr-read raw=0x00000300 target=0 actual=0 auto=0 reset=0\n")
                        return
                    if fault == "bad-probe-pmgr" and index == 1:
                        peer.sendall(b"stage=after-pmgr-read raw=0x00000300\n")
                        return
                    if fault == "pipeline" and index == 0:
                        peer.sendall(result + STAGES[index + 1] + b"\n")
                        return
                    if fault == "wrong-result" and index == 2:
                        peer.sendall(b"stage=after-gpc-control raw=0x40000000\n")
                        return
                    if fault == "bad-gpc" and index == 2:
                        peer.sendall(b"stage=after-gpc-state raw=0x00000001\n")
                        return
                    if index == 3 and fault != "missing-poll":
                        peer.sendall(b"checkpoint=gpc-poll-ok raw=0x00000001 polls=2\ncheckpoint=before-gpu-revision\n")
                    if fault == "core-stall" and index == 3:
                        return
                    peer.sendall(result)
                    if fault == "missing-poll" and index == 3:
                        return
                    assert peer.recv(16) == f"FEED {index + 1}\n".encode()
                    peer.sendall(f"FEED {index + 1}\n".encode())
                peer.sendall(b"stage=finished rc=0\n")
                peer.sendall(b"stage=watchdog-disarmed\n")
            except BaseException as error:
                errors.append(error)
            finally:
                peer.close()

        thread = threading.Thread(target=device)
        thread.start()
        if fault:
            try:
                capture(host, path, "a" * 64, 3, "b" * 64, "c" * 64)
                raise AssertionError(f"fault accepted: {fault}")
            except RuntimeError:
                if fault == "core-stall":
                    assert b"checkpoint=gpc-poll-ok" in path.read_bytes()
                    assert b"checkpoint=before-gpu-revision" in path.read_bytes()
        else:
            with host:
                result = capture(host, path, "a" * 64, 3, "b" * 64, "c" * 64)
            assert result == {"gpu-revision": 0x70300}
        thread.join()
        assert not errors, errors


run()
run(fault="bad-wrapper-pmgr")
run(fault="bad-probe-pmgr")
run(fault="bad-gpc")
run(fault="wrong-result")
run(fault="pipeline")
run(fault="missing-poll")
run(fault="core-stall")
print("PASS: wrapper and probe PMGR reads, strict stage/result ordering, echoes, watchdog feeds, and fail-closed gates")
