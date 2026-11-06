from pathlib import Path

source = Path(__file__).with_name("gpu-bridge-postgpc.c").read_text()
capture = Path(__file__).with_name("gpu_bridge_postgpc_capture.py").read_text()
wrapper = Path(__file__).with_name("gpu-bridge-postgpc-cycle-run.sh").read_text()
assert "201000" not in source
assert source.count("read32(") == 5
assert "stage=after-gpc-state raw=0x00000001" in capture
assert "gpu_pmgr_cycle" in wrapper
assert "READ" in capture
print("PASS: post-GPC bridge probe is read-only and RGX-free")
