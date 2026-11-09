#!/usr/bin/env python3
"""Test campaign gates and fail-stop ordering without connecting to a device."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile
import gpu_campaign as c

boot = 'db572110-5c85-4f55-bc10-16f7cda746ac'
assert c.parse_preflight(f'echo CAMPAIGN_GOOD\r\nCAMPAIGN_BOOT={boot}\r\nCAMPAIGN_GOOD\r\nCAMPAIGN_END\r\n') == boot
for bad in ('CAMPAIGN_GOOD\n', f'CAMPAIGN_BOOT={boot}\n',
            f'CAMPAIGN_BOOT={boot}\nCAMPAIGN_GOOD\nCAMPAIGN_GOOD\n'):
    try:
        c.parse_preflight(bad)
        raise AssertionError('accepted invalid preflight')
    except ValueError:
        pass

bundle = c.ROOT / 'artifacts/live/gpu-test-bundle-timed-revision-v3'
# Bundle files are private/local; synthetic inputs exercise logic without them.
with tempfile.TemporaryDirectory() as d:
    paths = Path(d)
    for mode in ('gpc-control', 'paced', 'timed'):
        commands = c.commands(mode, bundle, paths, ['bin/x'])
        expected = {'gpc-control': ['stage', 'pmgr', 'bridge', 'gpc'],
                    'paced': ['stage', 'pmgr', 'bridge', 'gpc', 'core'],
                    'timed': ['stage', 'pmgr', 'bridge', 'timed']}
        assert [name for name, _ in commands] == expected[mode]
        assert commands[-1][1][1].endswith({'gpc-control': 'gpu_gpc_init_capture.py',
            'paced': 'gpu_core_revision_capture.py', 'timed': 'gpu_gpc_timed_revision_capture.py'}[mode])
    calls = []
    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=1 if len(calls) == 3 else 0)
    with patch.object(c, 'verify_bundle', return_value=['bin/x']), patch.object(c, 'preflight', return_value=f'CAMPAIGN_BOOT={boot}\nCAMPAIGN_GOOD\nCAMPAIGN_END\n'), patch.object(c.subprocess, 'run', side_effect=fake_run), patch('sys.argv', ['gpu_campaign.py', 'timed', str(paths / 'run')]):
        try:
            c.main()
            raise AssertionError('campaign failed to stop')
        except SystemExit as e:
            assert e.code == 1
    assert len(calls) == 3
    assert f'CAMPAIGN_BOOT={boot}' in (paths / 'run' / 'preflight.log').read_text()
print('PASS: preflight validation, mode selection, and stop after failed step')
