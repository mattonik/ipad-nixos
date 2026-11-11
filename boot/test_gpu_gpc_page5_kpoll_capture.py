"""Exercise host ordering, result parsing, fail-closed faults and lost-host handling."""
import socket
import tempfile
import threading
from pathlib import Path
from gpu_gpc_page5_kpoll_capture import capture, describe, parse_result

BOOT = '12345678-1234-1234-1234-123456789abc'
LINES = {
    'immediate': b'result=ok mode=immediate raw=0x00000001 polls=5 prewrite_ns=300400 postwrite_ns=300000 first_valid=1 first=0x40000000 first_ns=250 later_valid=0 later=0x00000000 later_ns=0',
    'paired': b'result=ok mode=paired raw=0x00000001 polls=5 prewrite_ns=300400 postwrite_ns=300000 first_valid=1 first=0x40000000 first_ns=250 later_valid=1 later=0x00000000 later_ns=100600',
    'delayed': b'result=ok mode=delayed raw=0x00000001 polls=1 prewrite_ns=300400 postwrite_ns=300000 first_valid=0 first=0x00000000 first_ns=0 later_valid=1 later=0x00000000 later_ns=100300',
}
r = parse_result(LINES['paired'], 'paired')
assert r['first'] == 0x40000000 and r['later'] == 0 and r['polls'] == 5 and r['first_ns'] == 250
assert parse_result(LINES['immediate'], 'immediate')['later'] is None
assert parse_result(LINES['delayed'], 'delayed')['first'] is None
text = '\n'.join(describe(r)); assert 'bit 30 set' in text and 'bit 30 clear' in text and 'less than 250 ns' in text
BAD = [
    (LINES['paired'], 'immediate'),                                              # mode mismatch
    (LINES['immediate'].replace(b'raw=0x00000001', b'raw=0x00000002'), 'immediate'),  # invalid GPC state
    (LINES['immediate'].replace(b'raw=0x00000001', b'raw=0x00000011'), 'immediate'),  # busy
    (LINES['immediate'].replace(b'polls=5', b'polls=0'), 'immediate'),
    (LINES['immediate'].replace(b'polls=5', b'polls=1001'), 'immediate'),
    (LINES['immediate'].replace(b'first_valid=1', b'first_valid=0'), 'immediate'),    # missing sample is not zero
    (LINES['immediate'].replace(b'later_valid=0', b'later_valid=1'), 'immediate'),
    (LINES['delayed'].replace(b'first=0x00000000', b'first=0x40000000'), 'delayed'),
    (LINES['paired'].replace(b'later_ns=100600', b'later_ns=99999'), 'paired'),
    (LINES['immediate'].replace(b'first_ns=250', b'first_ns=0'), 'immediate'),
    (LINES['immediate'].replace(b'prewrite_ns=300400', b'prewrite_ns=300000'), 'immediate'),
    (LINES['immediate'] + b' extra=1', 'immediate'),
    (LINES['immediate'].replace(b'first=0x40000000', b'first=0x4000000'), 'immediate'),
    (b'result=poll-failed mode=immediate raw=0x00000011 polls=1000', 'immediate'),
]
for line, mode in BAD:
    try: parse_result(line, mode); raise AssertionError(f'accepted {line!r}')
    except RuntimeError: pass


