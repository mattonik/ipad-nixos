#!/usr/bin/env python3
"""Simulate the checkpointed bridge writer without touching hardware."""
import subprocess
import tempfile
from pathlib import Path

source = Path(__file__).with_name("gpu-bridge-once.c")
harness = Path(__file__).with_name("test-gpu-bridge-sim.c").read_text()
with tempfile.TemporaryDirectory() as d:
    p=Path(d);(p/'test.c').write_text(harness)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(source.parent),str(p/'test.c'),'-o',str(p/'test')],check=True)
    out=subprocess.run([str(p/'test')],check=True,capture_output=True,text=True).stdout
    assert 'stage=after-bridge-10-32' in out and 'stage=finished rc=0' in out
print('PASS: bridge replay offsets, ordering, acknowledgement and one-shot gates')
