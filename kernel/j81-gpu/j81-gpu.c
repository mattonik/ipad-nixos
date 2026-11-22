// SPDX-License-Identifier: GPL-2.0-only
/*
 * J81 (iPad Air 2, A8X) GPU bring-up driver, step 1: power the GPU, open its bus, read its identity. TEST ONLY.
 *
 * Everything the research runs did with userspace tools plus a one-shot module is done here, in order, each step
 * triggered separately through sysfs so a supervisor can watchdog-feed between steps:
 *
 *   precheck   reads only: dwi on (0xff), GFX off, PLL/MCC/MiscACG/TVM words at their expected Linux values
 *   pmgr       guarded stores (old value checked, readback checked): PLL1 +8 (optional), PLL4 +8, MCC bank bit 31
 *              (5 words), MiscACG, SoC TVM
 *   activate   one runtime-PM get on the GFX power domain (held until reboot)
 *   batch      66 bridge stores, GPC state 1 request + poll, page-5 sample, then the identity reads
 *              (CORE_REVISION +0x20, CORE_ID +0x18, +0x24), all in one irq-off kernel batch
 *
 * After `batch`, `peek` reads allow-listed registers of the first RGX page (step 2: read-only survey), and `meta` reads
 * allow-listed registers of the META firmware processor through its slave port (step 3a: MSLVCTRL0 address select + MSLVDATAX,
 * the sequence of the upstream PowerVR driver pvr_meta_cr_read32; bounded polls, no unbounded wait).
 *
 * Evidence: research/2026-11-22-j81-dwi-always-on-result.md (identical sequence from userspace tools),
 * research/2026-11-22-j81-ablation-a1-id-result.md (PLL1 not needed for the identity reads).
 * Requires dwi kept on (DT apple,always-on on ps_dwi, patch 0125). A hang resets the iPad via the supervisor's watchdog.
 *
 * Mappings are non-posted (ioremap_np) like Apple's and the earlier modules, all made at load before any access.
 */
#include <linux/atomic.h>
#include <linux/delay.h>
#include <linux/device.h>
#include <linux/io.h>
#include <linux/irqflags.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/pm_domain.h>
#include <linux/pm_runtime.h>
#include <linux/string.h>
#include <linux/timekeeping.h>

#include "gfx-bridge-plan.h"
#include "fb_breadcrumb.h"

#define GFX_NODE "/soc/power-management@20e000000/power-controller@20320"
#define PMGR_BASE 0x20e000000ULL
#define PMGR_SIZE 0x40000
#define GPC_BASE 0x201e00000ULL
#define GPC_SIZE 0x11000
#define GPC_STATE 0x1000
#define GPC_MASK 0x10000
#define CORE_BASE 0x201000000ULL
#define CORE_SIZE 0x1000
#define BRIDGE_SIZE 0x81000
#define POLL_LIMIT 1000
#define POLL_DELAY_US 10

/* PMGR word offsets (from 0x20e000000). */
#define PM_PLL1 0x1008
#define PM_PLL4 0x4008
#define PM_PAGE5_4 0x5004
#define PM_DWI 0x20120
#define PM_GFX_PS 0x20320
#define PM_VM 0x23000
#define PM_GFX_VID 0x2300c
#define PM_TVM 0x2d000
#define PM_TVM_STATUS 0x2d100
#define PM_MISCACG 0x32000

static const struct { u32 off, old; } mcc_words[5] = {
	{ 0x22000, 0x00000000 }, { 0x22090, 0x09070300 }, { 0x220a0, 0x09040300 },
	{ 0x220b0, 0x09060300 }, { 0x22130, 0x09040300 },
};
#define MCC_BANK_BIT BIT(31)
#define MCC_CMP_MASK 0xbfffffffU /* bit 30 may change by itself */

static const u64 bridge_base[2] = { 0x201f00000ULL, 0x201f80000ULL };

/* Registers `peek` may read: first page of the RGX core (offsets from CORE_BASE), names from the upstream PowerVR headers. */
static const struct { u32 off; const char *name; } peek_list[] = {
	{ 0x0000, "CLK_CTRL_lo" }, { 0x0004, "CLK_CTRL_hi" }, { 0x0008, "CLK_STATUS_lo" }, { 0x000c, "CLK_STATUS_hi" },
	{ 0x0018, "CORE_ID" }, { 0x0020, "CORE_REVISION" }, { 0x0028, "DESIGNER_REV_FIELD1" },
	{ 0x0030, "DESIGNER_REV_FIELD2" }, { 0x0040, "CHANGESET_NUMBER" },
	{ 0x0100, "SOFT_RESET_lo" }, { 0x0104, "SOFT_RESET_hi" }, { 0x0130, "EVENT_STATUS_lo" },
	{ 0x0160, "TIMER_lo" }, { 0x03c8, "SIDEKICK_IDLE_lo" }, { 0x08f8, "MARS_IDLE_lo" },
	{ 0x0a10, "META_SP_MSLVCTRL0" }, { 0x0a18, "META_SP_MSLVCTRL1" },
};

