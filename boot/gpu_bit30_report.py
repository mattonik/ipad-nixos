#!/usr/bin/env python3
"""Decode read-only J81 GPC/PMGR snapshots for the bit-30 comparison."""

import argparse
from pathlib import Path

def words(path: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    for line in path.read_text().splitlines():
        if line.startswith("stage=state value="):
            out["state"] = int(line.rsplit("0x", 1)[1], 16)
        elif line.startswith("stage=control value="):
            out["control"] = int(line.rsplit("0x", 1)[1], 16)
        elif line.startswith("stage=hold value="):
            out["hold"] = int(line.rsplit("0x", 1)[1], 16)
        elif line.startswith("ctl raw="):
            out["ctl"] = int(line.rsplit("0x", 1)[1], 16)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fender_log", type=Path)
    parser.add_argument("perf_log", type=Path)
    args = parser.parse_args()
    fender, perf = words(args.fender_log), words(args.perf_log)
    if not {"state", "control", "hold"} <= fender.keys():
        parser.error("Fender log lacks state/control/hold")
    if "ctl" not in perf:
        parser.error("PMGR perf log lacks ctl")
    control = fender["control"]
    print(f"gpc_state=0x{fender['state']:08x}")
    print(f"gpc_control=0x{control:08x} bit30={(control >> 30) & 1}")
    print(f"gpc_hold=0x{fender['hold']:08x}")
    print(f"pmgr_perf_control=0x{perf['ctl']:08x} bit31={(perf['ctl'] >> 31) & 1}")
    print("writes=none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
