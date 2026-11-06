import runpy
import sys

module = runpy.run_path("boot/gpu_bridge_segment_capture.py", run_name="gpu_bridge_segment_capture_test")
args = module["_args"]
assert args(["capture", "log", "a" * 64, "b" * 64, "c" * 64])[0].name == "log"
try:
    args(["capture", "log", "a" * 63, "b" * 64, "c" * 64])
except SystemExit:
    pass
else:
    raise AssertionError("short hash accepted")
print("PASS: bridge capture validates SHA-256 arguments")
