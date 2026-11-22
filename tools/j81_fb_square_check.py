#!/usr/bin/env python3
"""Draw N white squares on the iPad framebuffer from userspace (devmem), same geometry as fb_breadcrumb.h.

Validates that the breadcrumb squares are visible on the panel. No GPU access; only writes the framebuffer RAM.
Usage: PYTHONPATH=<runner/boot dir> python3 j81_fb_square_check.py [N]   (default 4)
"""
import re, sys
from ipad_console import IPadShell

N = int(sys.argv[1]) if len(sys.argv) > 1 else 4
SQ, GAP = 32, 8
sh = IPadShell()
def run(c, t=20):
    return sh.run(c, t)
def be(path, n):
    out = run(f"od -An -v -tx1 {path}")
    b = bytes.fromhex("".join(re.findall(r"\b[0-9a-f]{2}\b", out)))
    return int.from_bytes(b[:n], "big")
node = run("ls -d /proc/device-tree/chosen/framebuffer* /proc/device-tree/framebuffer* 2>/dev/null | head -1").split()[0]
reg = run(f"od -An -v -tx1 {node}/reg")
raw = bytes.fromhex("".join(re.findall(r"\b[0-9a-f]{2}\b", reg)))
addr = int.from_bytes(raw[:8], "big"); size = int.from_bytes(raw[8:16], "big")
w, h, s = (be(f"{node}/{k}", 4) for k in ("width", "height", "stride"))
print(f"node={node} addr=0x{addr:x} size=0x{size:x} width={w} height={h} stride={s}")
print(run("pkill tablet-dashboard; killall tablet-dashboard 2>/dev/null; echo dashboard-stopped"))
y0 = h - SQ - GAP
cmd = (f"A={addr}; for n in $(seq 1 {N}); do x0=$((8+(n-1)*{SQ+GAP})); "
       f"for y in $(seq 0 {SQ-1}); do for x in $(seq 0 {SQ-1}); do "
       f"devmem $((A+({y0}+y)*{s}+(x0+x)*4)) 32 0xffffffff; done; done; done; echo squares-done")
print(run(cmd, 120))
sh.close()
