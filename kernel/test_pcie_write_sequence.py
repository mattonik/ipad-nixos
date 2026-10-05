#!/usr/bin/env python3
"""Write-sequence fingerprint test for pcie-apple-t7000.c (host-only).

Compiles the REAL driver source against a stub kernel API (kernel/pcie_trace/),
runs its probe through the real init path against fake registers (all-zero and
all-ones, so read-modify-write masks and values are visible), and compares the
ordered trace of every MMIO READ and write, PMU write, GPIO action and delay with the
golden trace recorded from the hardware-proven 0053 driver. dev_info() evaluates its
arguments (reads happen) while dev_dbg() does not, exactly like the kernel. A clean-up that renames or
restructures code must leave this trace byte-identical; anything that changes an
offset, mask, value, order or delay fails here.

Usage:
  python3 kernel/test_pcie_write_sequence.py --source PATH/pcie-apple-t7000.c
  python3 kernel/test_pcie_write_sequence.py --source PATH --update-golden   (deliberate re-baseline)
"""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).parent
HARNESS = HERE / "pcie_trace"
GOLDEN = HARNESS / "golden-0053.trace"
HEADERS = ("linux/bitops.h", "linux/build_bug.h", "linux/log2.h", "linux/delay.h", "linux/err.h", "linux/gpio/consumer.h", "linux/i2c.h",
           "linux/io.h", "linux/jiffies.h", "linux/module.h", "linux/of.h", "linux/of_address.h",
           "linux/pci-ecam.h", "linux/platform_device.h", "linux/regmap.h",
           "linux/bitmap.h", "linux/irqchip/irq-msi-lib.h", "linux/irqdomain.h", "linux/msi.h",
           "linux/mutex.h", "linux/of_irq.h")


def run_trace(source: Path, *args: str, defines: tuple = ()) -> str:
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    assert cc, "no C compiler"
    with tempfile.TemporaryDirectory(prefix="pcie-trace-") as tmp:
        tmp = Path(tmp)
        for header in HEADERS:
            (tmp / "inc" / header).parent.mkdir(parents=True, exist_ok=True)
            (tmp / "inc" / header).write_text("")
        (tmp / "src").mkdir()
        shutil.copy(source, tmp / "src" / "pcie-apple-t7000.c")
        (tmp / "src" / "pci-host-common.h").write_text("")  # shadow the real kernel header
        binary = tmp / "trace"
        build = subprocess.run(
            [cc, "-std=gnu11", "-Wall", "-Wextra", "-Wno-unused-function", "-Wno-unused-parameter",
             "-Wno-unused-variable", *[f"-D{d}" for d in defines], f"-I{tmp / 'inc'}", f"-I{HARNESS}",
             f'-DDRIVER_SOURCE="{tmp / "src" / "pcie-apple-t7000.c"}"', str(HARNESS / "main.c"),
             "-o", str(binary)], capture_output=True, text=True)
        assert build.returncode == 0, build.stdout + build.stderr
        result = subprocess.run([str(binary), *args], capture_output=True, text=True)
        assert result.returncode == 0, f"probe failed in the harness:\n{result.stdout}\n{result.stderr}"
        return result.stdout


def normalize(trace: str) -> str:
    """Sort each run of consecutive reads. C leaves the evaluation order of several
    readl() call arguments unspecified, so the order inside a run may differ between
    compilers; added, removed or moved reads (across a write or delay) still differ."""
    out, run = [], []
    for line in trace.splitlines():
        if line.startswith("R"):
            run.append(line)
            continue
        out.extend(sorted(run))
        run = []
        out.append(line)
    out.extend(sorted(run))
    return "\n".join(out) + "\n"


def check_invariants(trace: str) -> None:
    """Properties that must hold for every version, independent of the golden file."""
    scenarios = re.split(r"^== scenario ", trace, flags=re.M)[1:]
    assert len(scenarios) == 4, "expected board/generic scenarios, each with zero and all-ones registers"
    for body in scenarios:
        name = body.splitlines()[0]
        assert "?" not in body.replace("== probe returned", ""), f"{name}: write outside a mapped window"
        # The controller's +0x88/+0x8c words are undecoded and must never be written.
        assert not re.search(r"W\d+ +win3\+0x0008[8c] ", body), f"{name}: write to +0x88/+0x8c"
        # ... and its value must never decide anything: a read is allowed, a branch on it is not.
        # Only port 1's windows and the ECAM view are ever touched; no Bluetooth PMU register.
        assert not re.search(r"PMU_W 0x0402", body), f"{name}: Bluetooth GPIO2 written"
        assert body.rstrip().endswith("== probe returned 0"), f"{name}: probe did not succeed"
    for board, generic in ((scenarios[0], scenarios[1]), (scenarios[2], scenarios[3])):
        # REG_ON is the first action and only on the board scenario, followed by its 100 ms wait.
        assert board.splitlines()[1:3] == ["PMU_W 0x0403 0x0b", "MSLEEP 100"]
        assert "PMU_W" not in generic
        # Everything after REG_ON is identical between the two scenarios.
        assert board.splitlines()[3:] == generic.splitlines()[1:], "board path must not alter the PCIe sequence"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--golden", type=Path, default=GOLDEN)
    parser.add_argument("--update-golden", action="store_true")
    args = parser.parse_args()
    trace = run_trace(args.source)
    check_invariants(trace)
    if args.update_golden:
        args.golden.write_text(trace)
        print(f"golden updated: {args.golden} ({len(trace.splitlines())} lines)")
        return 0
    expected = normalize(args.golden.read_text())
    trace = normalize(trace)
    if trace != expected:
        import difflib
        sys.stdout.writelines(difflib.unified_diff(expected.splitlines(True), trace.splitlines(True),
                                                   "golden-0053", "candidate", n=2))
        print("FAIL: write sequence differs from the hardware-proven 0053 driver")
        return 1
    print(f"PASS: write sequence identical to golden ({len(trace.splitlines())} trace lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
