#!/usr/bin/env python3
"""Run the 12B410 J81 iBoot voltage reporter on host RAM and decode the archived Linux table."""
import argparse
import ctypes
from pathlib import Path
import platform
import re
import subprocess
import tempfile

from audit_j81_pmgr_start import checked_file
from test_j81_bank_enable import assembly_words


def test(loader_path, log):
    loader = checked_file(loader_path, "45960ccabbdd317ac9e522e608f5ed9b2c86952a1e85e1efc51ccf3ae3dc6e41")
    rows = [(int(s), int(w, 16)) for s, w in re.findall(r"^perf(\d+) raw=(0x[0-9a-f]+)", log.read_text(), re.M)]
    if [s for s, _ in rows] != list(range(16)):
        raise ValueError("expected exactly one ordered 16-state snapshot")
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise SystemExit("native loader test requires arm64 macOS with clang")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)
        asm = [".text", ".p2align 2", ".globl _report_mv", "_report_mv:",
               *assembly_words(loader, 0xb24c, 0xb284)]
        (path / "report.s").write_text("\n".join(asm) + "\n")
        subprocess.run(["clang", "-dynamiclib", "report.s", "-o", "report.dylib"], cwd=path, check=True)
        report = ctypes.CDLL(str(path / "report.dylib")).report_mv
        report.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        report.restype = ctypes.c_uint32
        for rail in range(4):
            for code in range(256):
                expected = 600 + 3125 * code // 1000 if rail < 3 else 0xffffffff
                if report(rail, code) != expected:
                    raise ValueError(f"conversion mismatch at rail {rail}, code {code}")
        print("state\tword\tcode\tnominal_Hz\tiBoot_reported_mV")
        for state, w in rows:
            if w & (1 << 21):
                hz = 24000000 * ((w >> 12) & 511) // ((w >> 4) & 31) // ((w & 15) + 1)
                print(f"{state}\t0x{w:08x}\t0x{w>>24:02x}\t{hz}\t{report(2,w>>24)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("loader", type=Path)
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    test(args.loader, args.snapshot)
