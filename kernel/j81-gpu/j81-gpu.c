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
#define CORE_SIZE 0x4000
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
	/* Post-research reads (packet 5/7 result): stock boot registers; read-only. */
	{ 0x0ac8, "META_SP_MSLVIRQSTATUS" }, { 0x0bf8, "META_BOOT_lo" }, { 0x0bfc, "META_BOOT_hi" },
	{ 0x1200, "BIF_CAT_BASE0_lo" }, { 0x1204, "BIF_CAT_BASE0_hi" }, { 0x1288, "BIF_FAULT_1288" },
	{ 0x1290, "BIF_IRQ_1290" }, { 0x12a8, "BIF_CTRL" }, { 0x12b0, "BIF_FAULT_STATUS_12b0" },
	{ 0x1340, "REG_1340" },
	{ 0x3800, "SLC_CTRL_MISC_lo" }, { 0x3804, "SLC_CTRL_MISC_hi" }, { 0x3808, "SLC_REG_3808" },
	{ 0x3898, "SLC_IDLE" },
};

/* META register addresses `meta` may read (META address space; names from the upstream PowerVR headers). */
static const struct { u32 addr; const char *name; } meta_list[] = {
	{ 0x04831000, "META_CORE_ID" }, { 0x04800000, "T0ENABLE" }, { 0x04800010, "T0STATUS" },
	{ 0x04801000, "T1ENABLE" }, { 0x04801010, "T1STATUS" }, { 0x048000b0, "TXCLKCTRL" },
	{ 0x048000e8, "T0PRIVEXT" }, { 0x04830030, "SYSC_JTAG_THREAD" }, { 0x04830018, "MMCU_DCACHE_CTRL" },
	{ 0x04830020, "MMCU_ICACHE_CTRL" }, { 0x04850000, "MMCU_SEG0_BASE" }, { 0x04850004, "MMCU_SEG0_LIMIT" },
	{ 0x04850008, "MMCU_SEG0_OUTA0" }, { 0x0485000c, "MMCU_SEG0_OUTA1" },
	{ 0x04850010, "MMCU_SEG1_BASE" }, { 0x04850014, "MMCU_SEG1_LIMIT" }, { 0x04850018, "MMCU_SEG1_OUTA0" },
	{ 0x0485001c, "MMCU_SEG1_OUTA1" }, { 0x04850020, "MMCU_SEG2_BASE" }, { 0x04850024, "MMCU_SEG2_LIMIT" },
	{ 0x04850028, "MMCU_SEG2_OUTA0" }, { 0x0485002c, "MMCU_SEG2_OUTA1" }, { 0x04850030, "MMCU_SEG3_BASE" },
	{ 0x04850034, "MMCU_SEG3_LIMIT" }, { 0x04850038, "MMCU_SEG3_OUTA0" }, { 0x0485003c, "MMCU_SEG3_OUTA1" },
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
static struct { bool w1_done, w2a_done; u32 w1_before, w1_after; u64 w2a_set, w2a_clear; u32 w2a_core; } wr;
static atomic_t w1_attempted = ATOMIC_INIT(0), w2a_attempted = ATOMIC_INIT(0);
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

/*
 * W1: first GPU register write. META_BOOT (0xbf8, 64-bit; low word) is rewritten with the value just read (expected 0), then
 * read back. Tests that a direct RGX store does not fault; it cannot show that a store changes state (same value).
 */
static int step_w1(void)
{
	u32 before, after;

	if (state != ST_IDENTIFIED)
		return -EBUSY;
	if (atomic_cmpxchg(&w1_attempted, 0, 1))
		return -EBUSY;
	before = readl(core_regs + 0xbf8);
	if (before != 0 || readl(core_regs + 0xbfc) != 0)
		return fail(-EBUSY, "w1-meta-boot-not-zero");
	writel(before, core_regs + 0xbf8);
	mb();
	after = readl(core_regs + 0xbf8);
	wr.w1_before = before;
	wr.w1_after = after;
	wr.w1_done = true;
	if (after != before)
		return fail(-EIO, "w1-readback-differs");
	return 0;
}

/*
 * W2a: first stage of the stock SOFT_RESET staging (research packet 5/7): 64-bit store 0x00e7fffffffffc1d to SOFT_RESET (0x100),
 * read it back, then store 0 and read back again, and re-read CORE_REVISION. Stock does the same writes on J81 (through the
 * Fender mailbox when its global bit is set, which is unresolved: a readback that is not the value written means direct
 * stores do not land). Interrupts are off for the whole window; only SOFT_RESET itself is read while blocks are in reset.
 */
static int step_w2a(void)
{
	unsigned long flags;
	u64 set, clear;
	u32 core;

	if (state != ST_IDENTIFIED || !wr.w1_done)
		return -EBUSY;
	if (atomic_cmpxchg(&w2a_attempted, 0, 1))
		return -EBUSY;
	if (readl(core_regs + 0x100) != 0 || readl(core_regs + 0x104) != 0)
		return fail(-EBUSY, "w2a-soft-reset-not-zero");
	local_irq_save(flags);
	writeq(0x00e7fffffffffc1dULL, core_regs + 0x100);
	mb();
	set = readq(core_regs + 0x100);
	writeq(0, core_regs + 0x100);
	mb();
	clear = readq(core_regs + 0x100);
	core = readl(core_regs + 0x20);
	local_irq_restore(flags);
	wr.w2a_set = set;
	wr.w2a_clear = clear;
	wr.w2a_core = core;
	wr.w2a_done = true;
	if (clear != 0 || core != res.core)
		return fail(-EIO, "w2a-unwind-mismatch");
	return 0;
}

/*
 * F1/F2 (research packet 8, T3/T5): Fender ConfigRAM replay proof. Stock cycles the GPC state 1 -> 0 -> 1; ConfigRAM (words at
 * GPC +0x10000, terminated by 0xffff0000) is replayed into RGX at the 0 -> 1 transition. F1 cycles with an empty list and
 * re-reads the identity. F2 cycles with two SLC writes (0x3800 <- 0x0003550000300001, 0x3808 <- 1) and reads them back: R1 saw
 * 0x00320001 / 0x00035500 / 0, a replay would show 0x00300001 / 0x00035500 / 1. Only SLC_CTRL_MISC is touched; META stays held.
 */
/* Bounded poll of GPC_STATE bit 4 (busy); 10 us steps, 2 s bound (stock allows 30 s; the host watchdog is 20 s). */
static int gpc_wait_idle(void)
{
	int i;

	for (i = 0; i < 200000; i++) {
		if (!(readl(gpc_regs + GPC_STATE) & 0x10))
			return 0;
		udelay(10);
	}
	return -ETIMEDOUT;
}

/* Blank the breadcrumb row so F-step marks 1..5 are not confused with the batch step's earlier marks 1..8. */
static void fb_crumb_clear(void)
{
	u32 x, y, x1 = CRUMB_GAP + CRUMB_MAX * (CRUMB_SQ + CRUMB_GAP), y0;

	if (!fb_crumb_dev.ok)
		return;
	y0 = fb_crumb_dev.height - CRUMB_SQ - CRUMB_GAP;
	for (y = 0; y < CRUMB_SQ; y++)
		for (x = 0; x < x1; x++)
			__raw_writel(0, fb_crumb_dev.base + (u64)(y0 + y) * fb_crumb_dev.stride + x * 4);
	wmb();
}

static u32 cfg_n;

static void cfg_put(u32 w)
{
	writel(w, gpc_regs + GPC_MASK + 4 * cfg_n++);
}

static void cfg_put64(u32 reg, u64 v)
{
	cfg_put((reg + 4) | 0xff << 16);
	cfg_put(v >> 32);
	cfg_put(reg | 0xff << 16);
	cfg_put(v & 0xffffffff);
}

static struct { bool done; u32 core, s0, s4, s8; u32 g_start, g_after0, g_after20000, g_after1, p5; int err; const char *where; bool rgx_read; } fr[3];
static atomic_t f_attempted[3] = { ATOMIC_INIT(0), ATOMIC_INIT(0), ATOMIC_INIT(0) };

/*
 * F-steps, Apple's order (research packet 9, T3 rows 15/16/10/11, from Orchard's A8 driver and our 19H394 trace). Both earlier
 * runs hung F1 right after the state-0 request; the old F1 wrote ConfigRAM and +0x20000 immediately after the busy bit cleared,
 * skipping Apple's 100 ms wait, the +0x10 cycle and the +0 = 0x40000000 store.
 *   which 2 = f1a: ONLY state 0 -> poll -> 100 ms -> state 1 -> poll (no other Fender write): isolates the state transition.
 *   which 0 = f1 : state 0, 100 ms, +0x10 read/0/read, +0 = 0x40000000, ConfigRAM (empty), barrier, 100 ms, +0x20000 = 0, state 1.
 *   which 1 = f2 : as f1 with the two-entry ConfigRAM list.
 * RGX is read only when GPC_STATE == 1 (busy clear) AND PMGR +0x5004 bit 30 (PLL lock) is set. Sleeps run with interrupts on.
 * Crumbs (row cleared first): 1 before state-0 request, 2 state 0 reached (+100 ms done), 3 pre-release writes done, 4 state-1
 * request written, 5 state 1 verified.
 */
static int step_f(int which)
{
	int ret = 0;
	u32 g, v;

	if (state != ST_IDENTIFIED || !wr.w2a_done || (which == 1 && !fr[0].done))
		return -EBUSY;
	if (atomic_cmpxchg(&f_attempted[which], 0, 1))
		return -EBUSY;
	g = readl(gpc_regs + GPC_STATE);
	fr[which].g_start = g;
	if ((g & 0x1f) != 0x01)
		return fail(-EBUSY, "f-gpc-not-state-1");
	fb_crumb_clear();
	fb_crumb_mark(1);
	writel(0x10, gpc_regs + GPC_STATE);
	msleep(100);	/* g-run 2026-11-22: a read right after the 1 -> 0 store hung the bus; with a delay it is safe */
	ret = gpc_wait_idle();
	fr[which].g_after0 = readl(gpc_regs + GPC_STATE);
	if (ret || (fr[which].g_after0 & 0x1f) != 0x00) {
		fr[which].where = "state0-request";
		ret = ret ? ret : -EIO;
		goto recover;
	}
	msleep(100);
	fb_crumb_mark(2);
	if (which != 2) {
		v = readl(gpc_regs + 0x10);
		writel(0, gpc_regs + 0x10);
		v = readl(gpc_regs + 0x10);
		if (v) {
			fr[which].where = "int-enable-not-zero";
			ret = -EIO;
			goto recover;
		}
		writel(0x40000000, gpc_regs);
		cfg_n = 0;
		if (which == 1) {
			cfg_put64(0x3800, 0x0003550000300001ULL);
			cfg_put(0x3808 | 0xff << 16);
			cfg_put(1);
		}
		cfg_put(0xffff0000);
		wmb();
		msleep(100);
		writel(0, gpc_regs + 0x20000);
		msleep(10);
		ret = gpc_wait_idle();
		fr[which].g_after20000 = readl(gpc_regs + GPC_STATE);
		if (ret) {
			fr[which].where = "after-20000-write";
			goto recover;
		}
	}
	fb_crumb_mark(3);
	writel(0x11, gpc_regs + GPC_STATE);
	fb_crumb_mark(4);
	msleep(10);
	ret = gpc_wait_idle();
	g = readl(gpc_regs + GPC_STATE);
	fr[which].g_after1 = g;
	if (ret || (g & 0x1f) != 0x01) {
		fr[which].where = "state1-request";
		ret = ret ? ret : -EIO;
		goto out;
	}
	udelay(20);
	fr[which].p5 = readl(pmgr + PM_PAGE5_4);
	if (!(fr[which].p5 & 0x40000000)) {
		fr[which].where = "pll-lock-clear";
		ret = -EIO;
		goto out;
	}
	fb_crumb_mark(5);
	fr[which].s0 = readl(core_regs + 0x3800);
	fr[which].s4 = readl(core_regs + 0x3804);
	fr[which].s8 = readl(core_regs + 0x3808);
	fr[which].core = readl(core_regs + 0x20);
	fr[which].rgx_read = true;
	goto out;
recover:
	/* one attempt back to state 1, GPC_STATE only */
	writel(0x11, gpc_regs + GPC_STATE);
	msleep(100);
	gpc_wait_idle();
	fr[which].g_after1 = readl(gpc_regs + GPC_STATE);
out:
	fr[which].err = ret;
	fr[which].done = true;
	if (ret)
		return fail(ret, fr[which].where ? fr[which].where : "f-error");
	if (fr[which].core != res.core)
		return fail(-EIO, "f-core-mismatch");
	return 0;
}

/*
 * G-steps (after three F1 hangs at the 1 -> 0 transition): ONE primitive per host-visible stage so the last stage line names it.
 *   g0  write GPC +0x1000 = 0x10 and NOTHING else (no read afterwards, non-posted store)
 *   g1  one single read of GPC +0x1000
 *   g2  bounded poll (2 s) for busy clear, reads only GPC +0x1000
 *   g3  100 ms sleep, then write +0x1000 = 0x11 and nothing else
 *   g4  bounded poll for busy clear, state must be 1, then PMGR +0x5004 bit 30 must be set (no RGX read in any g-step)
 * Order enforced: g0 -> g1 -> g2 -> g3 -> g4, each once, from state 1 after W2a.
 */
static struct { int next; u32 r1, polls_state, p5; int perr; } gs;

static int step_g(int n)
{
	int i, ret;
	u32 v;

	if (state != ST_IDENTIFIED || !wr.w2a_done || gs.next != n)
		return -EBUSY;
	gs.next = n + 1;
	switch (n) {
	case 0:
		if ((readl(gpc_regs + GPC_STATE) & 0x1f) != 0x01)
			return fail(-EBUSY, "g-gpc-not-state-1");
		writel(0x10, gpc_regs + GPC_STATE);
		return 0;
	case 1:
		gs.r1 = readl(gpc_regs + GPC_STATE);
		return 0;
	case 2:
		for (i = 0; i < 200000; i++) {
			v = readl(gpc_regs + GPC_STATE);
			if (!(v & 0x10))
				break;
			udelay(10);
		}
		gs.polls_state = v;
		gs.perr = i == 200000 ? -ETIMEDOUT : 0;
		return gs.perr ? fail(gs.perr, "g2-poll-timeout") : 0;
	case 3:
		msleep(100);
		writel(0x11, gpc_regs + GPC_STATE);
		return 0;
	case 4:
		ret = gpc_wait_idle();
		v = readl(gpc_regs + GPC_STATE);
		gs.polls_state = v;
		if (ret || (v & 0x1f) != 0x01)
			return fail(ret ? ret : -EIO, "g4-state1-not-reached");
		udelay(20);
		gs.p5 = readl(pmgr + PM_PAGE5_4);
		if (!(gs.p5 & 0x40000000))
			return fail(-EIO, "g4-pll-lock-clear");
		return 0;
	}
	return -EINVAL;
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
	else if (sysfs_streq(buf, "w1"))
		ret = step_w1();
	else if (sysfs_streq(buf, "w2a"))
		ret = step_w2a();
	else if (sysfs_streq(buf, "g0"))
		ret = step_g(0);
	else if (sysfs_streq(buf, "g1"))
		ret = step_g(1);
	else if (sysfs_streq(buf, "g2"))
		ret = step_g(2);
	else if (sysfs_streq(buf, "g3"))
		ret = step_g(3);
	else if (sysfs_streq(buf, "g4"))
		ret = step_g(4);
	else if (sysfs_streq(buf, "f1a"))
		ret = step_f(2);
	else if (sysfs_streq(buf, "f1"))
		ret = step_f(0);
	else if (sysfs_streq(buf, "f2"))
		ret = step_f(1);
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
	if (wr.w1_done)
		n += sysfs_emit_at(buf, n, " w1_before=0x%08x w1_after=0x%08x", wr.w1_before, wr.w1_after);
	if (gs.next)
		n += sysfs_emit_at(buf, n, " g_next=%d g_r1=0x%08x g_poll_state=0x%08x g_perr=%d g_p5=0x%08x", gs.next, gs.r1, gs.polls_state, gs.perr, gs.p5);
	{
		static const char *const fn[3] = { "f1", "f2", "f1a" };
		int k;

		for (k = 0; k < 3; k++)
			if (fr[k].done)
				n += sysfs_emit_at(buf, n, " %s_err=%d %s_where=%s %s_gpc=0x%08x/0x%08x/0x%08x/0x%08x %s_p5=0x%08x %s_rgx_read=%d %s_core=0x%08x %s_slc=0x%08x/0x%08x/0x%08x",
						   fn[k], fr[k].err, fn[k], fr[k].where ? fr[k].where : "-", fn[k], fr[k].g_start, fr[k].g_after0,
						   fr[k].g_after20000, fr[k].g_after1, fn[k], fr[k].p5, fn[k], fr[k].rgx_read, fn[k], fr[k].core, fn[k], fr[k].s0, fr[k].s4, fr[k].s8);
	}
	if (wr.w2a_done)
		n += sysfs_emit_at(buf, n, " w2a_set=0x%016llx w2a_clear=0x%016llx w2a_core=0x%08x", wr.w2a_set, wr.w2a_clear, wr.w2a_core);
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
