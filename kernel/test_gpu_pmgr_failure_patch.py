#!/usr/bin/env python3
"""Check the isolated PMGR patch; optionally run its actual function with fake regmap."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
PATCH = HERE / "patches/0123-apple-pmgr-pwrstate-stop-on-errors.patch"
OBSERVE = HERE.parent / "research/probes/j81-linux-gfx-request.patch"
DRIVER = Path("drivers/pmdomain/apple/pmgr-pwrstate.c")

SHIM = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
struct generic_pm_domain { const char *name; };
struct regmap { int fail, reads, writes, polls; u32 written[2], poll_extra; };
struct apple_pmgr_ps { void *dev; struct regmap *regmap; u32 offset; bool j81_test_no_poweroff; };
static struct apple_pmgr_ps test_ps;
#define genpd_to_apple_pmgr_ps(g) ((void)(g), &test_ps)
#define APPLE_PMGR_RESET (1u << 31)
#define APPLE_PMGR_AUTO_ENABLE (1u << 28)
#define APPLE_PMGR_FLAGS (3u << 8)
#define APPLE_PMGR_PS_TARGET 15u
#define APPLE_PMGR_PS_ACTUAL 0xf0u
#define APPLE_PMGR_PS_ACTIVE 15u
#define APPLE_PMGR_PS_PWRGATE 0u
#define APPLE_PMGR_PS_SET_TIMEOUT 100
#define FIELD_PREP(mask, val) ((val) & (mask))
#define FIELD_GET(mask, val) (((val) & (mask)) >> 4)
#define dev_err(...) ((void)0)
#define dev_dbg(...) ((void)0)
#define dev_info(dev, ...) printf(__VA_ARGS__)
#define task_pid_nr(task) 123
#define of_machine_is_compatible(name) (strcmp(name, "apple,j81") == 0)
static int regmap_read(struct regmap *m, u32 offset, u32 *value) {
    (void)offset; m->reads++; *value = 0x300;
    return m->fail == 1 ? -10 : 0;
}
static int regmap_write(struct regmap *m, u32 offset, u32 value) {
    (void)offset; assert(m->writes < 2); m->written[m->writes++] = value;
    return m->fail == m->writes + 1 ? -10 - m->writes : 0;
}
static int fake_poll(struct regmap *m, u32 *value) {
    m->polls++; *value = ((m->written[0] & 15u) << 4) | m->poll_extra;
    return m->fail == 4 ? -14 : 0;
}
#define regmap_read_poll_timeout_atomic(map, offset, value, condition, delay, timeout) fake_poll((map), &(value))
'''
CHECKS = r'''
int main(void) {
    struct generic_pm_domain domain = { .name = "gfx" };
    struct regmap map = {0};
    test_ps.regmap = &map;
    test_ps.offset = 0x20320;
    for (int failure = 0; failure <= 4; failure++) {
        map = (struct regmap){ .fail = failure };
        int ret = apple_pmgr_ps_set(&domain, 15, true);
        assert(map.reads == 1);
        if (failure == 1) { assert(ret == -10 && map.writes == 0 && map.polls == 0); }
        if (failure == 2) { assert(ret == -11 && map.writes == 1 && map.polls == 0); }
        if (failure == 4) { assert(ret == -14 && map.writes == 1 && map.polls == 1); }
        if (failure == 3) { assert(ret == -12 && map.writes == 2 && map.polls == 1); }
        if (failure == 0) {
            assert(ret == 0 && map.writes == 2 && map.polls == 1);
            assert(map.written[0] == 15 && map.written[1] == (0xf0 | APPLE_PMGR_AUTO_ENABLE));
        }
    }
    /* The published J81 poll sample includes both history bits and TARGET=15. */
    map = (struct regmap){ .poll_extra = 0x30f };
    assert(apple_pmgr_ps_set(&domain, 15, true) == 0);
    assert(map.reads == 1 && map.polls == 1 && map.writes == 2);
    assert(map.written[0] == 0xf && map.written[1] == 0x100000ff);
    map = (struct regmap){0};
    assert(apple_pmgr_ps_set(&domain, 0, false) == 0);
    assert(map.writes == 1 && map.polls == 1);
    map = (struct regmap){0};
    test_ps.j81_test_no_poweroff = true;
    assert(apple_pmgr_ps_power_off(&domain) == -EPERM);
    assert(map.reads == 0 && map.writes == 0 && map.polls == 0);
    test_ps.j81_test_no_poweroff = false;
    assert(apple_pmgr_ps_power_off(&domain) == 0);
    assert(map.reads == 1 && map.writes == 1 && map.polls == 1);
    domain.name = "uart";
    map = (struct regmap){0};
    assert(apple_pmgr_ps_set(&domain, 15, true) == 0);
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="pinned pmgr-pwrstate.c")
    parser.add_argument("--cc", default="cc")
    parser.add_argument("--trace-gfx", action="store_true", help="also build and verify the optional J81 request observer")
    args = parser.parse_args()
    if args.trace_gfx and not args.source:
        parser.error("--trace-gfx requires --source")
    text = PATCH.read_text()
    assert text.count("+\tret = regmap_write") == 1
    assert "+\t\tret = regmap_write" in text
    assert "+\t\treturn ret;" in text
    if not args.source:
        print("PASS: patch contract (supply --source to compile and exercise patched function)")
        return
    with tempfile.TemporaryDirectory(prefix="gpu-pmgr-") as tmp:
        root = Path(tmp)
        target = root / DRIVER
        target.parent.mkdir(parents=True)
        shutil.copyfile(args.source, target)
        for patch in [PATCH, OBSERVE] if args.trace_gfx else [PATCH]:
            subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(patch)], cwd=root, check=True, capture_output=True)
        source = target.read_text()
        start = source.index("static int apple_pmgr_ps_set(")
        end = source.index("\nstatic bool apple_pmgr_ps_is_active(", start)
        off_start = source.index("static int apple_pmgr_ps_power_off(")
        off_end = source.index("\nstatic ", off_start + 1)
        test = root / "test.c"
        test.write_text(SHIM + source[start:end] + source[off_start:off_end] + CHECKS)
        subprocess.run([args.cc, "-std=c11", "-Wall", "-Wextra", "-Werror", str(test), "-o", str(root / "test")], check=True)
        run = subprocess.run([str(root / "test")], check=True, capture_output=True, text=True)
        if args.trace_gfx:
            prefix = "gfx-request pid=123 old=00000300 "
            assert run.stdout.splitlines() == [prefix + row for row in [
                "request=0000000f poll=000000f0 auto=1 auto_word=100000f0 rc=0",
                "request=0000000f poll=000000f0 auto=1 auto_word=100000f0 rc=-12",
                "request=0000000f poll=000003ff auto=1 auto_word=100000ff rc=0",
                "request=00000000 poll=00000000 auto=0 auto_word=00000000 rc=0",
                "request=00000000 poll=00000000 auto=0 auto_word=00000000 rc=0",
            ]]
            print("PASS: GFX request observer on the compiled Linux setter with simulated register values")
    print("PASS: patch applied with zero fuzz; actual function passed simulated PMGR failures")


if __name__ == "__main__":
    main()
