#!/usr/bin/env python3
"""Capture one watchdog-supervised in-kernel GPC poll and page-5 sample."""
import argparse
import os
import re
import socket
import time
from pathlib import Path

HEX = re.compile(r"[0-9a-f]{64}\Z")
MODES = ('immediate', 'paired', 'delayed')
LATER_DELAY_NS = 100_000
RESULT = re.compile(
    rb'result=ok mode=(immediate|paired|delayed) raw=0x([0-9a-f]{8}) polls=([0-9]+) '
    rb'prewrite_ns=([0-9]+) postwrite_ns=([0-9]+) '
    rb'first_valid=([01]) first=0x([0-9a-f]{8}) first_ns=([0-9]+) '
    rb'later_valid=([01]) later=0x([0-9a-f]{8}) later_ns=([0-9]+)\Z')


def parse_result(text, mode):
    """Validate the kernel's result line; return its fields or raise."""
    m = RESULT.fullmatch(text)
    if not m or m[1].decode() != mode: raise RuntimeError('invalid kernel batch result')
    r = dict(mode=mode, raw=int(m[2], 16), polls=int(m[3]), prewrite_ns=int(m[4]), postwrite_ns=int(m[5]),
             first=int(m[7], 16) if m[6] == b'1' else None, first_ns=int(m[8]),
             later=int(m[10], 16) if m[9] == b'1' else None, later_ns=int(m[11]))
    if r['raw'] & 0x1f != 1 or not 1 <= r['polls'] <= 1000: raise RuntimeError('kernel reported an invalid GPC poll')
    if (r['first'] is None) != (mode == 'delayed') or (r['later'] is None) != (mode == 'immediate'):
        raise RuntimeError('samples do not match the mode')
    # An absent sample must be all zero so that it cannot be read as a value.
    if r['first'] is None and (m[7] != b'00000000' or r['first_ns']): raise RuntimeError('absent first sample is not zero')
    if r['later'] is None and (m[10] != b'00000000' or r['later_ns']): raise RuntimeError('absent later sample is not zero')
    if r['prewrite_ns'] <= r['postwrite_ns']: raise RuntimeError('write timestamps out of order')
    if r['first'] is not None and r['first_ns'] == 0: raise RuntimeError('first sample has no interval')
    if r['later'] is not None and r['later_ns'] < LATER_DELAY_NS + r['first_ns']: raise RuntimeError('later sample earlier than its delay')
    return r