/* META register addresses `meta` may read (META address space; names from the upstream PowerVR headers). */
static const struct { u32 addr; const char *name; } meta_list[] = {
	{ 0x04831000, "META_CORE_ID" }, { 0x04800000, "T0ENABLE" }, { 0x04800010, "T0STATUS" },
	{ 0x04801000, "T1ENABLE" }, { 0x04801010, "T1STATUS" }, { 0x048000b0, "TXCLKCTRL" },
	{ 0x048000e8, "T0PRIVEXT" }, { 0x04830030, "SYSC_JTAG_THREAD" }, { 0x04830018, "MMCU_DCACHE_CTRL" },
	{ 0x04830020, "MMCU_ICACHE_CTRL" }, { 0x04850000, "MMCU_SEG0_BASE" }, { 0x04850004, "MMCU_SEG0_LIMIT" },
};
#define MSLVCTRL0 0x0a10
#define MSLVCTRL1 0x0a18
#define MSLVDATAX 0x0a00
#define MSLV_READY_IDLE 0x05000000U /* READY (24) | GBLPORT_IDLE (26) */

static char *mode_unused;
module_param_named(mode, mode_unused, charp, 0000);
static int skip_pll1;
module_param(skip_pll1, int, 0000);
static int skip_pll4;
module_param(skip_pll4, int, 0000);

enum { ST_NEW, ST_PRECHECKED, ST_PMGR_DONE, ST_ACTIVE, ST_IDENTIFIED, ST_FAILED };
static const char * const st_name[] = { "new", "prechecked", "pmgr-done", "active", "identified", "failed" };

static struct device *consumer;
static void __iomem *pmgr, *gpc_regs, *core_regs, *bridge_regs[2];
static DEFINE_MUTEX(lock);
static int state;
static char reason[96] = "-";
static struct {
	u32 core, id, hi, gpc_raw, page5, vid, gfx_ps;
	u64 bridge_ns, bridge_to_gpc_ns, poll_to_core_ns, core_read_ns;
	unsigned int polls;
	bool batch_done;
} res;
static u32 peek_off, peek_val;
static bool peek_valid;
static u32 meta_addr, meta_val, meta_ctrl1;
static bool meta_valid;
static atomic_t batch_attempted = ATOMIC_INIT(0), activate_attempted = ATOMIC_INIT(0), pmgr_attempted = ATOMIC_INIT(0);

static int fail(int err, const char *msg)
{
	strscpy(reason, msg, sizeof(reason));
	state = ST_FAILED;
	return err;
}

#define PR(off) readl(pmgr + (off))

static int store_check(u32 off, u32 old, u32 val, u32 cmp_mask)
{
	u32 cur = PR(off);

	if (cur != old)
		return -EBUSY;
	writel(val, pmgr + off);
	mb();
	usleep_range(500, 1500);
	cur = PR(off);
	return (cur & cmp_mask) == (val & cmp_mask) ? 0 : -EIO;
}

static int step_precheck(void)
{
	unsigned int i;

	if (state != ST_NEW)
		return -EBUSY;
	if (PR(PM_DWI) != 0xff)
		return fail(-ENODEV, "dwi-not-on");
	if (PR(PM_GFX_PS) != 0x300)
		return fail(-EBUSY, "gfx-not-off");
	if (PR(PM_PLL1) != 0x80480348 || PR(PM_PLL4) != 0x88480348)
		return fail(-EBUSY, "pll-words-unexpected");
	for (i = 0; i < 5; i++)
		if (PR(mcc_words[i].off) != mcc_words[i].old)
			return fail(-EBUSY, "mcc-words-unexpected");
	if (PR(PM_MISCACG) != 0 || PR(PM_TVM) != 0 || (PR(PM_VM) & 0xf00))
		return fail(-EBUSY, "miscacg-tvm-vm-unexpected");
	state = ST_PRECHECKED;
	strscpy(reason, "-", sizeof(reason));
	return 0;
}

