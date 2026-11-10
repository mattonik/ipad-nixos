"""Static contract for the GPU staging bundle: hashes and access classes are mandatory."""

import json
import sys
from pathlib import Path


source = Path(__file__).with_name("build_gpu_test_bundle.py").read_text()
assert "refusing to overwrite" in source
if len(sys.argv) > 1:
    manifest = Path(sys.argv[1]) / "MANIFEST.json"
else:
    manifests = sorted(Path("artifacts/live").glob("gpu-test-bundle-*/MANIFEST.json"))
    assert manifests, "build the bundle before running this contract"
    manifest = manifests[-1]
data = json.loads(manifest.read_text())
assert len(data["binaries"]) >= 10
assert len(data["modules"]) == 4
assert "j81-mcc-read-once.ko" in data["modules"]
assert "j81-mcc-read-once-run.sh" in data["wrappers"]
assert "one-shot MCC read modes" in data["binaries"]["gpu-watchdog-supervisor"]["access"]
assert any("read-only" in item["access"] for item in data["binaries"].values())
assert any("MMIO writes" in item["access"] for item in data["binaries"].values())
for group in ("binaries", "modules", "wrappers", "data"):
    for record in data[group].values():
        assert len(record["sha256"]) == 64
assert data["data"]["gfx-bridge-plan.bin"]["sha256"] == "1c7b3839da2e7aa914a393e914a7a427c12190293ba5d2b50fe06cf4d8df6435"
print("PASS: GPU staging bundle manifest and access labels")
