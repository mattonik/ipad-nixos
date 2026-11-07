#!/usr/bin/env python3
"""Exercise the bridge host protocol using synthetic data and sockets."""
import hashlib
import socket
import struct
import tempfile
import threading
from pathlib import Path
import gpu_bridge_capture as m

offsets=[0x18]+list(range(0x40000,0x40080,4))
table=b''.join(struct.pack('<II',o,i) for i,o in enumerate(offsets))
plan=table*2
m.TABLE_SHA=hashlib.sha256(table).hexdigest()
m.PLAN_SHA=hashlib.sha256(plan).hexdigest()
steps=m.plan_steps(plan)
assert len(steps)==67
try:m.plan_steps(plan[:-1])
except ValueError:pass
else:raise AssertionError('short plan accepted')


def run(path,limit,wrong=False,supervised=False,simulate=False,cycle=False):
    host,device=socket.socketpair();errors=[]
    def peer():
        try:
            command = (b'/tmp/gpu-watchdog-supervisor --simulate-bridge ' if simulate else b'/tmp/gpu-watchdog-supervisor --bridge-cycle ' if cycle else b'/tmp/gpu-watchdog-supervisor --bridge ') if supervised else b'/tmp/gpu-bridge-once-run '
            received=device.recv(512)
            assert (command+b'a'*64+b'\n') in received
            if supervised:
                assert b'b'*64 in received
                expected_wrapper = m.SIM_WRAPPER_SHA if simulate else 'c'*64 if cycle else m.BRIDGE_WRAPPER_SHA
                assert expected_wrapper.encode() in received
            if supervised:
                device.sendall(b'stage=before-watchdog-open\r\n');assert device.recv(20)==b'ARM\n'
                device.sendall(b'stage=watchdog-armed timeout=20\r\n')
            device.sendall(m.PMGR_BEFORE+b'\r\n');assert device.recv(20)==b'READ\n'
            device.sendall(m.PMGR_AFTER+b'\r\n')
            if supervised: assert device.recv(20)==b'FEED 1\n'
            for i,(name,address,op,value) in enumerate(steps):
                if i==limit:break
                if wrong and i==2: address+=4
                line=f'stage=before-{name} address=0x{address:x} op={op} value=0x{value:08x}\r\n'.encode()
                device.sendall(line)
                if wrong and i==2:break
                assert device.recv(20)==b'ACCESS\n'
                assert line.strip() in path.read_bytes()
                device.sendall(f'stage=after-{name} value=0x{value:08x}\r\n'.encode())
                if supervised: assert device.recv(20)==f'FEED {i+2}\n'.encode()
            if limit>=len(steps) and not wrong:
                device.sendall(b'stage=finished rc=0\r\n')
                if supervised:device.sendall(b'stage=watchdog-disarmed\r\n')
        except BaseException as e:errors.append(e)
        finally:device.close()
    t=threading.Thread(target=peer);t.start();failed=False
    try:
        with host:m.capture(host,path,'a'*64,plan,10,supervised,'b'*64 if supervised else None,simulate,cycle,'c'*64 if cycle else None)
    except RuntimeError:failed=True
    t.join();assert not errors,errors
    assert failed == (limit<len(steps) or wrong)


with tempfile.TemporaryDirectory() as d:
    p=Path(d)
    run(p/'complete',67)
    run(p/'supervised',67,supervised=True)
    run(p/'cycle-payload',67,supervised=True,cycle=True)
    run(p/'simulated',67,supervised=True,simulate=True)
    run(p/'supervised-partial',4,supervised=True)
    run(p/'cycle-partial',4,supervised=True,cycle=True)
    run(p/'partial',4)
    run(p/'wrong',67,True)
    assert (p/'complete').stat().st_mode & 0o777 == 0o600
print('PASS: bridge plan checksum, per-access checkpoints, ordering and aborts')
