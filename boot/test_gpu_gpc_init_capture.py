#!/usr/bin/env python3
"""Check GPC init acknowledgement ordering and failure gates offline."""
import socket
import tempfile
import threading
from pathlib import Path
from gpu_gpc_init_capture import FIXED, PMGR_AFTER, PMGR_BEFORE, capture


def before(name, offset, operation, value):
    return f"stage=before-{name} address=0x{0x201e00000+offset:x} op={operation} value=0x{value:08x}\r\n".encode()


def after(name, value):
    return f"stage=after-{name} value=0x{value:08x}\r\n".encode()


def run(path, steps, should_fail):
    host, device = socket.socketpair()
    errors = []
    def peer():
        try:
            assert device.recv(256) == b"/tmp/gpu-gpc-init-run " + b"a" * 64 + b"\n"
            for line, ack in steps:
                device.sendall(line)
                if ack:
                    assert device.recv(32) == ack
                    assert line.strip() in path.read_bytes()
        except BaseException as e:
            errors.append(e)
        finally:
            device.close()
    t = threading.Thread(target=peer)
    t.start()
    failed = False
    try:
        with host:
            assert capture(host, path, "a" * 64, 3) == 1
    except RuntimeError:
        failed = True
    t.join()
    assert failed == should_fail and not errors, (failed, errors)


def run_supervised(path):
    host, device = socket.socketpair()
    errors = []
    def peer():
        try:
            command = device.recv(512)
            assert b"--gpc-init-cycle " + b"a" * 64 in command
            assert b"--gpu-gpc-init-cycle-run" not in command
            assert b"gpu-gpc-init-cycle-run" in command and b"b" * 64 in command and b"c" * 64 in command
            device.sendall(b"stage=before-watchdog-open\n"); assert device.recv(32) == b"ARM\n"
            device.sendall(b"stage=watchdog-armed timeout=20\n")
            for line, ack in [(PMGR_BEFORE, b"READ\n"), (PMGR_AFTER, None)]:
                device.sendall(line+b"\n")
                if ack: assert device.recv(32) == ack
            assert device.recv(32) == b"FEED 1\n"
            feed = 1
            sequence = list(FIXED) + [("poll-00", 0x1000, "read", 0), ("poll-01", 0x1000, "read", 0)]
            values = [*([v for _,_,_,v in FIXED]), 0x11, 1]
            for (name, offset, operation, expected), value in zip(sequence, values):
                device.sendall(before(name, offset, operation, expected)+b"\n")
                assert device.recv(32) == b"ACCESS\n"
                device.sendall(after(name, value)+b"\n")
                feed += 1; assert device.recv(32) == f"FEED {feed}\n".encode()
            device.sendall(b"stage=finished rc=0\n")
            device.sendall(b"stage=watchdog-disarmed\n")
        except BaseException as error:
            errors.append(error)
        finally:
            device.close()
    thread=threading.Thread(target=peer); thread.start()
    failed = False
    with host:
        try: assert capture(host, path, "a"*64, 3, True, "b"*64, "c"*64) == 1
        except RuntimeError: failed = True
    thread.join(); assert not failed and not errors, (failed, errors)


pmgr = [(PMGR_BEFORE + b"\r\n", b"READ\n"), (PMGR_AFTER + b"\r\n", None)]
fixed = []
for name, offset, operation, value in FIXED:
    fixed += [(before(name, offset, operation, value), b"ACCESS\n"), (after(name, value), None)]
poll0 = [(before("poll-00", 0x1000, "read", 0), b"ACCESS\n"), (after("poll-00", 0x11), None)]
poll1 = [(before("poll-01", 0x1000, "read", 0), b"ACCESS\n"), (after("poll-01", 1), None)]
with tempfile.TemporaryDirectory() as directory:
    p = Path(directory)
    run_supervised(p / "supervised")
    run(p / "ok", pmgr + fixed + poll0 + poll1 + [(b"stage=finished rc=0\r\n", None)], False)
    run(p / "bad-pmgr", [(PMGR_BEFORE+b"\r\n", b"READ\n"), (PMGR_AFTER.replace(b"003ff", b"00300")+b"\r\n", None)], True)
    run(p / "bad-initial", pmgr + [(before(*FIXED[0]), b"ACCESS\n"), (after("initial-state", 1), None)], True)
    run(p / "wrong-order", pmgr + [(before(*FIXED[1]), None)], True)
    run(p / "early-result", pmgr + [(before(*FIXED[0]) + after("initial-state", 0), None)], True)
    run(p / "poll-wrong", pmgr + fixed + [(before("poll-00",0x1000,"read",0), b"ACCESS\n"), (after("poll-00", 2), None)], True)
    run(p / "incomplete", pmgr + fixed + poll0, True)
    run(p / "bad-finish", pmgr + fixed + [(before("poll-00",0x1000,"read",0), b"ACCESS\n"), (after("poll-00",1), None), (b"stage=finished rc=1\r\n", None)], True)
    all_busy = []
    for i in range(64):
        name = f"poll-{i:02d}"
        all_busy += [(before(name,0x1000,"read",0), b"ACCESS\n"), (after(name,0x11), None)]
    run(p / "poll-limit", pmgr + fixed + all_busy, True)
print("PASS: GPC init durable checkpoints, order, state and completion gates")
