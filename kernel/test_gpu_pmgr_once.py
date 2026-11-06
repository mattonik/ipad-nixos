#!/usr/bin/env python3
"""Compile the one-shot module with fake OF, genpd, and runtime-PM APIs."""
from pathlib import Path
import subprocess
import tempfile

SOURCE = Path(__file__).resolve().parent / "gpu-pmgr-once/gpu-pmgr-once.c"
HARNESS = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <sys/types.h>
typedef uint32_t u32;
typedef int atomic_t;
#define ATOMIC_INIT(x) (x)
static int atomic_cmpxchg(atomic_t *v, int old, int newval) { int was = *v; if (was == old) *v = newval; return was; }
#define smp_load_acquire(p) (*(p))
#define smp_store_release(p, v) (*(p) = (v))
#define __init
#define module_init(fn)
#define MODULE_LICENSE(x)
#define MODULE_DESCRIPTION(x)
#define IS_ERR(p) ((p) == (void *)-1)
#define PTR_ERR(p) ((void)(p), -ENOMEM)
struct device_node { struct device_node *parent; };
struct regmap { int unused; };
struct resource { uint64_t start, end; };
#define resource_size(r) ((r)->end - (r)->start + 1)
struct device_driver { const char *name; };
struct device { struct device_driver *driver; };
struct platform_device { struct device dev; };
struct device_attribute { int unused; };
struct of_phandle_args { struct device_node *np; int args_count; };
#define DEVICE_ATTR_WO(name) struct device_attribute dev_attr_##name
static struct device fake_device;
static struct device_driver fake_driver = { "apple-pmgr-pwrstate" };
static struct device_driver wrong_driver = { "wrong" };
static struct platform_device fake_provider;
static struct device_node fake_node;
static struct regmap fake_regmap;
static int fault, attaches, enables, gets, reads, files, removes, unregisters, pm_result, read_result;
static u32 read_value = 0x300;
const bool j81_gpu_pmgr_failstop_v1 = true;
static bool of_machine_is_compatible(const char *s) { (void)s; return fault != 1; }
static struct device_node *of_find_node_by_path(const char *s) { (void)s; return fault == 2 ? NULL : &fake_node; }
static bool of_device_is_available(struct device_node *n) { (void)n; return fault != 3; }
static bool of_device_is_compatible(struct device_node *n, const char *s) { (void)n; (void)s; return fault != 4; }
static bool of_property_read_bool(struct device_node *n, const char *s) {
    (void)n;
    if (!strcmp(s, "experimental,j81-gpu-test-no-poweroff")) return fault != 5;
    if (!strcmp(s, "power-domains")) return fault == 6;
    return false;
}
static int of_property_read_u32(struct device_node *n, const char *s, u32 *v) { (void)n; (void)s; *v = fault == 16 ? 1 : 0; return 0; }
static int of_property_count_u32_elems(struct device_node *n, const char *s) { (void)n; (void)s; return fault == 17 ? 3 : 2; }
static int of_address_to_resource(struct device_node *n, int i, struct resource *r) {
    (void)n; (void)i; r->start = fault == 18 ? 0 : 0x20e000000ULL; r->end = r->start + (fault == 19 ? 0x1000 : 0x24000) - 1; return 0;
}
static int of_property_read_u32_array(struct device_node *n, const char *s, u32 *v, int count) {
    (void)n; (void)s; assert(count == 2); v[0] = fault == 7 ? 0 : 0x20320; v[1] = 4; return 0;
}
static void of_node_put(struct device_node *n) { (void)n; }
static struct platform_device *of_find_device_by_node(struct device_node *n) {
    (void)n; fake_provider.dev.driver = fault == 15 ? &wrong_driver : &fake_driver;
    return fault == 13 ? NULL : &fake_provider;
}
static void device_lock(struct device *d) { (void)d; }
static void device_unlock(struct device *d) { (void)d; }
static void put_device(struct device *d) { (void)d; }
static bool device_is_bound(struct device *d) { (void)d; return fault != 14; }
static struct regmap *syscon_node_to_regmap(struct device_node *n) { (void)n; return fault == 12 ? (void *)-1 : &fake_regmap; }
static int regmap_read(struct regmap *m, u32 offset, u32 *v) { assert(m == &fake_regmap && offset == 0x20320); reads++; *v = read_value; return read_result; }
static struct device *root_device_register(const char *s) { assert(!strcmp(s, "gpu-pmgr-once")); return fault == 8 ? (void *)-1 : &fake_device; }
static void root_device_unregister(struct device *d) { assert(d == &fake_device); unregisters++; }
static int device_create_file(struct device *d, struct device_attribute *a) { (void)d; (void)a; files++; return fault == 9 ? -ENOMEM : 0; }
static void device_remove_file(struct device *d, struct device_attribute *a) { (void)d; (void)a; removes++; }
static int pm_runtime_set_suspended(struct device *d) { (void)d; return fault == 10 ? -EINVAL : 0; }
static int of_genpd_add_device(struct of_phandle_args *a, struct device *d) {
    assert(a->np == &fake_node && a->args_count == 0 && d == &fake_device);
    attaches++; return fault == 11 ? -EINVAL : 0;
}
static void pm_runtime_enable(struct device *d) { assert(d == &fake_device); enables++; }
static int pm_runtime_get_sync(struct device *d) { assert(d == &fake_device); gets++; return pm_result; }
static bool sysfs_streq(const char *a, const char *b) { return !strcmp(a,b) || (!strcmp(a,"1\n") && !strcmp(b,"1")); }
#include "gpu-pmgr-once.c"
int main(void) {
    for (fault = 1; fault <= 19; fault++) {
        ready = false; attempted = 0; attaches = enables = gets = reads = files = removes = unregisters = 0;
        assert(gpu_pmgr_once_init() < 0);
        assert(!ready && gets == 0 && enables == 0);
        if (fault < 11 || fault >= 12) assert(attaches == 0);
        if (fault == 11) assert(attaches == 1);
        if (fault >= 9 && fault <= 11) assert(unregisters == 1);
        if (fault >= 10 && fault <= 11) assert(removes == 1);
    }
    fault = 0; ready = false; attempted = 0; attaches = enables = gets = 0;
    assert(power_once_store(&fake_device, NULL, "1\n", 2) == -EAGAIN);
    assert(gpu_pmgr_once_init() == 0);
    assert(ready && attaches == 1 && enables == 1 && gets == 0 && reads == 0);
    assert(power_once_store(&fake_device, NULL, "no", 2) == -EINVAL && gets == 0);
    read_result = -EIO;
    assert(power_once_store(&fake_device, NULL, "1\n", 2) == -EIO && gets == 0);
    assert(power_once_store(&fake_device, NULL, "1\n", 2) == -EBUSY && gets == 0);
    attempted = 0; read_result = 0; read_value = 0xf0;
    assert(power_once_store(&fake_device, NULL, "1\n", 2) == -EBUSY && gets == 0);
    attempted = 0; read_value = 0x300;
    pm_result = -EIO;
    assert(power_once_store(&fake_device, NULL, "1\n", 2) == -EIO && gets == 1);
    assert(power_once_store(&fake_device, NULL, "1\n", 2) == -EBUSY && gets == 1);
    attempted = 0; gets = 0; pm_result = 1;
    assert(power_once_store(&fake_device, NULL, "1\n", 2) == 2 && gets == 1);
    assert(power_once_store(&fake_device, NULL, "1\n", 2) == -EBUSY && gets == 1);
    return 0;
}
'''

with tempfile.TemporaryDirectory(prefix="gpu-once-") as directory:
    root = Path(directory)
    (root / "linux").mkdir()
    (root / "linux" / "mfd").mkdir()
    (root / "linux" / "mfd" / "syscon.h").write_text("")
    for name in ("atomic.h", "device.h", "init.h", "module.h", "of.h", "of_address.h", "of_platform.h", "platform_device.h", "pm_domain.h", "pm_runtime.h", "regmap.h", "string.h"):
        (root / "linux" / name).write_text("")
    (root / "test.c").write_text(HARNESS)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(root),
                    "-I", str(SOURCE.parent), str(root / "test.c"), "-o", str(root / "test")], check=True)
    subprocess.run([str(root / "test")], check=True)
    missing_marker = HARNESS.replace("const bool j81_gpu_pmgr_failstop_v1 = true;",
                                     "const bool j81_gpu_pmgr_failstop_v1 = false;")
    missing_marker = missing_marker[:missing_marker.index("int main(void)")] + (
        "int main(void) { (void)power_once_store; assert(gpu_pmgr_once_init() == -ENODEV); "
        "assert(attaches == 0 && gets == 0 && reads == 0); return 0; }\n")
    (root / "test.c").write_text(missing_marker)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(root),
                    "-I", str(SOURCE.parent), str(root / "test.c"), "-o", str(root / "test")], check=True)
    subprocess.run([str(root / "test")], check=True)
print("PASS: attachment is inert in the mock; power request is one-shot even on error")