def capture(sock, path, module_hash, supervisor_hash, wrapper_hash, boot_id, mode, timeout=40):
    if not all(HEX.fullmatch(v or "") for v in (module_hash, supervisor_hash, wrapper_hash)):
        raise ValueError("invalid hash")
    if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", boot_id):
        raise ValueError("invalid boot ID")
    if mode not in MODES: raise ValueError("invalid mode")
    before = (b"stage=before-pmgr-read address=0x20e020320 width=32",
              b"stage=before-gpc-state address=0x201e01000 width=32",
              b"stage=before-gpc-page5-kpoll address=0x20e005004 width=32 mode=" + mode.encode())
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb', buffering=0) as log:
        parent = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(parent)
        finally: os.close(parent)
        command = (f'test "$(sha256sum /tmp/gpu-watchdog-supervisor | cut -d " " -f 1)" = {supervisor_hash} && '
                   f'test "$(sha256sum /tmp/gpu-gpc-page5-kpoll-run | cut -d " " -f 1)" = {wrapper_hash} && '
                   f'/tmp/gpu-watchdog-supervisor --gpc-page5-kpoll {module_hash} {boot_id} {mode}\n')
        sock.sendall(command.encode())
        buf = b''; stage = watchdog = feeds = cp = 0
        awaiting = disarming = False
        checkpoint = result = None; echoes = set(); deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            sock.settimeout(max(.001, min(1., deadline - time.monotonic())))
            try: chunk = sock.recv(4096)
            except TimeoutError: continue
            if not chunk: break
            # Every byte is on disk before the host acknowledges anything.
            log.write(chunk); os.fsync(log.fileno()); buf += chunk
            if len(buf) > 65536: raise RuntimeError('capture exceeded 64 KiB')
            while b'\n' in buf:
                line, buf = buf.split(b'\n', 1); line = line.strip(b'\r')
                if line in echoes: echoes.remove(line); continue
                if line.startswith(b'checkpoint='):
                    if stage != 2 or not awaiting: raise RuntimeError('unexpected checkpoint')
                    if cp == 0 and line == b'checkpoint=before-kernel-batch': cp = 1; continue
                    if cp == 1 and line.startswith(b'checkpoint=kernel-batch result=ok '):
                        checkpoint = line[len(b'checkpoint=kernel-batch '):]; parse_result(checkpoint, mode); cp = 2; continue
                    if cp == 1 and line.startswith(b'checkpoint=kernel-batch result=poll-failed '):
                        raise RuntimeError('GPC poll failed: ' + line.decode(errors='replace') + '; no page-5 sample exists')
                    raise RuntimeError('invalid batch checkpoint')
                if not line.startswith(b'stage='): continue
                if watchdog == 0:
                    if line != b'stage=before-watchdog-open': raise RuntimeError('missing watchdog arm checkpoint')
                    echoes.add(b'ARM'); sock.sendall(b'ARM\n'); watchdog = 1; continue
                if watchdog == 1:
                    if line != b'stage=watchdog-armed timeout=20': raise RuntimeError('watchdog did not arm')
                    watchdog = 2; continue
                if disarming:
                    if line != b'stage=watchdog-disarmed' or b'stage=' in buf: raise RuntimeError('watchdog not disarmed')
                    return result
                if line.startswith(b'stage=before-'):
                    if awaiting or stage >= len(before) or line != before[stage] or b'stage=' in buf: raise RuntimeError('unexpected or pipelined checkpoint')
                    echoes.add(b'READ'); sock.sendall(b'READ\n'); awaiting = True; continue
                if line.startswith(b'stage=after-'):
                    if not awaiting or b'stage=' in buf: raise RuntimeError('unexpected or pipelined result')
                    if stage == 0 and line != b'stage=after-pmgr-read raw=0x000003ff target=15 actual=15 auto=0 reset=0': raise RuntimeError('PMGR not active')
                    if stage == 1 and line != b'stage=after-gpc-state raw=0x00000000': raise RuntimeError('GPC not initially zero')
                    if stage == 2:
                        if cp != 2 or line != b'stage=after-gpc-page5-kpoll ' + checkpoint: raise RuntimeError('invalid batch result')
                        result = parse_result(checkpoint, mode)
                    stage += 1; awaiting = False; feeds += 1
                    echo = f'FEED {feeds}'.encode(); echoes.add(echo); sock.sendall(echo + b'\n'); continue
                if line == b'stage=finished rc=0' and stage == len(before) and not awaiting:
                    disarming = True; continue
                raise RuntimeError('unexpected stage')
    raise RuntimeError('capture incomplete; device state unknown, do not retry this boot')


def describe(r):
    out = [f"GPC poll raw=0x{r['raw']:08x} after {r['polls']} poll(s); last GPC store to successful poll load: "
           f"more than {r['postwrite_ns']} ns, less than {r['prewrite_ns'] + (r['first_ns'] or r['later_ns'])} ns"]
    if r['first'] is not None:
        out.append(f"first page-5 sample 0x{r['first']:08x} (bit 30 {'set' if r['first'] & 0x40000000 else 'clear'}), "
                   f"loaded less than {r['first_ns']} ns after the poll load")
    if r['later'] is not None:
        out.append(f"later page-5 sample 0x{r['later']:08x} (bit 30 {'set' if r['later'] & 0x40000000 else 'clear'}), "
                   f"loaded less than {r['later_ns']} ns after the poll load")
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('log', type=Path); p.add_argument('module_sha256'); p.add_argument('boot_id'); p.add_argument('mode', choices=MODES)
    p.add_argument('--supervisor-sha256', required=True); p.add_argument('--wrapper-sha256', required=True); p.add_argument('--timeout', type=int, default=40)
    a = p.parse_args()
    if not 1 <= a.timeout <= 300: p.error('timeout must be between 1 and 300 seconds')
    try:
        with socket.create_connection(('172.16.42.1', 23), timeout=5) as sock:
            r = capture(sock, a.log, a.module_sha256, a.supervisor_sha256, a.wrapper_sha256, a.boot_id, a.mode, a.timeout)
    except (OSError, RuntimeError, ValueError) as e:
        p.exit(1, f'capture failed: {e}; do not retry this boot\n')
    print('\n'.join(describe(r))); print(a.log)
if __name__ == '__main__': main()
