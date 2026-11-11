import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import j81_wide_power_compare as w

BOOT = '12345678-1234-1234-1234-123456789abc'


def transcript():
    result = [b'stage=before-ps-read count=20\n']
    for name, offset in w.DOMAINS:
        result.append(f'stage=ps-read name={name} address=0x{0x20e020000+offset:x} raw=0x00000200\n'.encode())
    for name, offset in w.DOMAINS:
        result.append(f'stage=before-ps-write name={name} address=0x{0x20e020000+offset:x} raw=0x00000200 set=0xf\n'.encode())
        result.append(f'result=on name={name} raw=0x000000ff polls=0\n'.encode())
    result.append(b'result=all-on\n')
    return result


class Socket:
    def __init__(self, parts): self.parts = iter(parts); self.sent = []
    def sendall(self, data): self.sent.append(data)
    def settimeout(self, value): pass
    def recv(self, size): return next(self.parts, b'')


class RestoreTests(unittest.TestCase):
    def check(self, parts, good):
        with tempfile.TemporaryDirectory() as d:
            sock = Socket(parts)
            if good:
                w.restore_capture(sock, BOOT, Path(d) / 'log')
            else:
                with self.assertRaises(RuntimeError):
                    w.restore_capture(sock, BOOT, Path(d) / 'log')
            return sock

    def test_complete_order(self):
        sock = self.check(transcript(), True)
        self.assertEqual(sock.sent[1:], [b'READ\n'] + [b'WRITE\n'] * 20)
        self.assertLess([x[0] for x in w.DOMAINS].index('isp'), [x[0] for x in w.DOMAINS].index('venc'))

    def test_bad_baseline_never_writes(self):
        parts = transcript(); parts[2] = parts[2].replace(b'00000200', b'80000200')
        sock = self.check(parts, False)
        self.assertNotIn(b'WRITE\n', sock.sent)

    def test_wrong_domain_and_stall_stop(self):
        parts = transcript(); parts[21] = parts[21].replace(b'name=dwi', b'name=isp')
        self.assertNotIn(b'WRITE\n', self.check(parts, False).sent)
        sock = self.check(transcript()[:23], False)
        self.assertEqual(sock.sent.count(b'WRITE\n'), 1)


    def test_domain_snapshot_requires_all_active(self):
        values = [f'w 0x{0x20000+offset:06x} raw=0x000000ff' for _, offset in w.DOMAINS]
        values.append('stage=after-pmgr-words-read')
        with patch.object(w.dwi, 'remote', return_value='\n'.join(values)):
            self.assertEqual(len(w.domain_snapshot(BOOT, Path('/unused'), True)), 20)
        values[7] = values[7].replace('000000ff', '00000200')
        with patch.object(w.dwi, 'remote', return_value='\n'.join(values)):
            with self.assertRaises(ValueError):
                w.domain_snapshot(BOOT, Path('/unused'), True)
            self.assertEqual(len(w.domain_snapshot(BOOT, Path('/unused'), False)), 20)

    def test_active_domain_is_skipped(self):
        parts = transcript()
        parts[21:23] = [b'result=already-on name=dwi raw=0x000000ff\n']
        sock = self.check(parts, True)
        self.assertEqual(sock.sent.count(b'WRITE\n'), 19)


if __name__ == '__main__': unittest.main()
