#!/usr/bin/env python3
"""Compile and run the timed sequence with mocked MMIO, never hardware."""
import subprocess
import tempfile
from pathlib import Path

source = Path(__file__).with_suffix('.c')
with tempfile.TemporaryDirectory() as directory:
    binary = Path(directory) / 'test'
    subprocess.run(['cc', '-std=c11', '-D_POSIX_C_SOURCE=200809L', '-Wall',
                    '-Wextra', '-Werror', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
