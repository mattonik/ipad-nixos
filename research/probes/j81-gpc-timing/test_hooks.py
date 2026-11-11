#!/usr/bin/env python3
import pathlib
import subprocess
import tempfile

p = pathlib.Path(__file__).parent
s = (p / 'j81_timing_shell.S').read_text()
s = s[s.index('_j81_timing_gpc_start:'):s.index('_j81_timing_identity:')]
s = s[:s.index('.p2align 3\n_j81_timing_timer:')]
s = s.replace('ldr x9, _j81_timing_buffer', 'adrp x9, _test_buffer@PAGE\n add x9, x9, _test_buffer@PAGEOFF')
s = s.replace('mrs x11, tpidr_el1', 'adrp x11, _test_thread@PAGE\n ldr x11, [x11, _test_thread@PAGEOFF]')
s = s.replace('ldr x12, _j81_timing_timer\n blr x12', 'bl _fake_timer')
s = s.replace('b _j81_timing_start_resume', 'ret').replace('b _j81_timing_finish_resume', 'ret')
s = '''.text
.globl _test_start, _test_finish, _test_flags_start, _test_flags_finish
_test_start:
 stp x29, x30, [sp, #-16]!
 mov w8, #0x11
 bl _j81_timing_gpc_start
 ldp x29, x30, [sp], #16
 ret
_test_finish:
 stp x29, x30, [sp, #-16]!
 bl _j81_timing_gpc_finish
 ldp x29, x30, [sp], #16
 ret
_test_flags_start:
 stp x29, x30, [sp, #-16]!
 mov x9, #0xa0000000
 msr nzcv, x9
 mov w8, #0x11
 bl _j81_timing_gpc_start
 mrs x0, nzcv
 ldp x29, x30, [sp], #16
 ret
_test_flags_finish:
 stp x29, x30, [sp, #-16]!
 mov x9, #0xa0000000
 msr nzcv, x9
 bl _j81_timing_gpc_finish
 mrs x0, nzcv
 ldp x29, x30, [sp], #16
 ret
''' + s
with tempfile.TemporaryDirectory() as tmp:
    assembly = pathlib.Path(tmp) / 'hooks.S'
    assembly.write_text(s)
    exe = pathlib.Path(tmp) / 'test'
    subprocess.run(['clang', '-arch', 'arm64', str(assembly), str(p / 'test_hooks.c'), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
