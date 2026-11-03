#!/usr/bin/env python3
"""Off-hardware check of touchdemo: run boot/touchdemo-test.replay headless, then check the summary and pixels.

  touchdemo-check.py TOUCHDEMO REPLAY ZERO_REPLAY FONT.psf OUTDIR

Runs the real evdev parser and renderer (the replay feeds struct input_event), so it covers protocol-B slot
handling, the axis mapping, the dirty-rectangle compositor, the GRID statistics and the zero-axis-range fallback.
It cannot check the DRM/fbdev backends or the real touchscreen; those need the iPad.
"""
import os
import subprocess
import sys

W, H = 1536, 2048
PALETTE = [0xff4040, 0x40c0ff, 0x60ff60, 0xffc020, 0xff60ff, 0x40ffe0,
           0xffffff, 0xff8040, 0xa080ff, 0xc0ff40, 0xff4090, 0x80a0ff]


def read_ppm(path):
    with open(path, "rb") as f:
        data = f.read()
    parts = data.split(b"\n", 3)
    assert parts[0] == b"P6", path
    w, h = map(int, parts[1].split())
    assert (w, h) == (W, H), (path, w, h)
    pix = parts[3]
    assert len(pix) == w * h * 3, (path, len(pix))
    return lambda x, y: int.from_bytes(pix[(y * w + x) * 3:(y * w + x) * 3 + 3], "big")


def run(binary, replay, font, outdir, *extra):
    p = subprocess.run([binary, "--headless", f"{W}x{H}", "--replay", replay, "--font", font, *extra],
                       cwd=outdir, capture_output=True, text=True, timeout=120)
    sys.stdout.write(p.stdout)
    sys.stderr.write(p.stderr)
    assert p.returncode == 0, f"touchdemo exited {p.returncode}"
    return p.stdout


def main():
    binary, replay, zero_replay, font, outdir = (os.path.abspath(a) for a in sys.argv[1:6])
    os.makedirs(outdir, exist_ok=True)
    out = run(binary, replay, font, outdir)

    assert "grid cells" in out and "edge 52/52" in out, "the edge sweep must cover all 52 outer cells"
    assert "targets 8/8" in out, "all eight targets must be recorded"
    for name, x, y, dx, dy in (("top-left", 96, 96, 4, -6), ("top", 768, 96, 0, 4), ("right", 1440, 1024, 0, 0)):
        line = f"target {name:<12} at {x:4d},{y:4d} offset dx {dx:+.1f} dy {dy:+.1f} px"
        assert line in out, f"missing: {line}"
    assert "max fingers 2" in out
    assert "(ZERO RANGE)" not in out

    paint = read_ppm(os.path.join(outdir, "paint.ppm"))
    assert paint(750, 600) == PALETTE[7 % 12], hex(paint(750, 600))     # ID 7 stroke
    assert paint(768, 1300) == PALETTE[8 % 12], hex(paint(768, 1300))   # ID 8 stroke
    assert paint(300, 1500) == 0x000000, hex(paint(300, 1500))          # untouched background
    assert paint(10, 2040) != 0x000000, "button bar"
    assert paint(10, 10) != 0x000000, "HUD panel"

    grid = read_ppm(os.path.join(outdir, "grid.ppm"))
    assert grid(704, 64) != 0x000000, "an edge cell lit by the sweep"
    assert grid(400, 400) == 0x000000, "an untouched inner cell stays dark"
    assert grid(96 + 40, 96) == 0x40e060, hex(grid(96 + 40, 96))       # top-left target turned green

    events = read_ppm(os.path.join(outdir, "events.ppm"))
    text = sum(1 for y in range(300, 1800, 3) for x in range(0, W, 3) if events(x, y) != 0)
    assert text > 2000, f"the EVENTS screen should be full of text, {text} lit samples"

    # Zero axis ranges (apple_z2 before geometry): flagged, the first touches press no button, and once two
    # opposite corners were touched the seen-range mapping reaches every outer cell.
    out = run(binary, zero_replay, font, outdir, "--zero-axes")
    assert "(ZERO RANGE)" in out
    assert "edge 52/52" in out, "seen-range mapping must reach the outer cells"
    print("touchdemo-check: all checks passed")


if __name__ == "__main__":
    main()
