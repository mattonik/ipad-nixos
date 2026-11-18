#!/usr/bin/env python3
"""Run the minimal PMGR-cycle then GPC/Fender status capture on one RAM boot."""
import argparse
import hashlib
import socket
import sys
from pathlib import Path

import gpu_campaign as campaign
import gpu_gpc_fender_status_capture as fender
import gpu_pmgr_cycle_capture as pmgr
from stage_gpu_test_bundle import stage


ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "artifacts/live/private/j81-gpc-fender-status-ready"
FILES = {
    "gpu-pmgr-cycle.ko": "c27f7a9044c99104b13b3089e52ca3311de0fc257e47d307ec3b451c5cb20f23",
    "gpu-pmgr-peek": "78349e4aa934a5ea1f22a2c9ea1859a39597476810764cdd92b3d8b35d3959dd",
    "gpu-pmgr-cycle-run": "e21f678dd41064d865b9946a0a6c9002166ea573ed48500e9748fe0e0e848d62",
    "gpu-gpc-fender-status": "690a2d5774ed302c76a0104767990faee1e72a1d5f5041ab349c8c3140186eff",
    "gpu-gpc-fender-status-run": "648d81347352f02d434a803384884fbc5ca10058e717f3b07eca47a85a425123",
    "gpu-watchdog-supervisor": "076bee589ff168b952bb48ad2c233b608372f6e70a0806ffbadec60d2a2d2fa9",
    "j81-page5-read-once.ko": "ca16576e6d574ff3587d631cd3fb82e3ae0ce83f49cdd5c4d3156f9306099e4c",
}


def verify():
    for name, expected in FILES.items():
        if hashlib.sha256((BUNDLE / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"bundle checksum mismatch: {name}")


def run(logdir):
    verify()
    logdir.mkdir(parents=True, exist_ok=False)
    preflight = campaign.preflight()
    (logdir / "preflight.log").write_text(preflight)
    boot_id = campaign.parse_preflight(preflight)
    for name in FILES:
        stage("172.16.42.1", "/tmp/" + name, (BUNDLE / name).read_bytes())
    with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock:
        pmgr.capture(sock, logdir / "pmgr.log", FILES["gpu-pmgr-cycle.ko"], campaign.NOTES, 40)
    with socket.create_connection(("172.16.42.1", 23), timeout=5) as sock:
        result = fender.capture(sock, logdir / "fender.log", FILES["gpu-gpc-fender-status"],
                                FILES["gpu-watchdog-supervisor"], FILES["gpu-gpc-fender-status-run"], boot_id, 40)
    print(f"captured {result}; logs={logdir}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logdir", type=Path)
    args = parser.parse_args()
    try:
        run(args.logdir.resolve())
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"campaign stopped: {error}; do not retry this boot\n")


if __name__ == "__main__":
    main()
