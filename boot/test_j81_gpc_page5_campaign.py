"""Exercise offline orchestration and stop-on-failure behavior."""
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import j81_gpc_page5_campaign as c

BOOT = '12345678-1234-1234-1234-123456789abc'

class FakeSocket:
    def __enter__(self): return self
    def __exit__(self, *args): pass

with tempfile.TemporaryDirectory() as d:
    d = Path(d); bundle = d/'bundle'; bundle.mkdir()
    original = c.FILES
    try:
        import hashlib
        c.FILES = {name: hashlib.sha256(name.encode()).hexdigest() for name in original}
        for name in c.FILES: (bundle/name).write_bytes(name.encode())
        calls = []
        commands = [('stage',['stage']),('pmgr',['pmgr']),('bridge',['bridge']),('gpc',['forbidden'])]
        def execute(command, **kwargs): calls.append(command[0]); return SimpleNamespace(returncode=0)
        with patch.object(c,'BUNDLE',bundle), patch.object(c.campaign,'verify_bundle',return_value=['x']), \
             patch.object(c.campaign,'preflight',return_value='preflight'), patch.object(c.campaign,'parse_preflight',return_value=BOOT), \
             patch.object(c.campaign,'commands',return_value=commands), patch.object(c.subprocess,'run',side_effect=execute), \
             patch.object(c,'stage',side_effect=lambda host,path,data: calls.append(path)), \
             patch('socket.create_connection',return_value=FakeSocket()), patch.object(c.timed,'capture',return_value=0) as capture:
            c.run(d/'run')
            assert calls[:3] == ['stage','pmgr','bridge'] and 'forbidden' not in calls
            assert capture.call_args.args[-1] == BOOT and len(calls) == 7
        (bundle/'gpu-gpc-page5-timed').write_bytes(b'corrupt')
        with patch.object(c,'BUNDLE',bundle), patch.object(c.campaign,'verify_bundle',return_value=[]):
            try: c.verify(); raise AssertionError('corrupt binary accepted')
            except ValueError: pass
    finally: c.FILES = original
print('PASS: campaign stages bridge then timed probe, pins boot and rejects corruption')
