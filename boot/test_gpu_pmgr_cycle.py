from pathlib import Path

source = Path(__file__).parents[1].joinpath("kernel/gpu-pmgr-cycle/gpu-pmgr-cycle.c").read_text()
assert "pm_runtime_get_sync(dev)" in source
assert "pm_runtime_put_sync(dev)" in source
assert source.count("pm_runtime_get_sync(dev)") == 2
assert "pm_runtime_put_sync(dev)" in source
assert "experimental,j81-gpu-test-no-poweroff" in source
assert "atomic_cmpxchg(&attempted, 0, 1)" in source
assert "power-domains" in source
print("PASS: PMGR cycle is one-shot, gated, and leaves a final runtime reference")
