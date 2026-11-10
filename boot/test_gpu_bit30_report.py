import subprocess
from pathlib import Path

root = Path(__file__).parent
with __import__("tempfile").TemporaryDirectory() as d:
    p = Path(d)
    (p / "fender.log").write_text(
        "stage=state value=0x00000001\n"
        "stage=control value=0x40000000\n"
        "stage=hold value=0x00000000\n"
    )
    (p / "perf.log").write_text("ctl raw=0x80000000\n")
    result = subprocess.run(
        ["python3", str(root / "gpu_bit30_report.py"), str(p / "fender.log"), str(p / "perf.log")],
        check=True, capture_output=True, text=True,
    )
    assert "gpc_control=0x40000000 bit30=1" in result.stdout
    assert "pmgr_perf_control=0x80000000 bit31=1" in result.stdout
    assert "writes=none" in result.stdout
print("PASS: bit-30/bit-31 snapshot report")
