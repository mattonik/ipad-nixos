#!/usr/bin/env python3
"""Derive the j81-perftab probe from j81-perfctl. usage: gen_perftab.py <perfctl-dir> <out-dir>"""
import sys
from pathlib import Path
src, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
pair = ' mov w2, #0xc200\n movk w2, #0x1, lsl #16\n'
# file order of the read sites: early Q, control C, power T, middle M, late Q
offsets = [0x23000, 0x1c010, 0x20120, 0x1c014, 0x1c300]
def asm(s):
    s = s.replace('j81_perfctl', 'j81_perftab')
    parts = s.split(pair)
    assert len(parts) == 6
    r = parts[0]
    for off, rest in zip(offsets, parts[1:]):
        r += ' mov w2, #0x%x\n movk w2, #0x%x, lsl #16\n' % (off & 0xffff, off >> 16) + rest
    return r
(out / 'j81_perftab_shell.S').write_text(asm((src / 'j81_perfctl_shell.S').read_text()))
(out / 'j81_perftab_capture.c').write_text((src / 'j81_perfctl_capture.c').read_text()
    .replace('j81_perfctl', 'j81_perftab').replace('J81_PERFCTL', 'J81_PERFTAB'))
for n in ('hosttest', 'irqtest'):
    (out / f'j81-perftab-{n}.S').write_text(asm((src / f'j81-perfctl-{n}.S').read_text()))
    c = (src / f'j81-perfctl-{n}.c').read_text()
    assert c.count('off!=0x1c200') == 1, n
    if n == 'hosttest':
        # call order in the simulation: early, power, control, middle, late
        c = c.replace('off!=0x1c200', 'reads>=5||off!=(unsigned[]){0x23000,0x20120,0x1c010,0x1c014,0x1c300}[reads]')
    else:
        c = c.replace('off!=0x1c200', '(off!=0x23000&&off!=0x20120&&off!=0x1c010&&off!=0x1c014&&off!=0x1c300)')
    (out / f'j81-perftab-{n}.c').write_text(c)
