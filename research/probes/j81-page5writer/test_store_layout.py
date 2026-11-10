"""Static contracts for the experimental PMGR store trampoline."""
from pathlib import Path
s = Path(__file__).with_name('j81_page5writer_shell.S').read_text()
w = s.split('_j81_page5writer_store:', 1)[1].split('_j81_page5writer_store_resume:', 1)[0]
host = Path(__file__).with_name('j81-page5writer-hosttest.S').read_text()
host_store = host.split('_j81_page5writer_store:', 1)[1].split('_j81_page5writer_store_resume:', 1)[0]
assert host_store == w.replace(' ldr x9, _j81_page5writer_buffer', ' adrp x9, _test_buffer@PAGE\n add x9, x9, _test_buffer@PAGEOFF')
assert w.count('str w21, [x8, w19, uxtw]') == 1
for regs, off in [('x9, x10', ''), ('x11, x12', ', #0x10'), ('x13, x14', ', #0x20'), ('x15, x16', ', #0x30')]:
    assert f'stp {regs}, [sp{off}]' in w and f'ldp {regs}, [sp{off}]' in w
assert 'mrs x9, nzcv' in w and 'msr nzcv, x9' in w
assert all(x in w for x in ('cmp x23, x10', 'cbnz w22', 'cbnz w20', 'mov w10, #0x5004', 'cmp w19, w10'))
assert 'mov w15, #16' in w and 'subs w15, w15, #1' in w and 'cmp w12, #16' in w
assert 'add x13, x9, #3744' in w and 3744 + 16 * 16 <= 4096
assert 'stlr w11, [x10]' in w and 'W=UNREADY' in s
print('PASS: one displaced store, filter, bounded buffer and register layout')
