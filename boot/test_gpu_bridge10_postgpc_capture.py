#!/usr/bin/env python3
"""Exercise supervised post-GPC comparison with synthetic bridge values."""
import socket
import tempfile
import threading
from pathlib import Path
from gpu_bridge10_postgpc_capture import STAGES, capture

host, device = socket.socketpair()
errors = []
values = {b"bridge10-18": 0x80010004}

def peer():
    try:
        command = device.recv(1024)
        assert b"--postgpc-cycle " + b"a"*64 in command
        assert b"b"*64 in command and b"c"*64 in command
        device.sendall(b"\xff\xfb\x01\xff\xfd\x03" + command.replace(b"\n", b"\r\n"))
        device.sendall(b"stage=before-watchdog-open\n"); assert device.recv(32) == b"ARM\n"
        device.sendall(b"ARM\r\nstage=watchdog-armed timeout=20\n")
        feed = 0
        for before in STAGES:
            device.sendall(before+b"\n"); assert device.recv(32) == b"READ\n"
            if before == STAGES[0]: after = b"stage=after-pmgr-read raw=0x000003ff target=15 actual=15 auto=0 reset=0"
            elif before == STAGES[1]: after = b"stage=after-gpc-state raw=0x00000001"
            elif before == STAGES[2]: after = b"stage=after-gpc-control raw=0x40000000"
            else:
                key = b"bridge10-18"
                after = b"stage=after-"+key+b" raw=0x"+f"{values[key]:08x}".encode()
            device.sendall(b"READ\r\n"+after+b"\n")
            feed += 1; command=f"FEED {feed}".encode(); assert device.recv(32) == command+b"\n"
            device.sendall(command+b"\r\n")
        device.sendall(b"stage=finished rc=0\nstage=watchdog-disarmed\n")
    except BaseException as error:
        errors.append(error)
    finally:
        device.close()

with tempfile.TemporaryDirectory() as directory:
    thread = threading.Thread(target=peer); thread.start()
    with host:
        actual = capture(host, Path(directory)/"capture", "a"*64, 3, True, "b"*64, "c"*64)
    thread.join()
    assert not errors, errors
    assert actual == {"bridge10-18": 0x80010004}
print("PASS: supervised post-GPC read stages and arbitrary-value comparison")

host, device = socket.socketpair()
def out_of_order_peer():
    device.recv(1024)
    device.sendall(b"stage=before-watchdog-open\n"); assert device.recv(32) == b"ARM\n"
    device.sendall(b"stage=watchdog-armed timeout=20\n" + STAGES[0] + b"\n")
    assert device.recv(32) == b"READ\n"
    device.sendall(STAGES[1] + b"\n")

with tempfile.TemporaryDirectory() as directory:
    thread = threading.Thread(target=out_of_order_peer); thread.start()
    try:
        with host:
            capture(host, Path(directory)/"capture", "a"*64, 3, True, "b"*64, "c"*64)
        raise AssertionError("out-of-order checkpoint was accepted")
    except RuntimeError as error:
        assert str(error) == "unexpected checkpoint"
    finally:
        device.close(); thread.join()
print("PASS: supervised post-GPC capture rejects out-of-order checkpoints")
