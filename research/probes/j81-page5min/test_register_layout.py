"""Check the intermediate hook's stack layout and paired register saves."""
import re
from pathlib import Path

s = Path(__file__).with_name('j81_page5min_shell.S').read_text()
hook = s.split('_j81_page5min_gpc_poll:', 1)[1].split('_j81_page5min_identity:', 1)[0]
assert hook.lstrip().startswith('tbnz w8, #4, Lmiddle_again\n sub sp, sp, #0x140')
for kind, limit in [('x', 28)]:
    for i in range(0, limit + 1, 2):
        pattern = rf'{kind}{i}, {kind}{i+1}, \[sp, #(0x[0-9a-f]+)\]'
        saves = re.findall(r'\bstp ' + pattern, hook)
        restores = re.findall(r'\bldp ' + pattern, hook)
        assert len(saves) == len(restores) == 1 and saves == restores, (kind, i)
assert 'str x30, [sp, #0x130]' in hook and 'ldr x30, [sp, #0x130]' in hook
assert 'mrs x8, nzcv\n str x8, [sp, #0x138]' in hook
assert 'ldr x8, [sp, #0x138]\n msr nzcv, x8' in hook
assert all(x not in hook for x in (' stp q', ' ldp q', ' fpcr', ' fpsr'))
assert 'ldr x9, _j81_page5min_reader\n cmp x8, x9\n b.ne Lmiddle_restore' in hook
assert hook.count('sub sp, sp, #0x140') == hook.count('add sp, sp, #0x140') == 1
assert 'mov w2, #0x5004\n mov x3, #0\n blr x8' in hook
print('PASS: intermediate hook register-save layout')