static int step_pmgr(void)
{
	unsigned int i, t;
	int err;

	if (state != ST_PRECHECKED)
		return -EBUSY;
	if (atomic_cmpxchg(&pmgr_attempted, 0, 1))
		return -EBUSY;
	if (!skip_pll1 && (err = store_check(PM_PLL1, 0x80480348, 0x40480348, ~0U)))
		return fail(err, "pll1-store");
	if (!skip_pll4 && (err = store_check(PM_PLL4, 0x88480348, 0x48480348, ~0U)))
		return fail(err, "pll4-store");
	for (i = 0; i < 5; i++)
		if ((err = store_check(mcc_words[i].off, mcc_words[i].old, mcc_words[i].old | MCC_BANK_BIT, MCC_CMP_MASK)))
			return fail(err, "mcc-store");
	if ((err = store_check(PM_MISCACG, 0, 1, ~0U)))
		return fail(err, "miscacg-store");
	if ((err = store_check(PM_TVM, 0, 1, ~0U)))
		return fail(err, "tvm-store");
	for (t = 0; t < 100 && PR(PM_TVM_STATUS) != 1; t++)
		udelay(10);
	if (PR(PM_TVM_STATUS) != 1)
		return fail(-EIO, "tvm-status");
	if (PR(PM_DWI) != 0xff)
		return fail(-ENODEV, "dwi-lost");
	state = ST_PMGR_DONE;
	return 0;
}

static int step_activate(void)
{
	int ret;

	if (state != ST_PMGR_DONE)
		return -EBUSY;
	if (atomic_cmpxchg(&activate_attempted, 0, 1))
		return -EBUSY;
	ret = pm_runtime_get_sync(consumer);
	if (ret < 0)
		return fail(ret, "runtime-get");
	res.gfx_ps = PR(PM_GFX_PS);
	res.vid = PR(PM_GFX_VID);
	if (res.gfx_ps != 0x3ff)
		return fail(-EIO, "gfx-ps-not-active");
	state = ST_ACTIVE;
	return 0;
}

static int step_batch(void)
{
	u64 t_bridge0, t_bridge1, t_prewrite, t_poll = 0, t_core0, t_core1;
	u32 st = 0, first = 0, core, id, hi;
	unsigned long flags;
	unsigned int i, t;
	bool ok = false;

	if (state != ST_ACTIVE)
		return -EBUSY;
	if (atomic_cmpxchg(&batch_attempted, 0, 1))
		return -EBUSY;
	if (readl(gpc_regs + GPC_STATE) != 0)
		return fail(-EBUSY, "gpc-state-not-zero");

	local_irq_save(flags);
	fb_crumb_mark(1);
	t_bridge0 = ktime_get_raw_fast_ns();
	for (t = 0; t < 2; t++)
		for (i = 0; i < 33; i++) {
			writel(bridge_plan[t][i][1], bridge_regs[t] + bridge_plan[t][i][0]);
			mb();
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
	fb_crumb_mark(3);
	for (i = 0; i < POLL_LIMIT; i++) {
		t_poll = ktime_get_raw_fast_ns();
		st = readl(gpc_regs + GPC_STATE);
		if (!(st & 0x10)) {
			if ((st & 0x1f) == 1) {
				fb_crumb_mark(4);
				first = readl(pmgr + PM_PAGE5_4);
				ok = true;
			}
			i++;
			break;
		}
		udelay(POLL_DELAY_US);
	}
	res.gpc_raw = st;
	res.polls = i;
	res.page5 = first;
	if (!ok || !(first & 0x40000000)) {
		local_irq_restore(flags);
		return fail(-EIO, ok ? "page5-bit30-clear" : "gpc-poll-failed");
	}
	fb_crumb_mark(5);
	t_core0 = ktime_get_raw_fast_ns();
	core = readl(core_regs + 0x20);
	t_core1 = ktime_get_raw_fast_ns();
	fb_crumb_mark(6);
	id = readl(core_regs + 0x18);
	fb_crumb_mark(7);
	hi = readl(core_regs + 0x24);
	fb_crumb_mark(8);
	local_irq_restore(flags);

	res.core = core; res.id = id; res.hi = hi;
	res.bridge_ns = t_bridge1 - t_bridge0;
	res.bridge_to_gpc_ns = t_prewrite - t_bridge1;
	res.poll_to_core_ns = t_core0 - t_poll;
	res.core_read_ns = t_core1 - t_core0;
	res.batch_done = true;
	state = ST_IDENTIFIED;
	return 0;
}

static ssize_t step_store(struct device *dev, struct device_attribute *attr, const char *buf, size_t count)
{
	int ret;

	mutex_lock(&lock);
	if (sysfs_streq(buf, "precheck"))
		ret = step_precheck();
	else if (sysfs_streq(buf, "pmgr"))
		ret = step_pmgr();
	else if (sysfs_streq(buf, "activate"))
		ret = step_activate();
	else if (sysfs_streq(buf, "batch"))
		ret = step_batch();
	else
		ret = -EINVAL;
	mutex_unlock(&lock);
	return ret ? ret : count;
}
static DEVICE_ATTR_WO(step);

static ssize_t status_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	ssize_t n;

	mutex_lock(&lock);
	n = sysfs_emit(buf, "state=%s reason=%s skip_pll1=%d skip_pll4=%d crumb=%s", st_name[state], reason, skip_pll1, skip_pll4, fb_crumb_state());
	if (state >= ST_ACTIVE)
		n += sysfs_emit_at(buf, n, " gfx_ps=0x%08x gfx_vid=0x%08x", res.gfx_ps, res.vid);
	if (res.batch_done)
		n += sysfs_emit_at(buf, n,
				   " core=0x%08x id=0x%08x hi=0x%08x bvnc_rev=%u.%u.%u.%u gpc=0x%08x polls=%u page5=0x%08x bridge_ns=%llu poll_to_core_ns=%llu core_read_ns=%llu",
				   res.core, res.id, res.hi, (res.core >> 24) & 0xff, (res.core >> 16) & 0xff,
				   (res.core >> 8) & 0xff, res.core & 0xff, res.gpc_raw, res.polls, res.page5,
				   res.bridge_ns, res.poll_to_core_ns, res.core_read_ns);
	n += sysfs_emit_at(buf, n, "\n");
	mutex_unlock(&lock);
	return n;
}
static DEVICE_ATTR_RO(status);

