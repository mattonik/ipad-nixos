#!/usr/bin/env python3
"""Patches 0063/0064 (Apple DART PCI IOVA window and the rebase switch): contract, apply, math.

Usage: python3 kernel/test_apple_dart_pci_window_patch.py [--j81-msi-source DIR]

DIR is the source tree of the 0057 kernel derivation. 0063 gives PCI devices behind a controller
with `apple,iova-window` a DMA aperture (and, unless the controller lacks `apple,iova-rebase`
via 0064, Apple's rebase through the existing S5L8960X mask); 0064 only adds the DT flag.
The two pure helpers are extracted from the patched driver and compiled on the host.
"""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

HERE = Path(__file__).parent
P63 = HERE / "patches" / "0063-apple-dart-pci-iova-window.patch"
P64 = HERE / "patches" / "0064-t7001-air2-pcie-iova-rebase.patch"
DART = "drivers/iommu/apple-dart.c"
DTSI = "arch/arm64/boot/dts/apple/t7001-air2.dtsi"
YAML = "Documentation/devicetree/bindings/pci/apple,t7000-pcie.yaml"


def added(text):
    return "\n".join(l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++"))


def files(text):
    return [l.split(" b/")[1] for l in text.splitlines() if l.startswith("diff --git")]


def check_text():
    t63, t64 = P63.read_text(), P64.read_text()
    assert files(t63) == [YAML, DTSI, DART], files(t63)
    assert files(t64) == [YAML, DTSI], files(t64)
    p63, p64 = added(t63), added(t64)
    code = re.sub(r"/\*.*?\*/", "", p63, flags=re.S)
    # 0063 is a window source: property-gated, PCI-only, no register access, and it does not use
    # 0060's reserved-region approach (the two proposals are mutually exclusive).
    for fragment in ("apple,iova-window", "<0x0 0x80000000 0x0 0xbffff000>", "dev_is_pci(dev)",
                     "apple_dart_window_range(", "apple_dart_rebase_valid(", "cfg->pci_window",
                     "cfg->no_rebase", 'of_property_read_bool(apple_dart_pci_bridge_node(dev), "apple,iova-rebase")',
                     "uint64-array"):
        assert fragment in p63, fragment
    for forbidden in ("writel", "readl", "IOMMU_RESV_RESERVED", "iommu_alloc_resv_region", "apple,msi-doorbell"):
        assert forbidden not in code, forbidden
    # The rebase validity check only applies to controller-window users.
    assert "cfg->pci_window && !apple_dart_rebase_valid(" in p63
    # 0064 adds the flag only (no kernel code), in the DT and its binding.
    assert "apple,iova-rebase;" in p64 and "apple,iova-rebase:" in p64 and "type: boolean" in p64
    assert DART not in t64


HARNESS = r"""
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
typedef uint64_t u64; typedef uint32_t u32; typedef uint64_t dma_addr_t;
#define EINVAL 22
#define IS_ALIGNED(x, a) (((x) & ((a) - 1)) == 0)
#define DMA_BIT_MASK(n) (((n) == 64) ? ~0ULL : ((1ULL << (n)) - 1))
%s
static int fail;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %%d: %%s\n", __LINE__, #c); fail = 1; } } while (0)
int main(void)
{
    dma_addr_t lo, hi;
    /* J81: [0x80000000, 0xbffff000) */
    CHECK(apple_dart_window_range(0x80000000ULL, 0xbffff000ULL, 4096, 32, &lo, &hi) == 0);
    CHECK(lo == 0x80000000ULL && hi == 0xbfffefffULL);
    CHECK(apple_dart_rebase_valid(lo, hi));
    /* Rebase by clearing dma_min's bits equals subtraction for the whole window (and page 0 starts it). */
    u64 mask = ~lo;
    for (u64 a = lo; a <= hi; a += 0x1000) CHECK((a & mask) == a - lo);
    CHECK((0x80000000ULL & mask) == 0 && (0x80001000ULL & mask) == 0x1000 && (hi & mask) == 0x3fffefffULL);
    /* Raw model: the full-width mask leaves the IOVA unchanged. */
    CHECK((0x80000000ULL & DMA_BIT_MASK(32)) == 0x80000000ULL);
    /* Invalid windows are refused. */
    CHECK(apple_dart_window_range(0x1000, 0x1000, 4096, 32, &lo, &hi) == -EINVAL);            /* empty */
    CHECK(apple_dart_window_range(0x2000, 0x1000, 4096, 32, &lo, &hi) == -EINVAL);            /* reversed */
    CHECK(apple_dart_window_range(0x80000800ULL, 0xbffff000ULL, 4096, 32, &lo, &hi) == -EINVAL); /* unaligned start */
    CHECK(apple_dart_window_range(0x80000000ULL, 0xbffff800ULL, 4096, 32, &lo, &hi) == -EINVAL); /* unaligned end */
    CHECK(apple_dart_window_range(0x80000000ULL, 0x100001000ULL, 4096, 32, &lo, &hi) == -EINVAL); /* beyond ias */
    CHECK(apple_dart_window_range(0x80000000ULL, 0x100000000ULL, 4096, 32, &lo, &hi) == 0 && hi == 0xffffffffULL);
    /* Rebase validity: aperture must sit inside the block dma_min's lowest set bit opens. */
    CHECK(apple_dart_rebase_valid(0, 0xffffffffULL));                       /* no rebase needed */
    CHECK(apple_dart_rebase_valid(0x80000000ULL, 0xffffffffULL));
    CHECK(!apple_dart_rebase_valid(0x40000000ULL, 0xbfffefffULL));          /* would alias: clearing bit 30 != subtract */
    CHECK(apple_dart_rebase_valid(0xc0000000ULL, 0xdfffffffULL));          /* 0x1fffffff < lowest bit 0x40000000 */
    /* The aliasing case really would corrupt: 0x80000000 & ~0x40000000 != 0x80000000 - 0x40000000. */
    CHECK((0x80000000ULL & ~0x40000000ULL) != 0x80000000ULL - 0x40000000ULL);
    return fail;
}
"""


def check_math(driver_text):
    a = driver_text.index("/* Window [start, end) as an inclusive DMA range")
    b = driver_text.index("static int apple_dart_of_xlate")
    helpers = driver_text[a:b]
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    assert cc, "no C compiler"
    with tempfile.TemporaryDirectory(prefix="dart-p63-") as tmp:
        src = Path(tmp) / "t.c"
        src.write_text(HARNESS % helpers)
        r = subprocess.run([cc, "-std=gnu11", "-Wall", "-Wextra", "-Wno-unused-function", str(src),
                            "-o", str(Path(tmp) / "t")], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        run = subprocess.run([str(Path(tmp) / "t")], capture_output=True, text=True)
        assert run.returncode == 0, run.stdout


def check_apply(source):
    with tempfile.TemporaryDirectory(prefix="dart-p63-tree-") as tmp:
        tree = Path(tmp)
        for rel in (DART, DTSI, YAML):
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(source) / rel, tree / rel)
            (tree / rel).chmod((tree / rel).stat().st_mode | 0o200)
        for patch in (P63, P64):
            r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(patch)], cwd=tree,
                               capture_output=True, text=True)
            assert r.returncode == 0, patch.name + "\n" + r.stdout + r.stderr
        driver = (tree / DART).read_text()
        check_math(driver)
        # Existing users are untouched: the old masks remain as the fallbacks, after the new raw branch.
        assert "dart_domain->mask = ~cfg->dma_min;" in driver and "dart_domain->mask = DMA_BIT_MASK(pgtbl_cfg.ias);" in driver
        assert driver.index("cfg->pci_window && cfg->no_rebase") < driver.index("dart_domain->mask = ~cfg->dma_min;")
        dtsi = (tree / DTSI).read_text()
        assert dtsi.count("apple,iova-window") == 1 and dtsi.count("apple,iova-rebase;") == 1
        # 0063 alone (raw model) applies cleanly too.
    with tempfile.TemporaryDirectory(prefix="dart-p63-raw-") as tmp:
        tree = Path(tmp)
        for rel in (DART, DTSI, YAML):
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(source) / rel, tree / rel)
            (tree / rel).chmod((tree / rel).stat().st_mode | 0o200)
        r = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(P63)], cwd=tree,
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "apple,iova-rebase;" not in (tree / DTSI).read_text()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--j81-msi-source", type=Path)
    args = parser.parse_args()
    check_text()
    if args.j81_msi_source:
        check_apply(args.j81_msi_source)
    print("PASS" + (" (text contract + zero-fuzz apply + window/rebase math)" if args.j81_msi_source else " (text contract only)"))


if __name__ == "__main__":
    main()
