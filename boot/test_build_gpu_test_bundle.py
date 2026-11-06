"""Static contract for the GPU staging bundle: hashes and access classes are mandatory."""

import json
from pathlib import Path


source = Path(__file__).with_name("build_gpu_test_bundle.py").read_text()
assert "refusing to overwrite" in source
manifests = sorted(Path("artifacts/live").glob("gpu-test-bundle-*/MANIFEST.json"))
assert manifests, "build the bundle before running this contract"
manifest = manifests[-1]
data = json.loads(manifest.read_text())
assert len(data["binaries"]) >= 10
assert len(data["modules"]) == 3
assert any("read-only" in item["access"] for item in data["binaries"].values())
assert any("MMIO writes" in item["access"] for item in data["binaries"].values())
for group in ("binaries", "modules", "wrappers"):
    for record in data[group].values():
        assert len(record["sha256"]) == 64
print("PASS: GPU staging bundle manifest and access labels")
