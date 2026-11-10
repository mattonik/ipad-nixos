"""Exercise host ordering, fail-closed checkpoints, and recorded result."""
import socket
import tempfile
import threading
from pathlib import Path
from gpu_gpc_page5_timed_capture import BEFORE, capture


def run(fault=None):
    host, peer = socket.socketpair(); errors = []
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / 'capture.log'
        def device():
            try:
                assert b'--gpc-page5-timed ' + b'a' * 64 in peer.recv(2048)
                peer.sendall(b'stage=before-watchdog-open\n'); assert peer.recv(16) == b'ARM\n'
                peer.sendall(b'stage=watchdog-armed timeout=20\n')
                for idx, response in enumerate((b'stage=after-pmgr-read raw=0x000003ff target=15 actual=15 auto=0 reset=0\n', b'stage=after-gpc-state raw=0x00000000\n', b'stage=after-gpc-page5 address=0x20e005004 value=0x40000000\n')):
                    peer.sendall(BEFORE[idx] + b'\n'); assert peer.recv(16) == b'READ\n'
                    if idx == 2:
                        peer.sendall(b'checkpoint=before-gpc-writes\ncheckpoint=before-gpc-poll\ncheckpoint=before-page5-read\n')
                        if fault == 'stall': return
                        peer.sendall(b'checkpoint=gpc-poll-ok raw=0x00000001 polls=1\ncheckpoint=poll-to-sysfs-return-ns value=7000\n' if fault != 'missing-poll' else b'checkpoint=poll-to-sysfs-return-ns value=7000\n')
                    peer.sendall(response)
                    if fault == 'missing-poll' and idx == 2: return
                    assert peer.recv(16) == f'FEED {idx+1}\n'.encode()
                peer.sendall(b'stage=finished rc=0\nstage=watchdog-disarmed\n')
            except BaseException as e: errors.append(e)
            finally: peer.close()
        t = threading.Thread(target=device); t.start()
        try:
            if fault:
                try: capture(host, path, 'a'*64, 'b'*64, 'c'*64, '12345678-1234-1234-1234-123456789abc', 3); raise AssertionError('fault accepted')
                except RuntimeError: pass
            else:
                assert capture(host, path, 'a'*64, 'b'*64, 'c'*64, '12345678-1234-1234-1234-123456789abc', 3) == 0x40000000
        finally: host.close(); t.join()
        assert not errors, errors
        assert b'checkpoint=before-page5-read' in path.read_bytes()

run(); run('stall'); run('missing-poll')
print('PASS: host captures result, rejects stalls and missing poll')
