#!/usr/bin/env python3
"""Patch 0061 (BCM4350 metadata observation probe, TEST KERNELS ONLY): contract, apply, host trace.

Usage: python3 kernel/test_bcm_probe_patch.py [--j81-msi-source DIR] [--update-golden]

DIR is the source tree of the 0057 kernel derivation. Checks: text contract (observation only);
zero-fuzz apply; the real driver compiled against a fake BCM4350 with failure injection, with
invariants on every scenario (only the BAR0 window register is ever written, restored on every
exit, no shadow read, nothing OTP-related read for unknown chip/revision) and a golden trace.
"""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HERE = Path(__file__).parent
PATCH = HERE / "patches" / "0061-pcie-apple-t7000-bcm-probe.patch"
GOLDEN = HERE / "bcm_probe_trace" / "golden.trace"
NEW = "drivers/pci/controller/pcie-apple-t7000-bcm-probe.c"
FILES = ("drivers/pci/controller/Kconfig", "drivers/pci/controller/Makefile")


def added(text):
    return "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))


def check_text():
    text = PATCH.read_text()
    touched = [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")]
    assert touched == [FILES[0], FILES[1], NEW], touched
    plus = added(text)
    assert "config PCIE_APPLE_T7000_BCM_PROBE" in plus and "depends on PCIE_APPLE_T7000=y" in plus
    assert "TEST KERNELS ONLY" in plus and "return -ENODEV;" in plus
    code = re.sub(r"/\*.*?\*/", "", plus, flags=re.S)       # strip comments, including trailing ones
    # Observation only: no register writes of any kind except the BAR0 window config write, no
    # selector/OTP/shadow access, no bus mastering, firmware, DMA, MSI, IRQ or brcmfmac.
    for forbidden in ("iowrite", "writel", "writew", "writeb", "pci_set_master", "request_firmware",
                      "dma_", "pci_alloc_irq", "request_irq", "brcmf", "sromotp", "BCM_CC_SROMOTP",
                      "otpcontrol", "otpprog", "OTPCONTROL", "0x800)", "pci_write_config_word",
                      "pci_write_config_byte", "pci_enable_device(", "pmu", "gpiod_"):
        assert forbidden not in code, forbidden
    assert code.count("pci_write_config_dword") == 2, "only the window select and its restore may write config"
    assert "BCM_CC_EROMPTR" in code and "BCM_ENUM_END" in code
    # Restore must sit on the single exit label.
    assert re.search(r"out:\n[^}]*pci_write_config_dword\(pdev, BCM_BAR0_WINDOW, saved\)", code, re.S)


def run_harness(driver, defines=()):
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    assert cc, "no C compiler"
    with tempfile.TemporaryDirectory(prefix="bcm-probe-") as tmp:
        tmp = Path(tmp)
        for header in ("io.h", "module.h", "pci.h", "crc32.h", "debugfs.h", "slab.h"):
            (tmp / "inc" / "linux" / header).parent.mkdir(parents=True, exist_ok=True)
            (tmp / "inc" / "linux" / header).write_text("")
        shutil.copy(driver, tmp / "drv.c")
        binary = tmp / "t"
        build = subprocess.run([cc, "-std=gnu11", "-Wall", "-Wextra", "-Wno-unused-parameter", *[f"-D{d}" for d in defines],
                                f"-I{tmp / 'inc'}", f"-I{HERE / 'bcm_probe_trace'}",
                                f'-DDRIVER_SOURCE="{tmp / "drv.c"}"', str(HERE / "bcm_probe_trace" / "main.c"),
                                "-o", str(binary)], capture_output=True, text=True)
        assert build.returncode == 0, build.stdout + build.stderr
        run = subprocess.run([str(binary)], capture_output=True, text=True)
        assert run.returncode == 0, "harness reported a violation or an unrestored window:\n" + run.stdout
        return run.stdout


def scenarios(trace):
    parts = re.split(r"^== scenario ", trace, flags=re.M)[1:]
    return {p.splitlines()[0]: p for p in parts}


def reads(block):
    return [(m.group(1), int(m.group(2), 16)) for m in re.finditer(r"^RD win=(0x[0-9a-f]+) off=0x([0-9a-f]+)", block, re.M)]


def check_invariants(trace):
    sc = scenarios(trace)
    assert len(sc) in (14, 23), sorted(sc)
    for name, block in sc.items():
        assert "PROBE_RET -19" in block, name                      # always declines the device
        assert "VIOLATIONS 0" in block, name
        fin = re.search(r"FINAL_WINDOW (0x[0-9a-f]+) INITIAL (0x[0-9a-f]+)", block)
        assert fin.group(1) == fin.group(2), f"{name}: window not restored"
        # Never touches a config offset other than 0x80, never reads the shadow.
        assert not re.search(r"CFG[RW] (?!0x80)", block), name
        for win, off in reads(block):
            assert off < 0x800 or win != "0x18000000", f"{name}: read the sromotp shadow"
        assert block.count("ENABLE_MEM") == block.count("DISABLE") + (1 if "ENABLE_MEM (fails)" in block else 0), name
        assert block.count("REQUEST_REGION") == block.count("RELEASE_REGION") + (1 if "REQUEST_REGION 0 (fails)" in block else 0), name
        # The only config writes are window selects + the final restore (last write == initial value).
        writes = re.findall(r"^CFGW 0x80 <- (0x[0-9a-f]+)", block, re.M)
        if writes:
            assert writes[-1] == fin.group(2), f"{name}: last window write is not the restore"
    off = lambda n: {o for w, o in reads(sc[n]) if w == "0x18000000"}
    # Mapping verdicts.
    assert "mapping path: chipcommon" in sc["ok-rev48-chipcommon"]
    assert "mapping path: gci" in sc["ok-rev49-gci"]
    assert "mapping path: chipcommon" in sc["ok-rev51-chipcommon"]      # rev 51 is the published exception
    assert off("ok-rev48-chipcommon") == {0x0, 0xfc, 0x4, 0x1c, 0x190}
    # Fail closed: unknown revision / chip / wrapper reads no OTP-related register.
    for n in ("stop-rev43", "stop-first-component-not-cc", "stop-no-component", "stop-eromptr-range"):
        assert "mapping path: STOP" in sc[n], n
        assert not off(n) & {0x4, 0x1c, 0x190}, f"{n}: read OTP-related registers"
    assert "mapping path: STOP" in sc["stop-chip-4354"] and off("stop-chip-4354") == {0x0, 0xfc}
    assert "CFGW 0x80 <- 0x180ff000" not in sc["stop-chip-4354"], "unknown chip must not select the EROM window"
    assert "mapping path: STOP - OTP wrapper" in sc["stop-wrap-not-40nm"]
    assert "STOP: access error -19" in sc["stop-chipid-allones"]
    assert "window 0x18000000 not accepted" in sc["stop-window-rejected"]
    assert "RD " not in sc["stop-window-rejected"], "no register may be read when the window did not take"
    assert "restore PASS" in sc["restore-nondefault-window"]
    # Early failures leave the device untouched.
    assert "CFGW" not in sc["fail-enable"] and "RD " not in sc["fail-enable"]
    assert "RD " not in sc["fail-region"]


def check_apply(source, update):
    with tempfile.TemporaryDirectory(prefix="bcm-probe-tree-") as tmp:
        tree = Path(tmp)
        for rel in FILES:
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(source) / rel, tree / rel)
            (tree / rel).chmod((tree / rel).stat().st_mode | 0o200)
        r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(PATCH)], cwd=tree,
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        trace = run_harness(tree / NEW)
        check_invariants(trace)
        if update:
            GOLDEN.write_text(trace)
            print(f"golden updated: {GOLDEN} ({len(trace.splitlines())} lines)")
        else:
            assert trace == GOLDEN.read_text(), "trace differs from golden (re-run with --update-golden after review)"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--j81-msi-source", type=Path)
    parser.add_argument("--update-golden", action="store_true")
    args = parser.parse_args()
    check_text()
    if args.j81_msi_source:
        check_apply(args.j81_msi_source, args.update_golden)
    print("PASS" + (" (text contract + zero-fuzz apply + host trace)" if args.j81_msi_source else " (text contract only)"))


if __name__ == "__main__":
    main()
