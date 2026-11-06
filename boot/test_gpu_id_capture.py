#!/usr/bin/env python3
"""Test durable checkpoints and ID guard failures with a simulated device."""
import socket
import tempfile
import threading
from pathlib import Path
from gpu_id_capture import STAGES, capture


def run(path, script, fails):
    host, peer = socket.socketpair()
    errors=[]
    def device():
        try:
            assert peer.recv(256)==b"/tmp/gpu-id-once-run "+b"a"*64+b"\n"
            for data,ack in script:
                peer.sendall(data)
                if ack:
                    assert peer.recv(128)==b"READ\n"
                    assert data.strip() in path.read_bytes()
        except BaseException as e: errors.append(e)
        finally: peer.close()
    t=threading.Thread(target=device);t.start();failed=False
    try:
        with host:capture(host,path,"a"*64,3)
    except RuntimeError:failed=True
    t.join();assert failed==fails and not errors,(failed,errors)


with tempfile.TemporaryDirectory() as d:
    p=Path(d)
    markers=[s[0]+b"\r\n" for s in STAGES]
    pmgr=b"stage=after-pmgr-read raw=0x000003ff target=15 actual=15 auto=0 reset=0\r\n"
    state=b"stage=after-gpc-state raw=0x00000001\r\n"
    ctrl=b"stage=after-gpc-control raw=0x40000000\r\n"
    rev=b"stage=after-gpu-revision raw=0x00070300\r\n"
    core=b"stage=after-gpu-core-id raw=0x00000803\r\n"
    prefix=[(markers[0],1),(pmgr,0),(markers[1],1),(state,0),(markers[2],1),(ctrl,0)]
    run(p/"ok",prefix+[(markers[3],1),(rev,0),(markers[4],1),(core,0),(b"stage=finished rc=0\r\n",0)],False)
    run(p/"state",[(markers[0],1),(pmgr,0),(markers[1],1),(state.replace(b"00000001",b"00000000"),0)],True)
    run(p/"handshake",prefix[:-1]+[(ctrl.replace(b"40000000",b"60000000"),0)],True)
    run(p/"zero-revision",prefix+[(markers[3],1),(rev.replace(b"00070300",b"00000000"),0)],True)
    run(p/"pipelined",prefix+[(markers[3]+rev,0)],True)
    run(p/"incomplete",prefix+[(markers[3],1)],True)
print("PASS: GPU ID capture guard, checkpoint ordering and failure handling")
