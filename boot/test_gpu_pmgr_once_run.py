#!/usr/bin/env python3
"""Exercise the actual wrapper with fake paths and an inert insmod."""
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import tempfile

source = Path(__file__).with_name("gpu-pmgr-once-run.sh").read_text()
with tempfile.TemporaryDirectory(prefix="gpu-run-") as tmp:
    root = Path(tmp)
    module = root / "module"
    notes = root / "notes"
    called = root / "called"
    insmod = root / "insmod"
    peek = root / "peek"
    power = root / "power"
    loaded = root / "loaded"
    wrapper = root / "run.sh"
    module.write_bytes(b"fake module")
    notes.write_bytes(b"fake notes")
    module_hash = sha256(module.read_bytes()).hexdigest()
    notes_hash = sha256(notes.read_bytes()).hexdigest()
    power.write_text("")
    insmod.write_text(f'#!/bin/sh\nprintf called > "{called}"\nexit "${{MOCK_RC:-0}}"\n')
    insmod.chmod(0o700)
    peek.write_text('#!/bin/sh\nprintf "stage=before-pmgr-read\\n"\nIFS= read -r reply\n[ "$reply" = READ ] || exit 1\nprintf "stage=after-pmgr-read\\n"\n')
    peek.chmod(0o700)
    wrapper.write_text(source.replace("/tmp/gpu-pmgr-once.ko", str(module))
                       .replace("/sys/kernel/notes", str(notes))
                       .replace("/sys/module/gpu_pmgr_once", str(loaded))
                       .replace("/sys/devices/gpu-pmgr-once/power_once", str(power))
                       .replace("/tmp/gpu-pmgr-peek", str(peek))
                       .replace("78349e4aa934a5ea1f22a2c9ea1859a39597476810764cdd92b3d8b35d3959dd", sha256(peek.read_bytes()).hexdigest())
                       .replace("39d32b553830d57b1ae0657c265b931bed248de95d14935c6be818b6372b8f89", module_hash)
                       .replace("b471f3c159c4d326ec466f78967dd5a57ecf1e6d3af9665b93f1ff4ba5f617fb", sha256(b"fake build id").hexdigest())
                       .replace("/sbin/insmod", str(insmod)))
    def run(args, reply="", env=None):
        return subprocess.run(["sh", str(wrapper), *args], input=reply, capture_output=True, text=True, env=env)
    assert run(["x", notes_hash], "POWER\n").returncode == 2
    assert run(["0" * 64, notes_hash], "POWER\n").returncode != 0
    assert run([module_hash, "0" * 64], "POWER\n").returncode != 0
    assert run([module_hash, notes_hash], "READ\nNO\n").returncode != 0
    assert called.exists() and not power.read_text()
    called.unlink()
    result = run([module_hash, notes_hash], "READ\nPOWER\n")
    assert result.returncode == 0 and called.read_text() == "called" and power.read_text() == "1\n"
    assert "stage=before-gfx-power " in result.stdout and "stage=after-gfx-power rc=0" in result.stdout
    called.unlink()
    result = run([module_hash, notes_hash], "POWER\n", dict(os.environ, MOCK_RC="7"))
    assert result.returncode != 0 and called.exists()
    assert "stage=before-gfx-power" not in result.stdout
    power.unlink()
    power.mkdir()
    result = run([module_hash, notes_hash], "READ\nPOWER\n")
    assert result.returncode != 0 and "stage=after-gfx-power rc=" in result.stdout
    power.rmdir()
    power.write_text("")
    called.unlink()
    (loaded / "notes").mkdir(parents=True)
    build_id = loaded / "notes/.note.gnu.build-id"
    build_id.write_bytes(b"wrong build id")
    assert run([module_hash, notes_hash], "READ\nPOWER\n").returncode != 0
    assert not called.exists() and not power.read_text()
    build_id.write_bytes(b"fake build id")
    result = run([module_hash, notes_hash], "READ\nPOWER\n")
    assert result.returncode == 0 and not called.exists() and power.read_text() == "1\n"
print("PASS: wrapper checks hashes, acknowledgement, load and power-request failures")
