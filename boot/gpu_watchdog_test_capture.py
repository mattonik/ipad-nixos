#!/usr/bin/env python3
"""Capture watchdog supervisor's simulated control tests, never GPU MMIO."""
import argparse
import os
import socket
import time
from pathlib import Path


def capture(sock, path, mode, digest, timeout):
    if mode not in ('ok', 'stall') or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('invalid mode or digest')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb', buffering=0) as log:
        parent = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(parent)
        finally: os.close(parent)
        command = ("test \"$(sha256sum /tmp/gpu-watchdog-supervisor | cut -d ' ' -f 1)\" = " + digest +
                   " && /tmp/gpu-watchdog-supervisor --simulate-" + mode + "\n")
        sock.sendall(command.encode())
        expected = [
            (b'stage=before-watchdog-open', b'ARM\n'),
            (b'stage=watchdog-armed timeout=20', None),
            (b'stage=before-sim address=0x0 op=read value=0x00000000', b'ACCESS\n'),
            (b'stage=after-sim value=0x00000000', b'FEED 1\n'),
        ]
        if mode == 'ok':
            expected += [(b'stage=finished rc=0', None), (b'stage=watchdog-disarmed', None)]
        index, buffer, deadline = 0, b'', time.monotonic() + timeout
        while time.monotonic() < deadline:
            sock.settimeout(min(1.0, max(0.001, deadline - time.monotonic())))
            try: data = sock.recv(4096)
            except TimeoutError: continue
            if not data: break
            log.write(data); os.fsync(log.fileno()); buffer += data
            if len(buffer) > 65536: raise RuntimeError('capture too large')
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1); line = line.strip(b'\r')
                if not line.startswith(b'stage='): continue
                if index >= len(expected) or line != expected[index][0]: raise RuntimeError('unexpected stage')
                log.write(b'\nhost-verified ' + line + b'\n'); os.fsync(log.fileno())
                ack = expected[index][1]
                if ack:
                    if b'stage=' in buffer: raise RuntimeError('pipelined stage')
                    sock.sendall(ack)
                index += 1
                if mode == 'ok' and index == len(expected): return 'disarmed'
        if mode == 'stall' and index == len(expected): return 'stall-observed-reset-unconfirmed'
        raise RuntimeError('incomplete capture; device state unknown')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('ok', 'stall')); p.add_argument('sha256'); p.add_argument('log', type=Path)
    args = p.parse_args()
    try:
        with socket.create_connection(('172.16.42.1', 23), 5) as sock:
            print(capture(sock, args.log, args.mode, args.sha256, 40))
    except (OSError, ValueError, RuntimeError) as error:
        p.exit(1, f'capture failed: {error}; device state may be unknown\n')


if __name__ == '__main__': main()
