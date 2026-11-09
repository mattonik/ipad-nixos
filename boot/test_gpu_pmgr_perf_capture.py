#!/usr/bin/env python3
"""Exercise the perf capture handshake without a device."""
import socket
import tempfile
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import gpu_pmgr_perf_capture as capture


def output():
    lines = ["ps raw=0x000000ff", "ctl raw=0x80000003", "perf-tunable raw=0x40000001"]
    for n in range(16):
        lines += [f"perf{n:02d} raw=0x{0x11000000 + n:08x}",
                  f"perf{n:02d}-p4 raw=0x{0x22000000 + n:08x}"]
    return ("\r\n".join(lines + ["stage=after-perf-read", ""])).encode()


class FakeSocket:
    def __init__(self, path, chunks):
        self.path, self.chunks = path, iter(chunks)
        self.sent = []
        self.acked_after_persist = False

    def sendall(self, data):
        self.sent.append(data)
        if data == b"READ\n":
            self.acked_after_persist = capture.READY in self.path.read_bytes()

    def settimeout(self, timeout):
        pass

    def recv(self, size):
        try:
            return next(self.chunks)
        except StopIteration:
            raise socket.timeout


with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "capture.log"
    ready = capture.READY
    chunks = [b"prefix " + ready[:23], ready[23:] + b"\n", output()]
    sock = FakeSocket(path, chunks)
    result = capture.capture(sock, path, 2)
    assert sock.sent == [b"/tmp/gpu-pmgr-perf-peek\n", b"READ\n"]
    assert sock.acked_after_persist
    assert capture.complete_output(result)
    assert capture.READY in path.read_bytes() and capture.DONE in path.read_bytes()

    incomplete = Path(directory) / "incomplete.log"
    sock = FakeSocket(incomplete, [capture.READY, b"ctl raw=0x00000000\n" + capture.DONE + b"\n"])
    try:
        capture.capture(sock, incomplete, 2)
        raise AssertionError("incomplete output accepted")
    except RuntimeError as error:
        assert "exactly one value" in str(error)

    duplicate = Path(directory) / "duplicate.log"
    sock = FakeSocket(duplicate, [capture.READY, output() + b"ctl raw=0x80000003\n"])
    try:
        capture.capture(sock, duplicate, 2)
        raise AssertionError("duplicate output accepted")
    except RuntimeError as error:
        assert "exactly one value" in str(error)

    timed_out = Path(directory) / "timeout.log"
    sock = FakeSocket(timed_out, [b"no ready marker"])
    try:
        capture.capture(sock, timed_out, 1)
        raise AssertionError("missing READY accepted")
    except RuntimeError as error:
        assert "capture incomplete" in str(error)

    staged = []
    with patch.object(sys, "argv", ["gpu_pmgr_perf_capture.py", "missing", "bad-hash", "unused",
                                   "--timeout", "301"]), \
         patch.object(capture, "stage", lambda *args: staged.append(args)):
        try:
            capture.main()
            raise AssertionError("invalid timeout accepted")
        except SystemExit as error:
            assert error.code == 2
    assert not staged

print("PASS: perf capture persists before ACK and validates complete output/timeout")
