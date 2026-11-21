// SPDX-License-Identifier: GPL-2.0-only
/*
 * IDENTITY variant of the breadcrumb module: after the +0x20 core read it also reads +0x18 (CORE_ID) and +0x24; squares 6 and 7 precede them, 8 is the end. Predicted CORE_ID low 16 bits 0x0803 (G4G A1 7.5.8.3).
 * TEST ONLY. BREADCRUMB + CORE READ variant (core load enabled; expected to hang on Linux): white squares are drawn on the framebuffer right before each step of the batch (see
 * fb_breadcrumb.h): 1 before the bridge stores, 2 before the GPC request, 3 before the poll, 4 poll succeeded (before the
 * page-5 sample), 5 before the core read position (the core read itself is CORE_READ below), 6-8 identity reads and batch finished (see IDENTITY note above). After a hang
 * the number of squares is the last step reached.
 *
 * TEST ONLY. CONTROL variant of the compressed module with the core-ID read DISABLED (CORE_READ 0): everything else is
 * identical (same mappings, same timing up to the page-5 sample), so a normal return localises the run-3 stall to the core read.
 *
 * TEST ONLY. "Compressed" J81 sequence: the two bridge tables, the GPC state-1
 * request, its poll, one page-5 sample and the GPU core-ID read all happen in
 * ONE kernel context with local interrupts masked, microseconds apart, the way
 * the 19H394 start path does it. The earlier Linux runs did each of these as a
 * separate step, seconds apart over USB.
 *
 * This keeps the identity of gpc-page5-kpoll (same module name, sysfs files
 * gpc_state and batch, same one-line batch result) so the existing wrapper,
 * supervisor and host capture code run unchanged. The core-ID result goes to
 * the extra sysfs file `core`, readable only if the batch survived. If the core
 * read hangs the bus, the supervisor's watchdog resets the iPad and nothing is
 * reported; the batch result is lost with it.
 *
 * Order inside batch (mirrors the iPadOS probe, which succeeds):
 *   bridge 9 table (33 stores), bridge 10 table (33 stores)
 *   GPC +0x10000 = 0xffff0000, GPC +0 = 0x40000000, GPC +0x1000 = 0x11
 *   poll GPC +0x1000 until bit 4 clears and (state & 0x1f) == 1
 *   page 5 +4 sample; if bit 30 is set -> core ID read 0x201000020
 *
 * All mappings are made at module load, before any device access. They use
 * ioremap_np() (Device-nGnRnE, non-posted), like the /dev/mem userspace tools
 * and Apple's ml_io_map, instead of the posted ioremap() of the older module.
 * Ranges (J81 only):
 *   bridges 0x201f00000 / 0x201f80000 + 0x81000   (writes, plan table)
 *   GPC     0x201e00000 + 0x11000
 *   page5   0x20e005000 + 0x1000                  (one read at +4)
 *   core    0x201000000 + 0x1000                  (reads at +0x20, +0x18, +0x24)
 */
#include <linux/atomic.h>
#include <linux/delay.h>
#include <linux/io.h>
#include <linux/irqflags.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/string.h>
#include <linux/timekeeping.h>

#include "gfx-bridge-plan.h"
#include "fb_breadcrumb.h"

#define GPC_BASE 0x201e00000ULL
#define GPC_SIZE 0x11000
#define GPC_STATE 0x1000
#define GPC_MASK 0x10000
#define PAGE5_BASE 0x20e005000ULL
#define PAGE5_SIZE 0x1000
#define PAGE5_OFFSET 4
#define CORE_BASE 0x201000000ULL
#define CORE_SIZE 0x1000
#define CORE_OFFSET 0x20
#define BRIDGE_SIZE 0x81000
/* 1: the core-ID load is ENABLED in this variant (breadcrumb 5 is drawn right before it; a hang leaves 5 squares). */
#define CORE_READ 1
#define POLL_LIMIT 1000
#define POLL_DELAY_US 10

static const u64 bridge_base[2] = { 0x201f00000ULL, 0x201f80000ULL };

