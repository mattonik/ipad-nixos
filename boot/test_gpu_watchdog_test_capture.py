#!/usr/bin/env python3
"""Validate the control-test collector's durable ordered acknowledgements."""
import socket
import tempfile
import threading
from pathlib import Path
from gpu_watchdog_test_capture import capture


def run(path, mode, wrong=False):
    host, peer = socket.socketpair(); errors = []
    def device():
        try:
            command = peer.recv(512)
            assert b'--simulate-' + mode.encode() in command and b'a'*64 in command
            stages=[(b'stage=before-watchdog-open',b'ARM\n'),
                    (b'stage=watchdog-armed timeout=20',None),
                    (b'stage=before-sim address=0x0 op=read value=0x00000000',b'ACCESS\n'),
                    (b'stage=after-sim value=0x00000000',b'FEED 1\n')]
            if mode=='ok': stages += [(b'stage=finished rc=0',None),(b'stage=watchdog-disarmed',None)]
            for i,(stage,ack) in enumerate(stages):
                if wrong and i==2: peer.sendall(b'stage=unexpected\n');return
                peer.sendall(stage+b'\n')
                if ack:
                    assert peer.recv(128)==ack
                    assert b'host-verified '+stage in path.read_bytes()
        except BaseException as error:errors.append(error)
        finally:peer.close()
    thread=threading.Thread(target=device);thread.start()
    try:
        with host:
            try: result=capture(host,path,mode,'a'*64,3)
            except RuntimeError:
                if not wrong: raise
            else:
                assert not wrong
                assert result==('disarmed' if mode=='ok' else 'stall-observed-reset-unconfirmed')
    finally:thread.join()
    assert not errors, errors

with tempfile.TemporaryDirectory() as d:
    p=Path(d);run(p/'ok','ok');run(p/'stall','stall');run(p/'wrong','ok',True)
    assert (p/'ok').stat().st_mode & 0o777 == 0o600
print('PASS: watchdog control collector verifies and persists stages before acknowledgements')
