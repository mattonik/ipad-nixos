"""Exercise offline orchestration, pinning and stop-on-failure behavior."""
import hashlib
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import j81_gpc_page5_kpoll_campaign as c

BOOT = '12345678-1234-1234-1234-123456789abc'
RESULT = dict(mode='paired', raw=1, polls=5, prewrite_ns=9, postwrite_ns=8, first=0, first_ns=7, later=0, later_ns=100007)

class FakeSocket:
    def __enter__(self): return self
    def __exit__(self, *args): pass

with tempfile.TemporaryDirectory() as d:
    d = Path(d); bundle = d/'bundle'; bundle.mkdir()
    original = c.FILES
    try:
        # Unpinned or partly pinned bundles never reach the device.
        c.FILES = dict(original, **{'j81-gpc-page5-kpoll.ko': None})
        with patch.object(c.campaign, 'verify_bundle', side_effect=AssertionError('reached base bundle')):
            try: c.verify(); raise AssertionError('unpinned bundle accepted')
            except ValueError: pass
        c.FILES = {name: hashlib.sha256(name.encode()).hexdigest() for name in original}
        for name in c.FILES: (bundle/name).write_bytes(name.encode())
        calls = []
        commands = [('stage',['stage']),('pmgr',['pmgr']),('bridge',['bridge']),('gpc',['forbidden'])]
        def execute(command, **kwargs): calls.append(command[0]); return SimpleNamespace(returncode=0)
        common = lambda: (patch.object(c,'BUNDLE',bundle), patch.object(c.campaign,'verify_bundle',return_value=['x']),
                          patch.object(c.campaign,'preflight',return_value='preflight'), patch.object(c.campaign,'parse_preflight',return_value=BOOT),
                          patch.object(c.campaign,'commands',return_value=commands),
                          patch.object(c,'stage',side_effect=lambda host,path,data: calls.append(path)),
                          patch('socket.create_connection',return_value=FakeSocket()))
        from contextlib import ExitStack
        with ExitStack() as s:
            for p in common(): s.enter_context(p)
            s.enter_context(patch.object(c.subprocess,'run',side_effect=execute))
            capture = s.enter_context(patch.object(c.kpoll,'capture',return_value=RESULT))
            c.run(d/'run', 'paired')
            assert calls == ['stage','pmgr','bridge','/tmp/j81-gpc-page5-kpoll.ko','/tmp/gpu-gpc-page5-kpoll-run','/tmp/gpu-watchdog-supervisor'], calls
            args = capture.call_args.args
            assert args[2] == c.FILES['j81-gpc-page5-kpoll.ko'] and args[3] == c.FILES['gpu-watchdog-supervisor'] and args[4] == c.FILES['gpu-gpc-page5-kpoll-run']
            assert args[5] == BOOT and args[6] == 'paired'
            # A used log directory or an unknown mode stops before the device is touched.
            calls.clear()
            for bad in (lambda: c.run(d/'run', 'paired'), lambda: c.run(d/'other', 'write')):
                try: bad(); raise AssertionError('bad run accepted')
                except (OSError, ValueError): pass
            assert not calls
        # A failed bridge stage stops before anything of this test is staged or run.
        calls.clear()
        with ExitStack() as s:
            for p in common(): s.enter_context(p)
            s.enter_context(patch.object(c.subprocess,'run',side_effect=lambda command, **k: (calls.append(command[0]), SimpleNamespace(returncode=command[0] == 'bridge'))[1]))
            capture = s.enter_context(patch.object(c.kpoll,'capture',return_value=RESULT))
            try: c.run(d/'run2', 'immediate'); raise AssertionError('bridge failure ignored')
            except RuntimeError: pass
            assert calls == ['stage','pmgr','bridge'] and not capture.called
        (bundle/'j81-gpc-page5-kpoll.ko').write_bytes(b'corrupt')
        with patch.object(c,'BUNDLE',bundle), patch.object(c.campaign,'verify_bundle',return_value=[]):
            try: c.verify(); raise AssertionError('corrupt module accepted')
            except ValueError: pass
    finally: c.FILES = original
print('PASS: campaign refuses unpinned bundles, stages after bridge, pins boot and mode, stops on failure')
