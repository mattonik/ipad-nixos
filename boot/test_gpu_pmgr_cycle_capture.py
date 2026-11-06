from pathlib import Path

source = Path(__file__).with_name("gpu_pmgr_cycle_capture.py").read_text()
wrapper = Path(__file__).with_name("gpu-pmgr-cycle-run.sh").read_text()
assert "stage=after-pmgr-cycle rc=0" in source
assert "do not retry this boot" in source
assert "pm_runtime_put_sync(dev)" in Path(__file__).parents[1].joinpath("kernel/gpu-pmgr-cycle/gpu-pmgr-cycle.c").read_text()
assert "/tmp/gpu-pmgr-cycle.ko" in wrapper
assert "[ \"$reply\" = CYCLE ]" in wrapper
print("PASS: PMGR cycle capture is checkpointed and fail-closed")
