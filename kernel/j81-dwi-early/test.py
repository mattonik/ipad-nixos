#!/usr/bin/env python3
"""Host-only behavioral check of the exact patched power-off callback."""
from pathlib import Path
import argparse
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('source', type=Path, help='pinned drivers/pmdomain/apple/pmgr-pwrstate.c')
source = parser.parse_args().source
import hashlib
assert hashlib.sha256(source.read_bytes()).hexdigest() == '4b0adc3013e2fabe9ca1cb8228f8f6b7934af4b667f7f0f893b675102d8710df'
with tempfile.TemporaryDirectory() as tmp:
    tree = Path(tmp)
    target = tree / 'drivers/pmdomain/apple/pmgr-pwrstate.c'
    target.parent.mkdir(parents=True)
    target.write_bytes(source.read_bytes())
    for patch in (root / 'kernel/patches/0123-apple-pmgr-pwrstate-stop-on-errors.patch', root / 'kernel/j81-dwi-early/early.patch'):
        subprocess.run(['patch', '-s', '-p1', '-i', str(patch)], cwd=tree, check=True)
    text = target.read_text()
    assert 'ps->offset == 0x20120 && !strcmp(name, "dwi")' in text
    assert 'of_machine_is_compatible("apple,j81")' in text
    assert 'of_device_is_compatible(node, "apple,t7000-pmgr-pwrstate")' in text
    start = text.index('static int apple_pmgr_ps_power_off(')
    end = text.index('\nstatic int apple_pmgr_reset_assert(', start)
    callback = text[start:end]
    harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
struct generic_pm_domain { int dummy; };
struct apple_pmgr_ps { int j81_test_no_poweroff, j81_dwi_trace; void *dev; } fake_ps;
static bool j81_dwi_hold;
static int sets, logs, result;
#define genpd_to_apple_pmgr_ps(g) ((void)(g), &fake_ps)
#define APPLE_PMGR_PS_PWRGATE 0
#define dev_info(...) ((void)0)
static void j81_dwi_log(struct apple_pmgr_ps *p, const char *phase) { (void)p; (void)phase; logs++; }
static int apple_pmgr_ps_set(struct generic_pm_domain *g, int state, bool auto_enable) {
    (void)g; assert(state == 0 && !auto_enable); sets++; return result;
}
''' + callback + r'''
int main(void) {
    struct generic_pm_domain g;
    fake_ps.j81_dwi_trace=1; j81_dwi_hold=1;
    assert(apple_pmgr_ps_power_off(&g)==-EBUSY && sets==0 && logs==1);
    j81_dwi_hold=0; result=-EIO;
    assert(apple_pmgr_ps_power_off(&g)==-EIO && sets==1 && logs==3);
    fake_ps.j81_dwi_trace=0; j81_dwi_hold=1; result=0;
    assert(apple_pmgr_ps_power_off(&g)==0 && sets==2 && logs==3);
    fake_ps.j81_test_no_poweroff=1;
    assert(apple_pmgr_ps_power_off(&g)==-EPERM && sets==2);
    return 0;
}
'''
    (tree / 'check.c').write_text(harness)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(tree / 'check.c'), '-o', str(tree / 'check')], check=True)
    subprocess.run([str(tree / 'check')], check=True)
print('PASS: pinned patches apply; callback only holds matched DWI and preserves errors')
