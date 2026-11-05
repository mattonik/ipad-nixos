#!/usr/bin/env python3
"""Exercise wrapper preconditions against a private fake device tree."""
import hashlib
import subprocess
import tempfile
from pathlib import Path

for kind in ("peek", "init", "id", "bridge", "simbridge", "bridgepeek"):
    probe_name = {"id": "gpu-id-once", "bridge": "gpu-bridge-once", "simbridge": "gpu-bridge-sim-live", "bridgepeek": "gpu-bridge-peek"}.get(kind, f"gpu-gpc-{kind}")
    source = Path(__file__).with_name(f"{probe_name}-run.sh").read_text()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        files = {
            f"/tmp/{probe_name}": b"#!/bin/sh\nprintf 'observer-started\\n'\n",
            "/tmp/gpu-pmgr-peek": b"#!/bin/sh\nprintf 'pmgr-observed\\n'\n",
            "/sys/kernel/notes": b"kernel notes",
            "/sys/module/gpu_pmgr_once/notes/.note.gnu.build-id": b"module note",
            "/sys/devices/gpu-pmgr-once/power/runtime_status": b"active\n",
            "/sys/devices/gpu-pmgr-once/power/runtime_usage": b"1\n",
            "/proc/mounts": b"rootfs / rootfs rw 0 0\n",
        }
        if kind in ("bridge", "simbridge"):
            files["/tmp/gfx-bridge-plan.bin"] = b"synthetic plan"
        for name, data in files.items():
            path = root / name.lstrip("/")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            if name.startswith("/tmp/"):
                path.chmod(0o700)
            source = source.replace(name, str(path))
        for old, name in (
            ("78349e4aa934a5ea1f22a2c9ea1859a39597476810764cdd92b3d8b35d3959dd", "/tmp/gpu-pmgr-peek"),
            ("82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014", "/sys/kernel/notes"),
            ("b471f3c159c4d326ec466f78967dd5a57ecf1e6d3af9665b93f1ff4ba5f617fb", "/sys/module/gpu_pmgr_once/notes/.note.gnu.build-id"),
        ):
            source = source.replace(old, hashlib.sha256(files[name]).hexdigest())
        if kind in ("bridge", "simbridge"):
            source = source.replace("1c7b3839da2e7aa914a393e914a7a427c12190293ba5d2b50fe06cf4d8df6435", hashlib.sha256(files["/tmp/gfx-bridge-plan.bin"]).hexdigest())
        if kind == "simbridge":
            source = source.replace("8ea9fbf71ecf19cf5f42c1b2548d35187ae8a89f82fb69d9626404402471359a", hashlib.sha256(files[f"/tmp/{probe_name}"]).hexdigest())
        script = root / "run.sh"
        script.write_text(source)
        digest = hashlib.sha256(files[f"/tmp/{probe_name}"]).hexdigest()
        def run(value):
            return subprocess.run(["sh", str(script), value], capture_output=True, text=True)
        assert run("bad").returncode == 2
        assert run("0" * 64).returncode != 0
        if kind == "simbridge":
            rejected = run("3b2f655d18d94a4349bd19dbc63025fa9343e8ac43efbebc5b1f7fe97332a02c")
            assert rejected.returncode != 0 and "pmgr-observed" not in rejected.stdout
        usage = root / "sys/devices/gpu-pmgr-once/power/runtime_usage"
        usage.write_text("0\n")
        failed = run(digest)
        assert failed.returncode != 0 and "pmgr-observed" not in failed.stdout
        usage.write_text("1\n")
        mounts = root / "proc/mounts"
        mounts.write_text("rootfs / rootfs rw 0 0\n/dev/mmcblk0p1 /mnt ext4 rw 0 0\n")
        assert run(digest).returncode != 0
        mounts.write_text("rootfs / rootfs rw 0 0\n")
        if kind in ("bridge", "simbridge"):
            plan = root / "tmp/gfx-bridge-plan.bin"
            plan.write_bytes(b"corrupt")
            assert run(digest).returncode != 0
            plan.write_bytes(files["/tmp/gfx-bridge-plan.bin"])
        good = run(digest)
        assert good.returncode == 0 and good.stdout == "pmgr-observed\nobserver-started\n"

print("PASS: GPC wrappers check identity, RAM root, and runtime ownership")
