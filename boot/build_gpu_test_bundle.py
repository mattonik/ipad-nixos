#!/usr/bin/env python3
"""Assemble the already-built J81 GPU probes into one RAM-staging bundle."""

import hashlib
import json
import shutil
import sys
from pathlib import Path


BINARIES = {
    "gpu-id-once": ("artifacts/live/gcroot-gpu-id-once/bin/gpu-id-once", "read-only; GPC state gate"),
    "gpu-core-revision-once": ("artifacts/live/gcroot-gpu-core-revision-once/bin/gpu-core-revision-once", "one read-only core-window revision read; cycle payload required"),
    "gpu-pmgr-peek": ("artifacts/live/gcroot-gpu-pmgr-peek/bin/gpu-pmgr-peek", "read-only; PMGR baseline"),
    "gpu-gpc-peek": ("artifacts/live/gcroot-gpu-gpc-peek/bin/gpu-gpc-peek", "read-only; GPC state/control"),
    "gpu-bridge-peek": ("artifacts/live/gcroot-gpu-bridge-peek/bin/gpu-bridge-peek", "read-only; bridge gate"),
    "gpu-bridge-map": ("artifacts/live/gcroot-gpu-bridge-map/bin/gpu-bridge-map", "MMIO writes; guarded"),
    "gpu-bridge-once": ("artifacts/live/gcroot-gpu-bridge-once/bin/gpu-bridge-once", "MMIO writes; guarded"),
    "gpu-bridge-sim": ("artifacts/live/gcroot-gpu-bridge-sim/bin/gpu-bridge-sim", "offline simulation only"),
    "gpu-bridge-sim-live": ("artifacts/live/gcroot-gpu-bridge-sim-live/bin/gpu-bridge-sim-live", "MMIO writes; guarded"),
    "gpu-gpc-init": ("artifacts/live/gcroot-gpu-gpc-init/bin/gpu-gpc-init", "MMIO writes; guarded"),
    "gpu-bridge-postgpc": ("artifacts/live/gpu-bridge-postgpc/gpu-bridge-postgpc", "read-only; GPC state-1 bridge observation"),
    "gpu-fender-wake": ("artifacts/live/gpu-fender-wake/bin/gpu-fender-wake", "MMIO writes; guarded"),
    "gpu-watchdog-supervisor": ("artifacts/live/gcroot-gpu-watchdog-supervisor-core-revision/bin/gpu-watchdog-supervisor", "watchdog supervisor; cycle-sequence and one-shot core revision mode"),
}
MODULES = {
    "gpu-pmgr-once.ko": ("artifacts/live/private/gpu-test-staging/gpu-pmgr-once.ko", "gpu-pmgr-once payload only"),
    "gpu-pmgr-cycle.ko": ("artifacts/live/gpu-pmgr-cycle/gpu-pmgr-cycle.ko", "gpu-pmgr-cycle payload only"),
    "gpu-fender-status.ko": ("artifacts/live/gpu-fender-status/gpu-fender-status.ko", "gpu-pmgr-cycle payload only"),
}
DATA = {
    "gfx-bridge-plan.bin": ("artifacts/live/private/gpu-offline/gfx-bridge-plan.bin", "pinned two-selector table input; SHA-256 checked by the wrapper"),
}
WRAPPERS = (
    "gpu-id-once-run.sh", "gpu-pmgr-once-run.sh", "gpu-gpc-peek-run.sh",
    "gpu-bridge-peek-run.sh", "gpu-bridge-once-run.sh", "gpu-bridge-first-run.sh",
    "gpu-bridge-segment-run.sh", "gpu-bridge-postgpc-cycle-run.sh",
    "gpu-bridge-once-cycle-run.sh", "gpu-core-revision-once-cycle-run.sh",
    "gpu-gpc-init-run.sh", "gpu-gpc-init-cycle-run.sh", "gpu-fender-wake-run.sh",
    "gpu-fender-status-run.sh", "gpu-pmgr-cycle-run.sh",
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def copy_one(root: Path, source: str, destination: Path) -> dict:
    path = root / source
    if not path.is_file():
        raise SystemExit(f"missing build artifact: {path}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)
    destination.chmod(0o755 if destination.suffix != ".ko" else 0o644)
    return {"sha256": digest(destination), "bytes": destination.stat().st_size}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    output = Path(sys.argv[1]).expanduser() if len(sys.argv) == 2 else root / "artifacts/live/gpu-test-bundle"
    if not output.is_absolute():
        output = root / output
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}; remove it deliberately first")
    manifest = {"format": 1, "purpose": "RAM-only J81 GPU test staging", "binaries": {}, "modules": {}, "wrappers": {}, "data": {}}
    for name, (source, access) in BINARIES.items():
        target = output / "bin" / name
        record = copy_one(root, source, target)
        record["access"] = access
        manifest["binaries"][name] = record
    for name, (source, requirement) in MODULES.items():
        target = output / "modules" / name
        record = copy_one(root, source, target)
        record["requires"] = requirement
        manifest["modules"][name] = record
    for name in WRAPPERS:
        target = output / "wrappers" / name
        record = copy_one(root, f"boot/{name}", target)
        manifest["wrappers"][name] = record
    for name, (source, purpose) in DATA.items():
        target = output / "data" / name
        record = copy_one(root, source, target)
        target.chmod(0o644)
        record["purpose"] = purpose
        manifest["data"][name] = record
    (output / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"built {output}")
    print(f"tests={len(BINARIES)} modules={len(MODULES)} wrappers={len(WRAPPERS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
