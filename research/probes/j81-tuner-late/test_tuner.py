#!/usr/bin/env python3
"""Check the device tracer and its host simulation, then run the latter."""
from pathlib import Path
import subprocess
import tempfile

p = Path(__file__).resolve().parent
device = (p / 'j81_tuner_shell.S').read_text()
host = (p / 'j81-tuner-hosttest.S').read_text()
a = device.split('_j81_tunerlate_policy_entry:', 1)[1].split('_j81_tunerlate_identity:', 1)[0]
b = host.split('_j81_tunerlate_policy_entry:', 1)[1].split('_j81_tunerlate_identity:', 1)[0]
a = a.replace('ldr x9, _j81_tunerlate_buffer', 'adrp x9, _test_buffer@PAGE\n add x9, x9, _test_buffer@PAGEOFF')
a = a.replace('mrs x13, tpidr_el1', 'adrp x13, _test_thread@PAGE\n ldr x13, [x13, _test_thread@PAGEOFF]')
a = a.replace(' sub sp, sp, #0x50\n_j81_tunerlate_policy_entry_resume:\n b _j81_tunerlate_policy_entry_resume', '_j81_tunerlate_policy_entry_resume:\n ret')
assert a == b, 'host tuner hooks differ from device hooks'
assert device.count(' sub sp, sp, #0x50\n_j81_tunerlate_policy_entry_resume:') == 1
assert '_j81_tunerlate_fw_original:\n bl _j81_tunerlate_fw_original' in device
assert '_j81_tunerlate_fw_original:\n bl _fake_original' in host
assert 'ldr x30, _j81_tunerlate_fw_return' in device
late = device.split('_j81_tunerlate_fw_log:', 1)[1].split('_j81_tunerlate_end:', 1)[0]
late_host = host.split('_j81_tunerlate_fw_log:', 1)[1].split('_j81_tunerlate_end:', 1)[0]
late = late.replace('_j81_tunerlate_fw_original:\n bl _j81_tunerlate_fw_original', '_j81_tunerlate_fw_original:\n bl _fake_original')
late = late.replace('mrs x8, daif', 'mov x8, #0')
for reg in ('x9', 'x10', 'x12', 'x16', 'x19'):
    late = late.replace(f'ldr {reg}, _j81_tunerlate_buffer', f'adrp {reg}, _test_buffer@PAGE\n add {reg}, {reg}, _test_buffer@PAGEOFF')
late = late.replace('ldr x0, _j81_tunerlate_format', 'adrp x0, _test_format@PAGE\n add x0, x0, _test_format@PAGEOFF')
late = late.replace('ldr x16, _j81_tunerlate_logger', 'adrp x16, _fake_logger@PAGE\n add x16, x16, _fake_logger@PAGEOFF')
late = late.replace(' ldr x30, _j81_tunerlate_fw_return\n_j81_tunerlate_fw_resume:\n b _j81_tunerlate_fw_resume', '_j81_tunerlate_fw_resume:\n b _test_fw_return')
assert late == late_host, 'host late-snapshot body differs from device source'
assert 'mov w15, #16' in a and 'stlxr w12, w11, [x10]' in a
with tempfile.TemporaryDirectory() as temp:
    binary = Path(temp) / 'tuner-test'
    subprocess.run(['clang', '-arch', 'arm64', '-o', str(binary), str(p / 'j81-tuner-hosttest.S'), str(p / 'j81-tuner-hosttest.c')], check=True)
    subprocess.run([str(binary)], check=True)
print('PASS: host hook body matches device source; bounded exclusive retry')
