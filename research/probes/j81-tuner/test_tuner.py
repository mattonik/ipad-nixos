#!/usr/bin/env python3
"""Check the device tracer and its host simulation, then run the latter."""
from pathlib import Path
import subprocess
import tempfile

p = Path(__file__).resolve().parent
device = (p / 'j81_tuner_shell.S').read_text()
host = (p / 'j81-tuner-hosttest.S').read_text()
a = device.split('_j81_tuner_policy_entry:', 1)[1].split('_j81_tuner_identity:', 1)[0]
b = host.split('_j81_tuner_policy_entry:', 1)[1].split('_j81_tuner_identity:', 1)[0]
a = a.replace('ldr x9, _j81_tuner_buffer', 'adrp x9, _test_buffer@PAGE\n add x9, x9, _test_buffer@PAGEOFF')
a = a.replace('mrs x13, tpidr_el1', 'adrp x13, _test_thread@PAGE\n ldr x13, [x13, _test_thread@PAGEOFF]')
a = a.replace(' sub sp, sp, #0x50\n_j81_tuner_policy_entry_resume:\n b _j81_tuner_policy_entry_resume', '_j81_tuner_policy_entry_resume:\n ret')
assert a == b, 'host tuner hooks differ from device hooks'
assert device.count(' sub sp, sp, #0x50\n_j81_tuner_policy_entry_resume:') == 1
assert 'mov w15, #16' in a and 'stlxr w12, w11, [x10]' in a
with tempfile.TemporaryDirectory() as temp:
    binary = Path(temp) / 'tuner-test'
    subprocess.run(['clang', '-arch', 'arm64', '-o', str(binary), str(p / 'j81-tuner-hosttest.S'), str(p / 'j81-tuner-hosttest.c')], check=True)
    subprocess.run([str(binary)], check=True)
print('PASS: host hook body matches device source; bounded exclusive retry')