def run(mode='immediate', fault=None):
    host, peer = socket.socketpair(); errors = []
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / 'capture.log'
        def device():
            try:
                command = peer.recv(2048)
                assert b'--gpc-page5-kpoll ' + b'a' * 64 + b' ' + BOOT.encode() + b' ' + mode.encode() + b'\n' in command
                assert b'gpu-gpc-page5-kpoll-run | cut' in command and b'b' * 64 in command and b'c' * 64 in command
                peer.sendall(b'stage=before-watchdog-open\n'); assert peer.recv(16) == b'ARM\n'
                peer.sendall(b'stage=watchdog-armed timeout=20\n')
                peer.sendall(b'stage=before-pmgr-read address=0x20e020320 width=32\n'); assert peer.recv(16) == b'READ\n'
                peer.sendall(b'stage=after-pmgr-read raw=0x000003f0 target=0 actual=15 auto=0 reset=0\n' if fault == 'pmgr' else b'stage=after-pmgr-read raw=0x000003ff target=15 actual=15 auto=0 reset=0\n')
                if fault == 'pmgr': return
                assert peer.recv(16) == b'FEED 1\n'
                peer.sendall(b'stage=before-gpc-state address=0x201e01000 width=32\n'); assert peer.recv(16) == b'READ\n'
                peer.sendall(b'stage=after-gpc-state raw=0x00000001\n' if fault == 'state' else b'stage=after-gpc-state raw=0x00000000\n')
                if fault == 'state': return
                assert peer.recv(16) == b'FEED 2\n'
                if fault == 'early-checkpoint': peer.sendall(b'checkpoint=before-kernel-batch\n'); return
                peer.sendall(b'stage=before-gpc-page5-kpoll address=0x20e005004 width=32 mode=' + (b'paired' if fault == 'wrong-mode' else mode.encode()) + b'\n')
                if fault == 'wrong-mode': return
                assert peer.recv(16) == b'READ\n'
                peer.sendall(b'checkpoint=before-kernel-batch\n')
                if fault == 'stall': return
                if fault == 'poll-failed':
                    peer.sendall(b'checkpoint=kernel-batch result=poll-failed mode=' + mode.encode() + b' raw=0x00000011 polls=1000\nstage=finished rc=1\n'); return
                line = LINES[mode]
                if fault != 'no-checkpoint': peer.sendall(b'checkpoint=kernel-batch ' + line + b'\n')
                peer.sendall(b'stage=after-gpc-page5-kpoll ' + (line.replace(b'0x40000000', b'0x00000000') if fault == 'differs' else line) + b'\n')
                if fault in ('no-checkpoint', 'differs'): return
                assert peer.recv(16) == b'FEED 3\n'
                if fault == 'no-disarm': peer.sendall(b'stage=finished rc=0\n'); return
                peer.sendall(b'stage=finished rc=0\nstage=watchdog-disarmed\n')
            except BaseException as e: errors.append(e)
            finally: peer.close()
        t = threading.Thread(target=device); t.start()
        try:
            if fault:
                try: capture(host, path, 'a'*64, 'b'*64, 'c'*64, BOOT, mode, 3); raise AssertionError(f'{fault} accepted')
                except RuntimeError as e: message = str(e)
                if fault == 'poll-failed': assert 'raw=0x00000011 polls=1000' in message and 'no page-5 sample' in message
            else:
                result = capture(host, path, 'a'*64, 'b'*64, 'c'*64, BOOT, mode, 3)
                assert result == parse_result(LINES[mode], mode)
        finally: host.close(); t.join()
        assert not errors, errors
        data = path.read_bytes()
        if fault in ('stall', 'poll-failed'): assert b'checkpoint=before-kernel-batch' in data
        if fault == 'poll-failed': assert b'raw=0x00000011 polls=1000' in data


for mode in LINES: run(mode)
for fault in ('pmgr', 'state', 'early-checkpoint', 'wrong-mode', 'stall', 'poll-failed', 'no-checkpoint', 'differs', 'no-disarm'): run(fault=fault)
for bad in (('a'*63, 'b'*64, 'c'*64, BOOT, 'immediate'), ('a'*64, 'b'*64, 'c'*64, 'boot', 'immediate'), ('a'*64, 'b'*64, 'c'*64, BOOT, 'write')):
    try: capture(None, Path('/nonexistent/x'), *bad); raise AssertionError('bad argument accepted')
    except ValueError: pass
print('PASS: host parses every mode, rejects malformed results, stalls, poll failure, lost host and missing disarm')