/* Only the "immediate" mode exists here; the parameter stays for wrapper compatibility. */
static char *mode;
module_param(mode, charp, 0000);
static struct device *kpoll_device;
static void __iomem *gpc_regs, *page5_regs, *core_regs, *bridge_regs[2];
static atomic_t state_attempted = ATOMIC_INIT(0);
static atomic_t batch_attempted = ATOMIC_INIT(0);
static int state_known;
static u32 initial_state;

/* Filled by batch, shown by `core`. */
static struct {
	bool done, core_valid;
	u32 core, id, hi;
	const char *skipped;
	u64 bridge_ns, bridge_to_gpc_ns, poll_to_core_ns, core_read_ns;
} sample;

static ssize_t gpc_state_show(struct device *dev, struct device_attribute *attr,
			      char *buf)
{
	(void)dev;
	(void)attr;
	if (atomic_cmpxchg(&state_attempted, 0, 1))
		return -EBUSY;
	initial_state = readl(gpc_regs + GPC_STATE);
	state_known = 1;
	return sysfs_emit(buf, "address=0x%llx value=0x%08x\n",
			  GPC_BASE + GPC_STATE, initial_state);
}
static DEVICE_ATTR(gpc_state, 0400, gpc_state_show, NULL);

static ssize_t batch_show(struct device *dev, struct device_attribute *attr,
			  char *buf)
{
	u64 t_bridge0, t_bridge1, t_prewrite, t_postwrite, t_poll = 0, t_first = 0;
	u64 t_core0 = 0, t_core1 = 0;
	u32 state = 0, first = 0, core = 0, id = 0, hi = 0;
	unsigned long flags;
	unsigned int i, t;
	bool ok = false, core_done = false;

	(void)dev;
	(void)attr;
	if (atomic_cmpxchg(&batch_attempted, 0, 1))
		return -EBUSY;
	/* Same precondition the host enforced for the earlier probes. */
	if (!state_known || initial_state != 0)
		return -EINVAL;

	/* Interrupts stay masked for the whole sequence (about 1 ms at most). */
	local_irq_save(flags);
	fb_crumb_mark(1);
	t_bridge0 = ktime_get_raw_fast_ns();
	for (t = 0; t < 2; t++) {
		for (i = 0; i < 33; i++) {
			writel(bridge_plan[t][i][1], bridge_regs[t] + bridge_plan[t][i][0]);
			mb();
		}
	}
	t_bridge1 = ktime_get_raw_fast_ns();
	fb_crumb_mark(2);
	writel(0xffff0000, gpc_regs + GPC_MASK);
	mb();
	writel(0x40000000, gpc_regs);
	mb();
	t_prewrite = ktime_get_raw_fast_ns();
	writel(0x11, gpc_regs + GPC_STATE);
	mb();
	t_postwrite = ktime_get_raw_fast_ns();

	fb_crumb_mark(3);
	for (i = 0; i < POLL_LIMIT; i++) {
		t_poll = ktime_get_raw_fast_ns();
		state = readl(gpc_regs + GPC_STATE);
		if (!(state & 0x10)) {
			if ((state & 0x1f) == 1) {
				fb_crumb_mark(4);
				first = readl(page5_regs + PAGE5_OFFSET);
				t_first = ktime_get_raw_fast_ns();
				ok = true;
				fb_crumb_mark(5);
#if CORE_READ
				if (first & 0x40000000) {
					t_core0 = ktime_get_raw_fast_ns();
					core = readl(core_regs + CORE_OFFSET);
					t_core1 = ktime_get_raw_fast_ns();
					/* Identity layout reads (research/2026-11-04-j81-gpu-offline-trace.md): CORE_ID at +0x18, then +0x24. */
					fb_crumb_mark(6);
					id = readl(core_regs + 0x18);
					fb_crumb_mark(7);
					hi = readl(core_regs + 0x24);
					core_done = true;
				}
#endif
			}
			i++;
			break;
		}
		udelay(POLL_DELAY_US);
	}
	local_irq_restore(flags);
	fb_crumb_mark(8);

	sample.bridge_ns = t_bridge1 - t_bridge0;
	sample.bridge_to_gpc_ns = t_prewrite - t_bridge1;
	if (core_done) {
		sample.core_valid = true;
		sample.core = core;
		sample.id = id;
		sample.hi = hi;
		sample.poll_to_core_ns = t_core0 - t_poll;
		sample.core_read_ns = t_core1 - t_core0;
	} else {
		sample.skipped = !ok ? "poll-failed" : CORE_READ ? "page5-bit30-clear" : "core-read-disabled";
	}
	smp_store_release(&sample.done, true);

	if (!ok)
		return sysfs_emit(buf, "result=poll-failed mode=immediate raw=0x%08x polls=%u\n",
				  state, i);
	/* Same fields and format as the original module's immediate mode. */
	return sysfs_emit(buf,
			  "result=ok mode=immediate raw=0x%08x polls=%u prewrite_ns=%llu postwrite_ns=%llu first_valid=1 first=0x%08x first_ns=%llu later_valid=0 later=0x00000000 later_ns=0\n",
			  state, i, t_poll - t_prewrite, t_poll - t_postwrite, first,
			  t_first - t_poll);
}
static DEVICE_ATTR(batch, 0400, batch_show, NULL);

