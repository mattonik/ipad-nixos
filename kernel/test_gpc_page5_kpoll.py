#!/usr/bin/env python3
"""Host-check order, guards, one-shot and timing brackets of the GPC/page-5 module."""
from pathlib import Path
import subprocess
import tempfile

source = Path(__file__).resolve().parent / "gpc-page5-kpoll/gpc-page5-kpoll.c"
harness = r'''
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
typedef uint32_t u32; typedef uint64_t u64; typedef int atomic_t;
#define ATOMIC_INIT(v) (v)
#define __iomem
#define __init
#define PAGE_SIZE 4096
#define module_init(fn)
#define module_param(n,t,m)
#define MODULE_LICENSE(v)
#define MODULE_DESCRIPTION(v)
#define THIS_MODULE ((struct module *)1)
#define IS_ERR(p) ((p) == (void *)-1)
#define PTR_ERR(p) (-ENOMEM)
#define DEVICE_ATTR(n,m,show,store) struct device_attribute dev_attr_##n = {.mode=(m)}
struct device {}; struct device_attribute { unsigned int mode; }; struct module {};
static struct device fake_device;
#define GPC ((char *)0x100000)
#define P5 ((char *)0x200000)
enum { EV_W, EV_POLL, EV_P5, EV_SLEEP, EV_UDELAY };
static struct { int kind; unsigned off; u32 value; int irqs_off; } ev[4096];
static int nev, irqs_off, maps, unmaps, creates, pins, unregs, fail_map, fail_create;
static bool is_j81 = true;
static u64 now;
static int busy_polls; static u32 final_state = 1, state_value;
static void log_ev(int kind, unsigned off, u32 value) { assert(nev < 4096); ev[nev].kind = kind; ev[nev].off = off; ev[nev].value = value; ev[nev++].irqs_off = irqs_off; }
static struct device *root_device_register(const char *name) { assert(!strcmp(name, "j81-gpc-page5-kpoll")); return &fake_device; }
static int device_create_file(struct device *d, struct device_attribute *a) { assert(d == &fake_device && a->mode == 0400); if (++creates == fail_create) return -ENOMEM; return 0; }
static void root_device_unregister(struct device *d) { assert(d == &fake_device); unregs++; }
static void __module_get(struct module *m) { assert(m == THIS_MODULE); pins++; }
static bool of_machine_is_compatible(const char *name) { assert(!strcmp(name, "apple,j81")); return is_j81; }
static int atomic_cmpxchg(atomic_t *p, int old, int v) { int previous = *p; if (previous == old) *p = v; return previous; }
static void *ioremap(uint64_t start, uint64_t size) {
 maps++;
 if (start == 0x201e00000ULL) { assert(size == 0x11000); return fail_map == 1 ? NULL : GPC; }
 assert(start == 0x20e005000ULL && size == 0x1000); return fail_map == 2 ? NULL : P5;
}
static void iounmap(void *p) { assert(p == GPC || p == P5); unmaps++; }
static u32 readl(void *p) {
 now += 40;
 if (p == (void *)(P5 + 4)) { log_ev(EV_P5, 4, 0); return 0x40000000; }
 assert(p == (void *)(GPC + 0x1000));
 if (!nev) { log_ev(EV_POLL, 0x1000, state_value); return state_value; }
 u32 v = busy_polls-- > 0 ? 0x11 : final_state; log_ev(EV_POLL, 0x1000, v); return v;
}
static void writel(u32 v, void *p) { char *c = p; assert(c >= GPC && c < GPC + 0x11000); now += 40; log_ev(EV_W, (unsigned)(c - GPC), v); }
static void mb(void) {}
static unsigned long irq_depth;
#define local_irq_save(f) do { assert(!irqs_off); irqs_off = 1; (f) = ++irq_depth; } while (0)
#define local_irq_restore(f) do { assert(irqs_off && (f) == irq_depth); irqs_off = 0; } while (0)
static u64 ktime_get_raw_fast_ns(void) { return now += 7; }
static void usleep_range(unsigned long lo, unsigned long hi) { assert(!irqs_off && lo == 10 && hi == 20); now += 15000; log_ev(EV_SLEEP, 0, 0); }
static void udelay(unsigned long us) { assert(irqs_off && us == 100); now += us * 1000; log_ev(EV_UDELAY, 0, 0); }
static int sysfs_emit(char *b, const char *f, ...) { va_list a; va_start(a, f); int n = vsprintf(b, f, a); va_end(a); return n; }
#include "gpc-page5-kpoll.c"

static void reset(const char *m) {
 nev = irqs_off = maps = unmaps = creates = pins = unregs = fail_map = fail_create = 0;
 is_j81 = true; now = 1000; busy_polls = 0; final_state = 1; state_value = 0;
 mode = (char *)m; mode_id = -1; state_attempted = batch_attempted = 0; state_known = 0; initial_state = 0;
}
static int count(int kind) { int n = 0; for (int i = 0; i < nev; i++) n += ev[i].kind == kind; return n; }
static void check_writes(void) {
 assert(ev[1].kind == EV_W && ev[1].off == 0x10000 && ev[1].value == 0xffff0000);
 assert(ev[2].kind == EV_W && ev[2].off == 0 && ev[2].value == 0x40000000);
 assert(ev[3].kind == EV_W && ev[3].off == 0x1000 && ev[3].value == 0x11 && ev[3].irqs_off);
 assert(count(EV_W) == 3);
}
int main(void) {
 char out[512], want[512]; unsigned polls, fv, lv; u32 raw, first, later; unsigned long long pre, post, fns, lns; char m[16];
 assert(dev_attr_gpc_state.mode == 0400 && dev_attr_batch.mode == 0400);
 /* Guards: wrong machine, missing or unknown mode, each failed mapping, failed attribute. */
 reset("immediate"); is_j81 = false; assert(gpc_page5_kpoll_init() == -ENODEV && !maps);
 reset(NULL); assert(gpc_page5_kpoll_init() == -ENODEV && !maps);
 reset("write"); assert(gpc_page5_kpoll_init() == -ENODEV && !maps);
 reset("paired"); fail_map = 1; assert(gpc_page5_kpoll_init() == -ENOMEM && maps == 1 && !unmaps && !creates && !nev);
 reset("paired"); fail_map = 2; assert(gpc_page5_kpoll_init() == -ENOMEM && maps == 2 && unmaps == 1 && !creates && !nev);
 reset("paired"); fail_create = 2; assert(gpc_page5_kpoll_init() == -ENOMEM && unmaps == 2 && unregs == 1 && !pins && !nev);
 /* Loading touches no register. */
 reset("immediate"); assert(gpc_page5_kpoll_init() == 0 && maps == 2 && creates == 2 && pins == 1 && !nev);
 /* Batch refuses before the state read, and that refusal is final. */
 assert(batch_show(&fake_device, &dev_attr_batch, out) == -EINVAL && !nev);
 assert(batch_show(&fake_device, &dev_attr_batch, out) == -EBUSY && !nev);
 /* Non-zero initial state: no write. */
 reset("immediate"); assert(!gpc_page5_kpoll_init()); state_value = 1;
 assert(gpc_state_show(&fake_device, &dev_attr_gpc_state, out) > 0 && !strcmp(out, "address=0x201e01000 value=0x00000001\n"));
 assert(gpc_state_show(&fake_device, &dev_attr_gpc_state, out) == -EBUSY);
 assert(batch_show(&fake_device, &dev_attr_batch, out) == -EINVAL && nev == 1);
 /* Immediate: poll then page-5 load with nothing in between, IRQs masked. */
 reset("immediate"); assert(!gpc_page5_kpoll_init()); busy_polls = 3;
 assert(gpc_state_show(&fake_device, &dev_attr_gpc_state, out) > 0 && !strcmp(out, "address=0x201e01000 value=0x00000000\n"));
 assert(batch_show(&fake_device, &dev_attr_batch, out) > 0); check_writes();
 assert(sscanf(out, "result=ok mode=%15s raw=0x%8x polls=%u prewrite_ns=%llu postwrite_ns=%llu first_valid=%u first=0x%8x first_ns=%llu later_valid=%u later=0x%8x later_ns=%llu", m, &raw, &polls, &pre, &post, &fv, &first, &fns, &lv, &later, &lns) == 11);
 snprintf(want, sizeof(want), "result=ok mode=%s raw=0x%08x polls=%u prewrite_ns=%llu postwrite_ns=%llu first_valid=%u first=0x%08x first_ns=%llu later_valid=%u later=0x%08x later_ns=%llu\n", m, raw, polls, pre, post, fv, first, fns, lv, later, lns);
 assert(!strcmp(out, want) && !strcmp(m, "immediate") && raw == 1 && polls == 4 && fv == 1 && first == 0x40000000 && lv == 0 && later == 0 && lns == 0);
 assert(count(EV_POLL) == 5 && count(EV_SLEEP) == 3 && count(EV_P5) == 1 && count(EV_UDELAY) == 0);
 assert(ev[nev - 2].kind == EV_POLL && ev[nev - 2].irqs_off && ev[nev - 1].kind == EV_P5 && ev[nev - 1].irqs_off && !irqs_off);
 /* first_ns brackets both loads: stamp, 40 ns poll, 40 ns page-5, stamp. */
 assert(fns == 87 && pre > post && post >= 3 * 15000);
 assert(batch_show(&fake_device, &dev_attr_batch, out) == -EBUSY && count(EV_W) == 3 && count(EV_P5) == 1);
 /* Paired: first load, fixed delay, later load, all under one IRQ-off section. */
 reset("paired"); assert(!gpc_page5_kpoll_init());
 assert(gpc_state_show(&fake_device, &dev_attr_gpc_state, out) > 0 && batch_show(&fake_device, &dev_attr_batch, out) > 0); check_writes();
 assert(sscanf(out, "result=ok mode=paired raw=0x%8x polls=%u prewrite_ns=%llu postwrite_ns=%llu first_valid=%u first=0x%8x first_ns=%llu later_valid=%u later=0x%8x later_ns=%llu", &raw, &polls, &pre, &post, &fv, &first, &fns, &lv, &later, &lns) == 10);
 assert(polls == 1 && fv == 1 && lv == 1 && fns == 87 && lns == 87 + 100000 + 40 + 7 && count(EV_P5) == 2);
 assert(ev[nev - 4].kind == EV_POLL && ev[nev - 3].kind == EV_P5 && ev[nev - 2].kind == EV_UDELAY && ev[nev - 1].kind == EV_P5 && ev[nev - 1].irqs_off);
 /* Delayed: exactly one page-5 load, after the delay. */
 reset("delayed"); assert(!gpc_page5_kpoll_init());
 assert(gpc_state_show(&fake_device, &dev_attr_gpc_state, out) > 0 && batch_show(&fake_device, &dev_attr_batch, out) > 0); check_writes();
 assert(strstr(out, "mode=delayed") && strstr(out, " first_valid=0 first=0x00000000 first_ns=0 later_valid=1 later=0x40000000 later_ns=100087\n"));
 assert(count(EV_P5) == 1 && ev[nev - 3].kind == EV_POLL && ev[nev - 2].kind == EV_UDELAY && ev[nev - 1].kind == EV_P5);
 /* Busy timeout: raw value and count reported, page 5 untouched. */
 reset("paired"); assert(!gpc_page5_kpoll_init()); busy_polls = 5000;
 assert(gpc_state_show(&fake_device, &dev_attr_gpc_state, out) > 0 && batch_show(&fake_device, &dev_attr_batch, out) > 0);
 assert(!strcmp(out, "result=poll-failed mode=paired raw=0x00000011 polls=1000\n") && count(EV_POLL) == 1001 && count(EV_SLEEP) == 1000 && !count(EV_P5) && !irqs_off);
 /* Invalid final state: reported, page 5 untouched. */
 reset("immediate"); assert(!gpc_page5_kpoll_init()); busy_polls = 2; final_state = 2;
 assert(gpc_state_show(&fake_device, &dev_attr_gpc_state, out) > 0 && batch_show(&fake_device, &dev_attr_batch, out) > 0);
 assert(!strcmp(out, "result=poll-failed mode=immediate raw=0x00000002 polls=3\n") && !count(EV_P5) && !irqs_off);
 return 0;
}
'''
text = source.read_text()
# The module must never store to page 5 or name the GPU core.
assert 'writel' in text and text.count('writel(') == 3 and 'page5_regs' not in ''.join(l for l in text.splitlines() if 'writel(' in l)
assert '0x201000' not in text.replace('0x201000000)', '') and '/dev/mem' not in text.replace('through /dev/mem', '')
with tempfile.TemporaryDirectory() as td:
    root = Path(td); (root / 'linux').mkdir()
    for name in ('atomic.h', 'delay.h', 'io.h', 'irqflags.h', 'module.h', 'of.h', 'platform_device.h', 'string.h', 'timekeeping.h'):
        (root / 'linux' / name).write_text('')
    (root / 'test.c').write_text(harness)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-I', str(root), '-I', str(source.parent), str(root / 'test.c'), '-o', str(root / 'test')], check=True)
    subprocess.run([str(root / 'test')], check=True)
print('PASS: GPC order, IRQ-masked poll-to-page-5 path, modes, guards, one-shot, failed mapping, poll failures')