/* peek: write an allow-listed offset, read the value back. One register per write so a supervisor sees where a hang happens. */
static ssize_t peek_store(struct device *dev, struct device_attribute *attr, const char *buf, size_t count)
{
	unsigned int i;
	u32 off;
	int ret = -EINVAL;

	if (kstrtou32(buf, 0, &off))
		return -EINVAL;
	mutex_lock(&lock);
	if (state != ST_IDENTIFIED) {
		ret = -EBUSY;
		goto out;
	}
	for (i = 0; i < ARRAY_SIZE(peek_list); i++)
		if (peek_list[i].off == off) {
			peek_off = off;
			peek_val = readl(core_regs + off);
			peek_valid = true;
			ret = count;
			break;
		}
out:
	mutex_unlock(&lock);
	return ret;
}

static ssize_t peek_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	unsigned int i;
	const char *name = "?";
	ssize_t n;

	mutex_lock(&lock);
	if (!peek_valid) {
		n = sysfs_emit(buf, "no-peek\n");
	} else {
		for (i = 0; i < ARRAY_SIZE(peek_list); i++)
			if (peek_list[i].off == peek_off)
				name = peek_list[i].name;
		n = sysfs_emit(buf, "offset=0x%04x name=%s value=0x%08x\n", peek_off, name, peek_val);
	}
	mutex_unlock(&lock);
	return n;
}
static DEVICE_ATTR_RW(peek);

static int meta_wait_ready(u32 *ctrl1)
{
	unsigned int i;

	for (i = 0; i < 1000; i++) {
		*ctrl1 = readl(core_regs + MSLVCTRL1);
		if ((*ctrl1 & MSLV_READY_IDLE) == MSLV_READY_IDLE)
			return 0;
		udelay(1);
	}
	return -ETIMEDOUT;
}

/* meta: write an allow-listed META address (hex), read the value back. Slave-port read sequence, bounded waits. */
static ssize_t meta_store(struct device *dev, struct device_attribute *attr, const char *buf, size_t count)
{
	unsigned int i;
	u32 addr, c1;
	int ret = -EINVAL;

	if (kstrtou32(buf, 0, &addr))
		return -EINVAL;
	mutex_lock(&lock);
	if (state != ST_IDENTIFIED) {
		ret = -EBUSY;
		goto out;
	}
	for (i = 0; i < ARRAY_SIZE(meta_list); i++)
		if (meta_list[i].addr == addr)
			break;
	/* Also the first 64 words of the coremem code (0x80000000) and data (0x82000000) windows, read-only, word aligned. */
	if (i == ARRAY_SIZE(meta_list) &&
	    !(!(addr & 3) && ((addr - 0x80000000U) < 0x100 || (addr - 0x82000000U) < 0x100)))
		goto out;
	ret = meta_wait_ready(&c1);
	if (ret)
		goto out;
	writel(addr | 1U, core_regs + MSLVCTRL0); /* address select + RD_EN */
	mb();
	(void)readl(core_regs + MSLVCTRL0);
	ret = meta_wait_ready(&c1);
	if (ret)
		goto out;
	meta_addr = addr;
	meta_ctrl1 = c1;
	meta_val = readl(core_regs + MSLVDATAX);
	meta_valid = true;
	ret = count;
out:
	mutex_unlock(&lock);
	return ret;
}

