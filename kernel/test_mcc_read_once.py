#!/usr/bin/env python3
"""Offline assert-based check for the one-shot MCC read module."""
from pathlib import Path
import subprocess
import tempfile

source = Path(__file__).resolve().parent / "mcc-read-once/mcc-read-once.c"
harness = r'''
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
typedef uint32_t u32;
typedef int atomic_t;
#define ATOMIC_INIT(v) (v)
#define __iomem
#define __init
#define PAGE_SIZE 4096
#define module_init(fn)
#define MODULE_LICENSE(v)
#define MODULE_DESCRIPTION(v)
#define THIS_MODULE ((struct module *)1)
#define IS_ERR(p) ((p) == (void *)-1)
#define PTR_ERR(p) (-ENOMEM)
#define DEVICE_ATTR(n, m, show, store) struct device_attribute dev_attr_##n = {.mode = (m)}
struct device {};
struct device_attribute { unsigned int mode; };
struct module {};
static struct device fake_device;
static struct device_attribute dev_attr_read_once;
static bool is_j81 = true, reserve_ok = true, map_ok = true;
static int reads, maps, reserves, releases, unmaps, creates, unregisters, pins;
static struct device *root_device_register(const char *name) { assert(!strcmp(name, "j81-mcc-read-once")); return &fake_device; }
static int device_create_file(struct device *d, struct device_attribute *a) { assert(d == &fake_device && a == &dev_attr_read_once); creates++; return 0; }
static void root_device_unregister(struct device *d) { assert(d == &fake_device); unregisters++; }
static void __module_get(struct module *m) { assert(m == THIS_MODULE); pins++; }
static bool of_machine_is_compatible(const char *name) { assert(!strcmp(name, "apple,j81")); return is_j81; }
static bool atomic_cmpxchg(atomic_t *p, int old, int newv) { int v = *p; if (v == old) *p = newv; return v; }
static void *request_mem_region(uint64_t start, uint64_t size, const char *name) { assert(start == 0x200000000ULL && size == 0x1000 && !strcmp(name, "j81-mcc-read-once")); reserves++; return reserve_ok ? (void *)1 : NULL; }
static void release_mem_region(uint64_t start, uint64_t size) { assert(start == 0x200000000ULL && size == 0x1000); releases++; }
static void *ioremap(uint64_t start, uint64_t size) { assert(start == 0x200000000ULL && size == 0x1000); maps++; return map_ok ? (void *)0x1000 : NULL; }
static u32 readl(void *p) { assert((uintptr_t)p == 0x1830); reads++; return 0x12345678; }
static void iounmap(void *p) { assert((uintptr_t)p == 0x1000); unmaps++; }
static int sysfs_emit(char *buf, const char *fmt, ...) { va_list ap; va_start(ap, fmt); int n = vsprintf(buf, fmt, ap); va_end(ap); return n; }
#include "mcc-read-once.c"
int main(void) {
  char out[128];
  assert(dev_attr_read_once.mode == 0400);
  is_j81 = false; assert(mcc_read_once_init() == -ENODEV && creates == 0);
  is_j81 = true; assert(mcc_read_once_init() == 0 && creates == 1 && reads == 0 && pins == 1);
  assert(read_once_show(&fake_device, &dev_attr_read_once, out) > 0);
  assert(!strcmp(out, "address=0x200000830 value=0x12345678\n"));
  assert(reads == 1 && reserves == 1 && maps == 1 && unmaps == 1 && releases == 1);
  assert(read_once_show(&fake_device, &dev_attr_read_once, out) == -EBUSY && reads == 1);
  attempted = 0; reserve_ok = false;
  assert(read_once_show(&fake_device, &dev_attr_read_once, out) == -EBUSY && reads == 1 && maps == 1);
  attempted = 0; reserve_ok = true; map_ok = false;
  assert(read_once_show(&fake_device, &dev_attr_read_once, out) == -ENOMEM && reads == 1 && releases == 2);
  return 0;
}
'''

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    (root / "linux").mkdir()
    for name in ("atomic.h", "io.h", "module.h", "of.h", "platform_device.h", "ioport.h"):
        (root / "linux" / name).write_text("")
    (root / "test.c").write_text(harness)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(root), "-I", str(source.parent), str(root / "test.c"), "-o", str(root / "test")], check=True)
    subprocess.run([str(root / "test")], check=True)
print("PASS: J81 guard, single bounded read, reservation, cleanup, and no repeat")
