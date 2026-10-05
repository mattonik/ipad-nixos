#!/usr/bin/env python3
"""Patch 0060 (per-controller IOVA window in the Apple DART): contract, apply, gap arithmetic.

Usage: python3 kernel/test_apple_dart_iova_window_patch.py [--j81-msi-source DIR]

DIR is the source tree of the 0057 kernel derivation (0055 applied). The pure helper
apple_dart_iova_window_gaps() is extracted from the patched driver and compiled on the host; its
output is checked so that window + doorbell page + gaps tile [0, top) exactly with no overlap.
"""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HERE = Path(__file__).parent
PATCH = HERE / "patches" / "0060-apple-dart-per-controller-iova-window.patch"
FILES = ("Documentation/devicetree/bindings/pci/apple,t7000-pcie.yaml",
         "arch/arm64/boot/dts/apple/t7001-air2.dtsi", "drivers/iommu/apple-dart.c")


def added(text):
    return "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))


def check_text():
    text = PATCH.read_text()
    touched = [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")]
    assert touched == list(FILES), touched
    plus = added(text)
    for fragment in ("apple,iova-window", "<0x0 0x80000000 0x0 0xbffff000>", "IOMMU_RESV_RESERVED",
                     "of_property_read_u64_index", "BIT_ULL(cfg->stream_maps[0].dart->ias)",
                     "uint64-array", "minItems: 2", "maxItems: 2"):
        assert fragment in plus, fragment
    code = "\n".join(l for l in plus.splitlines() if not l.lstrip().startswith(("/*", "*", "//")))
    # Property-gated and PCI-only: nothing here may change behaviour without the DT property, and
    # the DART is never programmed (no register access, no domain change).
    assert "dev_is_pci(dev)" in code and "apple_dart_pci_iova_window(dev, &start, &end)" in code
    for forbidden in ("writel", "readl", "dart_params", "IOMMU_RESV_MSI", "iommu_domain", "dma_min", "dma_max"):
        assert forbidden not in code, forbidden


def extract_helper(driver_text):
    a = driver_text.index("struct apple_dart_iova_gap {")
    b = driver_text.index("static void apple_dart_get_resv_regions")
    return driver_text[a:b]


HARNESS = r"""
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
typedef uint64_t u64;
#define PAGE_SIZE 4096ULL
#define PAGE_MASK (~(PAGE_SIZE - 1))
%s
static int fail;
static void expect(const char *name, u64 start, u64 end, u64 db, bool have, u64 top, int want_n)
{
    struct apple_dart_iova_gap g[2] = {{0,0},{0,0}};
    int n = apple_dart_iova_window_gaps(start, end, db, have, top, g);
    u64 total = 0;
    if (n != want_n) { printf("FAIL %%s: n=%%d want %%d\n", name, n, want_n); fail = 1; return; }
    for (int i = 0; i < n; i++) {
        total += g[i].len;
        /* No gap may touch the window, nor the doorbell page when it sits at the window end (a doorbell
           elsewhere simply lies inside a gap: overlapping reservations are harmless). */
        u64 gs = g[i].start, ge = g[i].start + g[i].len;
        if (ge > top) { printf("FAIL %%s: gap past top\n", name); fail = 1; }
        if (gs < end && ge > start) { printf("FAIL %%s: gap overlaps window\n", name); fail = 1; }
        if (have && (db & PAGE_MASK) == end && gs < db + PAGE_SIZE && ge > db) { printf("FAIL %%s: gap overlaps doorbell\n", name); fail = 1; }
    }
    if (n) {
        /* window + doorbell page (if it sits at end) + gaps tile [0, top). */
        u64 db_len = (have && (db & PAGE_MASK) == end) ? PAGE_SIZE : 0;
        if (total + (end - start) + db_len != top) { printf("FAIL %%s: does not tile [0,top)\n", name); fail = 1; }
    }
    printf("ok %%s: n=%%d", name, n);
    for (int i = 0; i < n; i++) printf(" [0x%%llx,+0x%%llx)", (unsigned long long)g[i].start, (unsigned long long)g[i].len);
    printf("\n");
}
int main(void)
{
    const u64 T = 1ULL << 32;
    expect("j81", 0x80000000ULL, 0xbffff000ULL, 0xbffff000ULL, true, T, 2);
    expect("no-doorbell", 0x80000000ULL, 0xbffff000ULL, 0, false, T, 2);
    expect("start-zero", 0, 0x40000000ULL, 0, false, T, 1);
    expect("end-at-top", 0x80000000ULL, T, 0, false, T, 1);
    expect("window-is-all", 0, T, 0, false, T, 0);
    expect("empty-window", 0x1000, 0x1000, 0, false, T, 0);
    expect("reversed", 0x2000, 0x1000, 0, false, T, 0);
    expect("past-top", 0x80000000ULL, T + 0x1000, 0, false, T, 0);
    expect("doorbell-elsewhere", 0x80000000ULL, 0xbffff000ULL, 0xfffff000ULL, true, T, 2);
    return fail;
}
"""


def check_gaps(driver_text):
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    assert cc, "no C compiler"
    with tempfile.TemporaryDirectory(prefix="dart-p60-") as tmp:
        src = Path(tmp) / "t.c"
        src.write_text(HARNESS % extract_helper(driver_text))
        r = subprocess.run([cc, "-std=gnu11", "-Wall", "-Wextra", str(src), "-o", str(Path(tmp) / "t")],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        run = subprocess.run([str(Path(tmp) / "t")], capture_output=True, text=True)
        assert run.returncode == 0, run.stdout
        out = run.stdout
        assert "ok j81: n=2 [0x0,+0x80000000) [0xc0000000,+0x40000000)" in out, out


def check_apply(source):
    with tempfile.TemporaryDirectory(prefix="dart-p60-tree-") as tmp:
        tree = Path(tmp)
        for rel in FILES:
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(source) / rel, tree / rel)
            (tree / rel).chmod((tree / rel).stat().st_mode | 0o200)
        r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(PATCH)], cwd=tree,
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        driver = (tree / FILES[2]).read_text()
        check_gaps(driver)
        # The 0055 doorbell reservation is untouched and still comes first.
        assert driver.index("IOMMU_RESV_MSI") < driver.index("IOMMU_RESV_RESERVED")
        assert "of_property_read_u64(parent->of_node, \"apple,msi-doorbell\", doorbell)" in driver


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--j81-msi-source", type=Path)
    args = parser.parse_args()
    check_text()
    if args.j81_msi_source:
        check_apply(args.j81_msi_source)
    print("PASS" + (" (text contract + zero-fuzz apply + gap arithmetic)" if args.j81_msi_source else " (text contract only)"))


if __name__ == "__main__":
    main()
