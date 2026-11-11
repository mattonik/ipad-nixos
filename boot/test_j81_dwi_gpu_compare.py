#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import j81_dwi_gpu_compare as c
import j81_gpc_page5_kpoll_campaign as k

BOOT = '12345678-1234-1234-1234-123456789abc'


def sample(value=0):
    words = dict.fromkeys(c.OFFSETS, 0)
    words['20120'] = value
    return words


class TestDwiCampaign(unittest.TestCase):
    def test_pmgr_exact_and_no_duplicates(self):
        text = '\n'.join('w 0x%06x raw=0x00000000' % int(x, 16) for x in c.OFFSETS)
        text += '\nstage=after-pmgr-words-read\n'
        self.assertEqual(set(c.parse_words(text)), set(c.OFFSETS))
        with self.assertRaises(ValueError):
            c.parse_words(text + 'w 0x020120 raw=0x00000000\n')
        with self.assertRaises(ValueError):
            c.parse_words(text.replace('stage=after-pmgr-words-read', 'missing'))

    def test_sequence_and_boot_pinning(self):
        events = []
        def snap(boot, directory, label):
            self.assertEqual(boot, BOOT)
            events.append(label)
            return sample(0x200 if label == 'before-dwi' else 0xff)
        def remote(command, boot, log):
            if '20120' in command:
                events.append('pre-request-dwi')
                return 'w 0x020120 raw=0x000000ff\nstage=after-pmgr-words-read\n'
            events.append('dwi')
            return 'result=on polls=0\n'
        def dwi(sock, boot, log):
            events.append('dwi')
        def campaign(path, mode, expected_boot_id, before_kpoll):
            events.append('campaign')
            before_kpoll(expected_boot_id)
            self.assertEqual(mode, 'paired')
            self.assertEqual(expected_boot_id, BOOT)
        with tempfile.TemporaryDirectory() as d, \
             patch.object(c, 'verify'), patch.object(c.subprocess, 'run', return_value=MagicMock(returncode=0, stdout='GO: gpc-page5-kpoll\n', stderr='')), \
             patch.object(c.base, 'preflight', return_value='ok'), \
             patch.object(c.base, 'parse_preflight', return_value=BOOT), \
             patch.object(c, 'stage'), patch.object(c, 'snapshot', side_effect=snap), \
             patch.object(c, 'remote', side_effect=remote), patch.object(c, 'dwi_capture', side_effect=dwi), \
             patch.object(c.socket, 'create_connection', return_value=MagicMock()), patch.object(c.kpoll, 'run', side_effect=campaign), \
             patch.object(c.time, 'sleep'):
            c.run(Path(d) / 'capture')
        self.assertEqual(events, ['before-dwi', 'dwi', 'before-gpc', 'campaign', 'pre-request-dwi', 'after-gpc', 'after-10s'])

    def test_dwi_failure_stops_before_campaign(self):
        with tempfile.TemporaryDirectory() as d, \
             patch.object(c, 'verify'), patch.object(c.subprocess, 'run', return_value=MagicMock(returncode=0, stdout='GO: gpc-page5-kpoll\n', stderr='')), \
             patch.object(c.base, 'preflight', return_value='ok'), \
             patch.object(c.base, 'parse_preflight', return_value=BOOT), \
             patch.object(c, 'stage'), patch.object(c, 'snapshot', return_value=sample()), \
             patch.object(c, 'dwi_capture', side_effect=RuntimeError('DWI failed')), \
             patch.object(c.socket, 'create_connection', return_value=MagicMock()), \
             patch.object(c.kpoll, 'run') as run:
            with self.assertRaises(RuntimeError):
                c.run(Path(d) / 'capture')
            run.assert_not_called()


    def test_dwi_acknowledges_only_checkpointed_accesses(self):
        class FakeSocket:
            def __init__(self):
                self.sent = []
                self.parts = iter([
                    b'stage=before-dwi-read address=0x20e020120 width=32\n',
                    b'stage=after-dwi-read raw=0x00000200 target=0 actual=0\n',
                    b'stage=before-dwi-write address=0x20e020120 set=0xf\n',
                    b'stage=after-dwi-write raw=0x000000ff target=15 actual=15\nresult=on polls=0\n'])
            def sendall(self, data): self.sent.append(data)
            def settimeout(self, timeout): pass
            def recv(self, count): return next(self.parts, b'')
        with tempfile.TemporaryDirectory() as d:
            sock = FakeSocket()
            c.dwi_capture(sock, BOOT, Path(d) / 'dwi.log')
            self.assertEqual(sock.sent[1:], [b'READ\n', b'WRITE\n'])
            self.assertIn('boot_id', sock.sent[0].decode())

    def test_changed_boot_stops_before_mutations(self):
        with tempfile.TemporaryDirectory() as d, patch.object(k, 'verify', return_value=[]), \
             patch.object(k.campaign, 'preflight', return_value='ok'), \
             patch.object(k.campaign, 'parse_preflight', return_value=BOOT), \
             patch.object(k.campaign, 'commands') as commands:
            with self.assertRaisesRegex(ValueError, 'boot ID changed'):
                k.run(Path(d) / 'capture', 'paired', expected_boot_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
            commands.assert_not_called()


if __name__ == '__main__':
    unittest.main()