static ssize_t core_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	(void)dev;
	(void)attr;
	if (!smp_load_acquire(&sample.done))
		return -EAGAIN;
	if (!sample.core_valid)
		return sysfs_emit(buf, "core_valid=0 reason=%s crumb=%s\n", sample.skipped, fb_crumb_state());
	return sysfs_emit(buf,
			  "core_valid=1 core=0x%08x id=0x%08x hi=0x%08x bridge_ns=%llu bridge_to_gpc_ns=%llu poll_to_core_ns=%llu core_read_ns=%llu crumb=%s\n",
			  sample.core, sample.id, sample.hi, sample.bridge_ns, sample.bridge_to_gpc_ns,
			  sample.poll_to_core_ns, sample.core_read_ns, fb_crumb_state());
}
static DEVICE_ATTR(core, 0400, core_show, NULL);

static int __init gpc_page5_kpoll_init(void)
{
	int ret, i;

	if (PAGE_SIZE != PAGE5_SIZE || !of_machine_is_compatible("apple,j81") ||
	    !mode || strcmp(mode, "immediate"))
		return -ENODEV;
	fb_crumb_init();
	gpc_regs = ioremap_np(GPC_BASE, GPC_SIZE);
	page5_regs = ioremap_np(PAGE5_BASE, PAGE5_SIZE);
	core_regs = ioremap_np(CORE_BASE, CORE_SIZE);
	bridge_regs[0] = ioremap_np(bridge_base[0], BRIDGE_SIZE);
	bridge_regs[1] = ioremap_np(bridge_base[1], BRIDGE_SIZE);
	if (!gpc_regs || !page5_regs || !core_regs || !bridge_regs[0] || !bridge_regs[1]) {
		ret = -ENOMEM;
		goto unmap;
	}
	kpoll_device = root_device_register("j81-gpc-page5-kpoll");
	if (IS_ERR(kpoll_device)) {
		ret = PTR_ERR(kpoll_device);
		goto unmap;
	}
	ret = device_create_file(kpoll_device, &dev_attr_gpc_state);
	if (!ret)
		ret = device_create_file(kpoll_device, &dev_attr_batch);
	if (!ret)
		ret = device_create_file(kpoll_device, &dev_attr_core);
	if (ret) {
		root_device_unregister(kpoll_device);
		goto unmap;
	}
	/* No exit path: the module and its mappings stay for this boot. */
	__module_get(THIS_MODULE);
	return 0;
unmap:
	for (i = 0; i < 2; i++)
		if (bridge_regs[i])
			iounmap(bridge_regs[i]);
	if (core_regs)
		iounmap(core_regs);
	if (page5_regs)
		iounmap(page5_regs);
	if (gpc_regs)
		iounmap(gpc_regs);
	return ret;
}
module_init(gpc_page5_kpoll_init);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("One-shot J81 compressed batch with framebuffer breadcrumbs");
