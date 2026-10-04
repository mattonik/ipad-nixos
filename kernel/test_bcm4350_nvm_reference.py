#!/usr/bin/env python3
"""Exercise exact public DHD NVM-dump logic with synthetic cores, not MMIO."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile

SOURCE_HASH = "837e468f978ac9b7f670aa335c2b18b03b8c74b28deaad77d30dee33729aa17c"
HEADER_HASH = "ae1ea2b9b96531f4dddfd73a2540bfe026082da36ba19aeba17e305e2e89a45e"
CONSTANTS = ("SRC_PRESENT", "SRC_OTPSEL", "SRC_OTPPRESENT", "SRC_SIZE_MASK", "SRC_SIZE_SHIFT",
             "OTPL_WRAP_TYPE_MASK", "OTPL_WRAP_TYPE_SHIFT", "OTPL_WRAP_TYPE_40NM",
             "OTPL_ROW_SIZE_MASK", "OTPL_ROW_SIZE_SHIFT", "CC_CAP_OTPSIZE", "CC_CAP_OTPSIZE_SHIFT")

PRELUDE = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef unsigned int uint;
typedef uint16_t uint16;
typedef uint32_t uint32;
#define ASSERT assert
#define DHD_ERROR(x) ((void)0)
#define DHD_INFO(x) ((void)0)
#define BCME_OK 0
#define BCME_UNSUPPORTED -1
#define BCME_NOTFOUND -2
#define BCME_NOTREADY -3
#define BCM4350_CHIP_ID 4350
#define BCM4355_CHIP_ID 4355
#define BCM4364_CHIP_ID 4364
#define BCM4345_CHIP(x) ((x)==4345)
#define CC_CORE_ID 1
#define GCI_CORE_ID 2
#define ORIGINAL_CORE 3
typedef struct { uint32 capabilities, otplayout, sromcontrol; uint16 sromotp[512]; } chipcregs_t;
typedef struct { uint chip, rev, id, unit; } si_t;
typedef struct { si_t *sih; void *regs; } dhd_bus_t;
struct bcmstrbuf { unsigned int reads; };
static chipcregs_t cc;
static uint16 gci[1024];
static int missing_gci;
static uint si_coreid(si_t *s) { return s->id; }
static uint si_corerev(si_t *s) { return s->rev; }
static void *si_setcore(si_t *s, uint id, uint unit)
{
    if (id==GCI_CORE_ID && missing_gci) return NULL;
    s->id=id; s->unit=unit;
    return id==CC_CORE_ID ? (void*)&cc : (void*)gci;
}
static int bcm_bprintf(struct bcmstrbuf *b, const char *format, ...)
{ if (!strcmp(format,"\t0x%04x")) b->reads++; return 0; }
'''

TESTS = r'''
static si_t si;
static dhd_bus_t bus;
static struct bcmstrbuf output;
static void reset(uint rev)
{
    memset(&cc,0,sizeof(cc)); memset(&output,0,sizeof(output)); missing_gci=0;
    si=(si_t){4350,rev,ORIGINAL_CORE,1}; bus=(dhd_bus_t){&si,&cc};
    cc.otplayout=OTPL_WRAP_TYPE_40NM<<OTPL_WRAP_TYPE_SHIFT;
    cc.capabilities=1u<<CC_CAP_OTPSIZE_SHIFT;
    cc.sromcontrol=SRC_OTPPRESENT|SRC_OTPSEL;
}
int main(int argc, char **argv)
{
    if (argc>1 && !strcmp(argv[1],"bad-index")) {
        reset(49); cc.otplayout=8u<<OTPL_ROW_SIZE_SHIFT;
        (void)dhdpcie_cc_nvmshadow(&bus,&output); return 0;
    }
    reset(43); assert(dhdpcie_cc_nvmshadow(&bus,&output)==BCME_UNSUPPORTED);
    assert(si.id==CC_CORE_ID && output.reads==0);
    reset(44); si.chip=999; assert(dhdpcie_cc_nvmshadow(&bus,&output)==BCME_UNSUPPORTED);
    assert(si.id==CC_CORE_ID);
    reset(44); bus.regs=NULL; assert(dhdpcie_cc_nvmshadow(&bus,&output)==BCME_NOTREADY);
    assert(si.id==CC_CORE_ID && output.reads==0);
    reset(44); cc.capabilities=0;
    assert(dhdpcie_cc_nvmshadow(&bus,&output)==BCME_NOTFOUND && output.reads==0);
    reset(44); assert(dhdpcie_cc_nvmshadow(&bus,&output)==BCME_OK && output.reads==128);
    assert(si.id==ORIGINAL_CORE && si.unit==0); /* Original unit 1 was lost. */
    for(uint encoding=0;encoding<3;encoding++) {
        reset(44); cc.sromcontrol=SRC_PRESENT|(encoding<<SRC_SIZE_SHIFT);
        assert(dhdpcie_cc_nvmshadow(&bus,&output)==BCME_OK && output.reads==512);
    }
    for(uint encoding=1;encoding<8;encoding++) {
        reset(44); cc.capabilities=encoding<<CC_CAP_OTPSIZE_SHIFT;
        assert(dhdpcie_cc_nvmshadow(&bus,&output)==BCME_OK);
        assert(output.reads==(encoding+1)*64);
    }
    reset(49); cc.otplayout|=11u<<OTPL_ROW_SIZE_SHIFT;
    assert(dhdpcie_cc_nvmshadow(&bus,&output)==BCME_OK && output.reads==768);
    reset(51); cc.otplayout|=11u<<OTPL_ROW_SIZE_SHIFT;
    assert(dhdpcie_cc_nvmshadow(&bus,&output)==BCME_OK && output.reads==128);
    reset(49); cc.otplayout|=11u<<OTPL_ROW_SIZE_SHIFT; missing_gci=1;
    assert(dhdpcie_cc_nvmshadow(&bus,&output)==BCME_NOTFOUND && si.id==CC_CORE_ID);
    reset(44); cc.sromcontrol=SRC_OTPPRESENT; /* No SPROM and OTPSEL clear. */
    assert(dhdpcie_cc_nvmshadow(&bus,&output)==BCME_OK && output.reads==128);
    puts("PASS: legacy sizes, rev49/51 mapping, strap selection, early-exit core leakage, instance-loss and SPROM over-dump reproducers");
    return 0;
}
'''


def pinned(path, expected, parser):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        parser.error(f"{path.name} differs from reviewed DHD pin")
    return data.decode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--header", type=Path, required=True)
    parser.add_argument("--cc", default=os.environ.get("CC", "gcc"))
    parser.add_argument("--sanitize", action="store_true")
    args = parser.parse_args()
    source = pinned(args.source, SOURCE_HASH, parser)
    header = pinned(args.header, HEADER_HASH, parser)
    start = source.index("static int\ndhdpcie_cc_nvmshadow(dhd_bus_t *bus, struct bcmstrbuf *b)\n{")
    end = source.index("} /* dhdpcie_cc_nvmshadow */", start) + 1
    defines = "\n".join(re.search(r"^#define\s+" + name + r"\s+[^\n]+", header, re.M)[0] for name in CONSTANTS)
    with tempfile.TemporaryDirectory(prefix="bcm4350-reference-") as directory:
        root = Path(directory)
        file = root / "test.c"
        file.write_text(PRELUDE + defines + "\n" + source[start:end] + TESTS)
        executable = root / "test"
        command = [args.cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-O1", "-g"]
        if args.sanitize:
            command += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
        subprocess.run(command + [str(file), "-o", str(executable)], check=True)
        subprocess.run([str(executable)], check=True)
        if args.sanitize:
            result = subprocess.run([str(executable), "bad-index"], capture_output=True, text=True)
            diagnostic = result.stdout + result.stderr
            if result.returncode == 0 or "index 8 out of bounds" not in diagnostic:
                raise RuntimeError("expected source table-index sanitizer diagnostic was not reproduced")
            print("CONFIRMED: 65nm row index 8 exceeds eight-entry table (synthetic state)")
    print("Reference-only: no J81 metadata, power transition, PCI mapping or hardware access validated")


if __name__ == "__main__":
    main()