static ssize_t meta_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	unsigned int i;
	const char *name = "?";
	ssize_t n;

	mutex_lock(&lock);
	if (!meta_valid) {
		n = sysfs_emit(buf, "no-meta-read\n");
	} else {
		for (i = 0; i < ARRAY_SIZE(meta_list); i++)
			if (meta_list[i].addr == meta_addr)
				name = meta_list[i].name;
		if (!strcmp(name, "?"))
			name = (meta_addr - 0x80000000U) < 0x100 ? "coremem_code" : "coremem_data";
		n = sysfs_emit(buf, "addr=0x%08x name=%s value=0x%08x mslvctrl1=0x%08x\n", meta_addr, name, meta_val, meta_ctrl1);
	}
	mutex_unlock(&lock);
	return n;
}
static DEVICE_ATTR_RW(meta);

static int __init j81_gpu_init(void)
{
	struct device_node *gfx;
	struct of_phandle_args domain = { .args_count = 0 };
	struct platform_device *provider;
	bool bound;
	u32 cells;
	int ret = -ENODEV, i;

	if (PAGE_SIZE != 0x1000 || !of_machine_is_compatible("apple,j81"))
		return -ENODEV;
	gfx = of_find_node_by_path(GFX_NODE);
	if (!gfx)
		return -ENODEV;
	if (!of_device_is_available(gfx) || !of_device_is_compatible(gfx, "apple,t7000-pmgr-pwrstate") ||
	    of_property_read_bool(gfx, "power-domains") ||
	    of_property_read_u32(gfx, "#power-domain-cells", &cells) || cells)
		goto out_node;
	provider = of_find_device_by_node(gfx);
	if (!provider)
		goto out_node;
	device_lock(&provider->dev);
	bound = device_is_bound(&provider->dev);
	device_unlock(&provider->dev);
	put_device(&provider->dev);
	if (!bound)
		goto out_node;

	pmgr = ioremap_np(PMGR_BASE, PMGR_SIZE);
	gpc_regs = ioremap_np(GPC_BASE, GPC_SIZE);
	core_regs = ioremap_np(CORE_BASE, CORE_SIZE);
	bridge_regs[0] = ioremap_np(bridge_base[0], BRIDGE_SIZE);
	bridge_regs[1] = ioremap_np(bridge_base[1], BRIDGE_SIZE);
	if (!pmgr || !gpc_regs || !core_regs || !bridge_regs[0] || !bridge_regs[1]) {
		ret = -ENOMEM;
		goto unmap;
	}
	fb_crumb_init();
	consumer = root_device_register("j81-gpu");
	if (IS_ERR(consumer)) {
		ret = PTR_ERR(consumer);
		goto unmap;
	}
	ret = device_create_file(consumer, &dev_attr_step);
	if (!ret)
		ret = device_create_file(consumer, &dev_attr_status);
	if (!ret)
		ret = device_create_file(consumer, &dev_attr_peek);
	if (!ret)
		ret = device_create_file(consumer, &dev_attr_meta);
	if (!ret)
		ret = pm_runtime_set_suspended(consumer);
	if (ret)
		goto out_dev;
	domain.np = gfx;
	ret = of_genpd_add_device(&domain, consumer);
	if (ret)
		goto out_dev;
	pm_runtime_enable(consumer);
	of_node_put(gfx);
	/* No exit path: mappings and the final runtime-PM reference stay until reboot. */
	__module_get(THIS_MODULE);
	return 0;
out_dev:
	root_device_unregister(consumer);
unmap:
	for (i = 0; i < 2; i++)
		if (bridge_regs[i])
			iounmap(bridge_regs[i]);
	if (core_regs)
		iounmap(core_regs);
	if (gpc_regs)
		iounmap(gpc_regs);
	if (pmgr)
		iounmap(pmgr);
out_node:
	of_node_put(gfx);
	return ret;
}
module_init(j81_gpu_init);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("J81 GPU bring-up step 1: power, bus, identity");
