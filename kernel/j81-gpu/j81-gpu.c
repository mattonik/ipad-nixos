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
#include <linux/dma-mapping.h>
#include <linux/device.h>
#include <linux/io.h>
#include <linux/irqflags.h>
#include <linux/mm.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/pm_domain.h>
#include <linux/pm_runtime.h>
#include <linux/string.h>
#include <linux/timekeeping.h>
#include <linux/vmalloc.h>

#include "gfx-bridge-plan.h"
#include "fb_breadcrumb.h"

#define GFX_NODE "/soc/power-management@20e000000/power-controller@20320"
#define PMGR_BASE 0x20e000000ULL
#define PMGR_SIZE 0x40000
#define GPC_BASE 0x201e00000ULL
#define GPC_SIZE 0x21000	/* request 13: was 0x11000, which never mapped +0x20000 (every override access hit stray memory) */
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
/* boot 27 (research request 8): Apple's GFX-on sets AUTO_PM_EN (PS bit 28) after the state reaches target; Linux's genpd leaves it clear. One store, one load; result in hs.x[0]/x[1]. */
static bool autopm_done;
static bool h_nowr;	/* boot 29 (request 9): h-steps without W1/W2a, i.e. no host RGX write before the stream (batch's identity read still happens) */
static u32 pa_x[2];
static int step_pa(void)
{
	u32 before, after;

	if (state != ST_IDENTIFIED || autopm_done)
		return -EBUSY;
	before = readl(pmgr + PM_GFX_PS);
	if (before != 0x3ff)
		return fail(-EIO, "pa-ps-not-3ff");
	autopm_done = true;
	writel(before | 0x10000000, pmgr + PM_GFX_PS);	/* 27b: read-modify-write, keeps status bits 8-9 (27 wrote 0x1000000f: no effect) */
	mb();
	udelay(100);
	after = readl(pmgr + PM_GFX_PS);
	if (!(after & 0x10000000) && !(after & 0x300)) {	/* 27c: Apple order: bit 28 in a SECOND store once target reached and bits 8-9 are clear */
		writel(after | 0x10000000, pmgr + PM_GFX_PS);
		mb();
		udelay(100);
		after = readl(pmgr + PM_GFX_PS);
	}
	pa_x[0] = before;
	pa_x[1] = after;
	if (!(after & 0x10000000))
		return fail(-EIO, "pa-bit28-not-set");
	return 0;
}

static int step_hn(void)
{
	if (state != ST_IDENTIFIED || h_nowr || wr.w1_done || wr.w2a_done)
		return -EBUSY;
	h_nowr = true;
	return 0;
}

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
/*
 * z-run 2026-11-22: in GPC state 0 a Fender-block access issued right after the previous one hangs the bus (ten back-to-back
 * reads hung; single accesses separated by sleeps or host round trips are safe). Every Fender access in the F steps therefore
 * goes through gr()/gw(), which wait 1 ms afterwards. The spacing is a first safe-looking guess, not a measured minimum.
 */
static u32 gr(u32 off)
{
	u32 v = readl(gpc_regs + off);

	udelay(1000);
	return v;
}

static void gw(u32 v, u32 off)
{
	writel(v, gpc_regs + off);
	udelay(1000);
}

/* Bounded poll of GPC_STATE bit 4 (busy); ~1 ms per iteration, about 2 s bound (stock allows 30 s; the host watchdog is 20 s). */
static int gpc_wait_idle(void)
{
	int i;

	for (i = 0; i < 2000; i++) {
		if (!(gr(GPC_STATE) & 0x10))
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

static bool cfg_readback;	/* h7e: Apple's J81 kext loads back every ConfigRAM store (review 2026-11-24) */

static void cfg_put(u32 w)
{
	gw(w, GPC_MASK + 4 * cfg_n);
	if (cfg_readback)
		(void)gr(GPC_MASK + 4 * cfg_n);
	cfg_n++;
}

static void cfg_put64(u32 reg, u64 v)
{
	cfg_put(reg + 4);	/* Apple J81 stream writer (slot 0xc8): no flag byte on the first word */
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
	g = gr(GPC_STATE);
	fr[which].g_start = g;
	if ((g & 0x1f) != 0x01)
		return fail(-EBUSY, "f-gpc-not-state-1");
	fb_crumb_clear();
	fb_crumb_mark(1);
	gw(0x10, GPC_STATE);
	msleep(100);	/* g-run 2026-11-22: a read right after the 1 -> 0 store hung the bus; with a delay it is safe */
	ret = gpc_wait_idle();
	fr[which].g_after0 = gr(GPC_STATE);
	if (ret || (fr[which].g_after0 & 0x1f) != 0x00) {
		fr[which].where = "state0-request";
		ret = ret ? ret : -EIO;
		goto recover;
	}
	msleep(100);
	fb_crumb_mark(2);
	if (which != 2) {
		v = gr(0x10);
		gw(0, 0x10);
		v = gr(0x10);
		if (v) {
			fr[which].where = "int-enable-not-zero";
			ret = -EIO;
			goto recover;
		}
		gw(0x40000000, 0);
		cfg_n = 0;
		if (which == 1) {
			cfg_put64(0x3800, 0x0003550000300001ULL);
			cfg_put(0x3808 | 0xff << 16);
			cfg_put(1);
		}
		cfg_put(0xffff0000);
		wmb();
		msleep(100);
		gw(0, 0x20000);
		msleep(10);
		ret = gpc_wait_idle();
		fr[which].g_after20000 = gr(GPC_STATE);
		if (ret) {
			fr[which].where = "after-20000-write";
			goto recover;
		}
	}
	fb_crumb_mark(3);
	gw(0x11, GPC_STATE);
	fb_crumb_mark(4);
	msleep(10);
	ret = gpc_wait_idle();
	g = gr(GPC_STATE);
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
	gw(0x11, GPC_STATE);
	msleep(100);
	gpc_wait_idle();
	fr[which].g_after1 = gr(GPC_STATE);
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


/*
 * H-steps (2026-11-24): F1/F2 split into one host-visible step per Fender access (the pattern of the passing g-run), so the last
 * stage line names the access that hangs. Plain readl/writel, no udelay between accesses; a host round trip separates every step.
 * PMGR observers (GFX PS 0x20320, sequencer 0x1c200, voltage 0x2300c) are sampled at h1/h5/h8/h10/h11 and shown in status.
 *   h0 state==1 check, store GPC_STATE=0x10      h1 read GPC_STATE (+observers)   h2 bounded poll for busy clear
 *   h3 msleep(100), read +0x10   h4 write +0x10=0   h5 read +0x10 (+observers; must be 0)   h6 write +0 = 0x40000000
 *   h7 ConfigRAM: terminator only (F1)   h7b ConfigRAM: F2 list (Apple 64-bit encoding) + terminator   h8 wmb, msleep(100), write +0x20000=0 (+observers)
 *   h9 bounded poll   h10 msleep(100), write GPC_STATE=0x11 (+observers)   h11 poll, state 1, PLL lock, SLC readback (only if state 1 and PLL set)
 */
static struct { int next; int f2; bool skip20000; u32 x[3]; u32 r1, r3, r5, p5, s0, s4, s8, core; u32 obs[5][3]; u32 pll[5]; u32 ps_off, ps_on; int err; } hs;

static void h_obs(int k)
{
	hs.obs[k][0] = readl(pmgr + PM_GFX_PS);
	hs.obs[k][1] = readl(pmgr + 0x1c200);
	hs.obs[k][2] = readl(pmgr + 0x2300c);
	if (k == 0 || k == 1 || k == 4)	/* runs 20-24: PMGR +0x5004 hangs once +0 = 0x40000000 has been stored (h6), so sample it only before h6 and in state 1. Was: run 20: a PLL5 read right after the +0x20000 store hung even with an empty list; sample it only before the store (k=0,1 and h8 pre-store) and in state 1 */
		hs.pll[k] = readl(pmgr + PM_PAGE5_4);
}

/* AT (request 11): Apple's timing. Power cycle + bridges as h3pb, then the second state-0 request WITHOUT waiting for it, and +0x10, +0, run 36's assert list, terminator and the override store in ONE irq-off call (no host round trip). A hang cannot be attributed inside this call. */
static int step_at(void)
{
	unsigned long flags;
	int i, t, ret;

	hs.f2 = 17;
	hs.next = 9;
	ret = pm_runtime_put_sync(consumer);
	hs.ps_off = readl(pmgr + PM_GFX_PS);
	if (ret < 0)
		return fail(ret, "at-runtime-put");
	ret = pm_runtime_get_sync(consumer);
	hs.ps_on = readl(pmgr + PM_GFX_PS);
	if (ret < 0)
		return fail(ret, "at-runtime-get");
	if (hs.ps_on != 0x3ff)
		return fail(-EIO, "at-gfx-not-active");
	for (t = 0; t < 2; t++)
		for (i = 0; i < 33; i++) {
			writel(bridge_plan[t][i][1], bridge_regs[t] + bridge_plan[t][i][0]);
			mb();
		}
	for (i = 0; i < 200000; i++) {
		if (!(readl(gpc_regs + GPC_STATE) & 0x10))
			break;
		udelay(10);
	}
	if (i == 200000)
		return fail(-ETIMEDOUT, "at-pre-poll");
	local_irq_save(flags);
	writel(0x10, gpc_regs + GPC_STATE);
	(void)readl(gpc_regs + GPC_STATE);
	writel(0, gpc_regs + 0x10);
	writel(0x40000000, gpc_regs);
	(void)readl(gpc_regs);
	cfg_n = 0;
	cfg_readback = true;
	cfg_put64(0x100, 0x00e7fffffffffc1dULL);
	cfg_put64(0x100, 0x00e7fe071ffffc1dULL);
	cfg_put64(0x100, 0x0000000100000000ULL);
	cfg_put64(0x100, 0);
	cfg_put(0xffff0000);
	cfg_readback = false;
	wmb();
	writel(0, gpc_regs + 0x20000);
	local_irq_restore(flags);
	return 0;
}


/*
 * F3a (first firmware run, plan research/2026-11-26-j81-f3a-plan.md). The module owns one 8 MiB DMA-coherent region (uncached for the CPU,
 * physically contiguous). The host builds a position-independent blob (boot/j81_f3a_build.py: firmware heap image at region offset 0,
 * header and ConfigRAM word template at F3_HDR) and writes it through the f3_img binary attribute; f3load builds the three GPU page-table
 * levels (PC/PD/PT, 4 KiB pages) at F3_PT and patches BIF_CAT_BASE0 into the ConfigRAM list with the real physical address.
 *   f3alloc : allocate + zero, report the physical base
 *   f3load  : verify header, build tables, verify the walk of 0xe1c0000000, checksum the heap image
 *   h7f1    : stage the ConfigRAM list WITHOUT the final SOFT_RESET release (META stays in reset), for the h8..h11 sequence
 *   h7f2    : the full list (META starts at the 0->1 walk)
 *   f3poll  : poll the event-ring write index in memory for up to 10 s, record the first record (type, words)
 *   f3bif   : read the BIF fault register once (after f3poll)
 */
#define F3_SIZE		(8u << 20)
#define F3_HDR		0x100000u
#define F3_BLOB		(F3_HDR + 0x1000u)
#define F3_PC		0x108000u
#define F3_PD		0x109000u
#define F3_PT		0x10a000u
#define F3_PT2		0x10b000u	/* GPU MMU partition 9 (VA 0xe1c4200000): MMIO windows, 66 MiB above the heap -> PD[33] */
#define F3_MAGIC	0x31413346u	/* "F3A1" */
#define F3_GPU_VA	0xe1c0000000ULL

static struct {
	void *cpu;
	dma_addr_t dma;
	bool show, loaded, alive_seen;
	u32 sum, nwords, rel_idx, ev_ctl, ev_buf, heap_used, walk;
	u32 pw[2];
	u32 polls, wr, rec[3], fault, fault_valid;
	void *snap;
	u32 chg, chg_off[3], chg_val[3], sum2, meta[6];
	bool late, win;
	u32 m2[8], m2sel, m2match;
	u32 cur, chg4[8], chgsel;
	u32 hpc[6], hcnt[6], hn;
} f3;

static int meta_wait_ready(u32 *ctrl1);

static u32 f3_rd(u32 off)
{
	return readl(f3.cpu + off);
}

static int f3_alloc(void)
{
	u64 phys;

	if (state != ST_IDENTIFIED || f3.cpu)
		return -EBUSY;
	if (dma_coerce_mask_and_coherent(consumer, DMA_BIT_MASK(36)))
		return fail(-EIO, "f3-dma-mask");
	f3.cpu = dma_alloc_coherent(consumer, F3_SIZE, &f3.dma, GFP_KERNEL);
	if (!f3.cpu)
		return fail(-ENOMEM, "f3-alloc");
	phys = is_vmalloc_addr(f3.cpu) ? (u64)vmalloc_to_pfn(f3.cpu) << PAGE_SHIFT : virt_to_phys(f3.cpu);
	if (phys != f3.dma)
		return fail(-EIO, "f3-phys-mismatch");
	memset(f3.cpu, 0, F3_SIZE);
	f3.show = true;
	return 0;
}

static void f3_put64(u32 off, u64 v)
{
	writel((u32)v, f3.cpu + off);
	writel(v >> 32, f3.cpu + off + 4);
}

static u64 f3_get64(u32 off)
{
	return (u64)f3_rd(off) | (u64)f3_rd(off + 4) << 32;
}

static int f3_load(void)
{
	u32 i, hdr = F3_HDR, sum = 0, cat_hi, cat_lo, used;
	u64 pc = f3.dma + F3_PC, pd = f3.dma + F3_PD, pt = f3.dma + F3_PT, e, v;

	if (state != ST_IDENTIFIED || !f3.cpu || f3.loaded)
		return -EBUSY;
	if (f3_rd(hdr) != F3_MAGIC)
		return fail(-EINVAL, "f3-blob-magic");
	f3.nwords = f3_rd(hdr + 4);
	f3.rel_idx = f3_rd(hdr + 8);
	f3.ev_ctl = f3_rd(hdr + 12);
	f3.ev_buf = f3_rd(hdr + 16);
	used = f3.heap_used = f3_rd(hdr + 20);
	cat_hi = f3_rd(hdr + 24);
	cat_lo = f3_rd(hdr + 28);
	if (f3.nwords < 8 || f3.nwords > 60 || f3.rel_idx + 5 != f3.nwords || cat_hi >= f3.nwords || cat_lo >= f3.nwords ||
	    used == 0 || used > 0x100000 || (used & 0xfff) || f3.ev_ctl + 0x20 > used || f3.ev_buf >= used)
		return fail(-EINVAL, "f3-blob-header");
	/* patch BIF_CAT_BASE0 (page catalogue physical address) into the staged ConfigRAM word list */
	writel(pc >> 32, f3.cpu + hdr + 0x40 + 4 * cat_hi);
	writel((u32)pc, f3.cpu + hdr + 0x40 + 4 * cat_lo);
	/* GPU page tables: PT maps heap pages 0..used (4 KiB each, valid bit only); PD[0] -> PT; PC[va >> 30 & 0x3ff] -> PD */
	memset(f3.cpu + F3_PC, 0, 0x4000);
	for (i = 0; i < used / 0x1000; i++)
		f3_put64(F3_PT + 8 * i, (f3.dma + (u64)i * 0x1000) | 1);
	f3_put64(F3_PD, pt | 1);
	if (f3_rd(hdr + 32) == 1) {	/* C2 (request 14 t2): Fender 5 pages, AIC timer, AIC SW-int in partition 9; valid-only PT entries */
		u64 pt2 = f3.dma + F3_PT2;

		for (i = 0; i < 5; i++)
			f3_put64(F3_PT2 + 8 * i, (0x201e00000ULL + (u64)i * 0x1000) | 1);
		f3_put64(F3_PT2 + 8 * 5, 0x20e101000ULL | 1);
		f3_put64(F3_PT2 + 8 * 6, 0x20e104000ULL | 1);
		f3_put64(F3_PD + 8 * 33, pt2 | 1);
		f3.win = true;
	}
	writel(((pd >> 12) << 4) | 1, f3.cpu + F3_PC + 4 * ((F3_GPU_VA >> 30) & 0x3ff));
	wmb();
	/* walk back: heap offsets 0, 0x22000 and the last page must resolve to dma + offset */
	f3.walk = 0;
	e = f3_rd(F3_PC + 4 * ((F3_GPU_VA >> 30) & 0x3ff));
	if (!(e & 1) || ((e >> 4) << 12) != pd)
		goto walk_done;
	f3.walk |= 1;
	v = f3_get64(F3_PD);
	if (!(v & 1) || (v & ~0xfffULL) != pt)
		goto walk_done;
	f3.walk |= 2;
	for (i = 0; i < 3; i++) {
		u32 pg = i == 0 ? 0 : i == 1 ? 0x22 : used / 0x1000 - 1;

		v = f3_get64(F3_PT + 8 * pg);
		if (!(v & 1) || (v & ~0xfffULL) != f3.dma + (u64)pg * 0x1000)
			goto walk_done;
	}
	f3.walk |= 4;
	if (f3.win) {
		v = f3_get64(F3_PD + 8 * 33);
		if (!(v & 1) || (v & ~0xfffULL) != f3.dma + F3_PT2)
			goto walk_done;
		v = f3_get64(F3_PT2 + 8 * 6);
		if (v != (0x20e104000ULL | 1))
			goto walk_done;
		f3.walk |= 8;
	}
walk_done:
	for (i = 0; i < used; i += 4)
		sum += f3_rd(i);
	f3.sum = sum;
	f3.snap = vmalloc(used);
	if (f3.snap)
		memcpy(f3.snap, f3.cpu, used);
	f3.pw[0] = pc >> 32;
	f3.pw[1] = (u32)pc;
	f3.loaded = f3.walk == (f3.win ? 15 : 7);
	return f3.loaded ? 0 : fail(-EIO, "f3-walk");
}

static int f3_poll(void)
{
	u32 i;

	if (state != ST_IDENTIFIED || !f3.loaded)
		return -EBUSY;
	/* 250 ms slice per call (repeat the step for a timeline: run 47 died inside one 10 s poll); f3.polls counts elapsed ms across calls */
	for (i = 0; i < 250; i++) {
		f3.wr = f3_rd(f3.ev_ctl + 0x10);
		if (f3.wr)
			break;
		msleep(1);
	}
	f3.polls += i;
	if (f3.wr) {
		f3.rec[0] = f3_rd(f3.ev_buf);
		f3.rec[1] = f3_rd(f3.ev_buf + 4);
		f3.rec[2] = f3_rd(f3.ev_buf + 8);
		f3.alive_seen = f3.rec[0] == 0;
	}
	return 0;
}

static int f3_bif(void)
{
	if (state != ST_IDENTIFIED)
		return -EBUSY;
	f3.fault = readl(core_regs + 0x12b0);
	f3.fault_valid = 1;
	return 0;
}

/* f3sum: diff the heap against the snapshot taken by f3load (did the firmware write anything?). Read-only on our side. */
static int f3_sum(void)
{
	u32 i, sum = 0, v;

	if (state != ST_IDENTIFIED || !f3.loaded || !f3.snap)
		return -EBUSY;
	f3.chg = 0;
	for (i = 0; i < f3.heap_used; i += 4) {
		v = f3_rd(i);
		sum += v;
		if (v != ((u32 *)f3.snap)[i / 4]) {
			if (f3.chg < 3) {
				f3.chg_off[f3.chg] = i;
				f3.chg_val[f3.chg] = v;
			}
			f3.chg++;
		}
	}
	f3.sum2 = sum;
	f3.late = true;
	return 0;
}

/* f3meta: six allow-listed META slave-port reads (T0/T1 ENABLE and STATUS, MMCU SEG2 BASE/LIMIT) after the firmware had its chance to run. */
static int f3_meta(void)
{
	static const u32 addrs[6] = { 0x04800000, 0x04800010, 0x04801000, 0x04801010, 0x04850020, 0x04850024 };
	u32 i, c1;
	int ret;

	if (state != ST_IDENTIFIED || !f3.loaded)
		return -EBUSY;
	for (i = 0; i < 6; i++) {
		ret = meta_wait_ready(&c1);
		if (ret)
			return fail(ret, "f3meta-not-ready");
		writel(addrs[i] | 1U, core_regs + MSLVCTRL0);
		mb();
		(void)readl(core_regs + MSLVCTRL0);
		ret = meta_wait_ready(&c1);
		if (ret)
			return fail(ret, "f3meta-read-timeout");
		f3.meta[i] = readl(core_regs + MSLVDATAX);
	}
	f3.late = true;
	return 0;
}

/* f3metaA / f3metaB (read-only, allow-listed META addresses): A = MMCU SEG0 and SEG1 BASE/LIMIT/OUTA0/OUTA1 (did the boot list program them?),
 * B = SEG3 BASE/LIMIT/OUTA0/OUTA1, D/I cache ctrl, T0PRIVEXT, TXCLKCTRL. Only the latest set is shown in the status line (480-byte cap). */
static int f3_meta2(int which)
{
	static const u32 set[3][8] = {
		{ 0x04850000, 0x04850004, 0x04850008, 0x0485000c, 0x04850010, 0x04850014, 0x04850018, 0x0485001c },
		{ 0x04850030, 0x04850034, 0x04850038, 0x0485003c, 0x04830018, 0x04830020, 0x048000e8, 0x048000b0 },
		/* D (request 14 M1): TXCATCH0..3 (the failed access), TXDEFR, TXPRIVEXT, T0STATUS, T1STATUS. Read-only; T0 is halted. */
		{ 0x04800080, 0x04800088, 0x04800090, 0x04800098, 0x048000a0, 0x048000e8, 0x04800010, 0x04801010 },
	};
	u32 i, c1;
	int ret;

	if (state != ST_IDENTIFIED || !f3.loaded)
		return -EBUSY;
	for (i = 0; i < 8; i++) {
		ret = meta_wait_ready(&c1);
		if (ret)
			return fail(ret, "f3meta2-not-ready");
		writel(set[which][i] | 1U, core_regs + MSLVCTRL0);
		mb();
		(void)readl(core_regs + MSLVCTRL0);
		ret = meta_wait_ready(&c1);
		if (ret)
			return fail(ret, "f3meta2-read-timeout");
		f3.m2[i] = readl(core_regs + MSLVDATAX);
	}
	f3.m2sel = which == 2 ? 4 : which + 1;
	return 0;
}

/* f3metaC: coremem code window, 8 words at 0x80000080 (the LDR places the first code word there; the image copy is at heap +0x1c000).
 * m2match is a bitmask of words equal to the image copy, i.e. did the bootloader copy the coremem image into the core memory? */
static int f3_meta3(void)
{
	u32 i, c1;
	int ret;

	if (state != ST_IDENTIFIED || !f3.loaded)
		return -EBUSY;
	f3.m2match = 0;
	for (i = 0; i < 8; i++) {
		ret = meta_wait_ready(&c1);
		if (ret)
			return fail(ret, "f3metaC-not-ready");
		writel((0x80000080U + 4 * i) | 1U, core_regs + MSLVCTRL0);
		mb();
		(void)readl(core_regs + MSLVCTRL0);
		ret = meta_wait_ready(&c1);
		if (ret)
			return fail(ret, "f3metaC-read-timeout");
		f3.m2[i] = readl(core_regs + MSLVDATAX);
		if (f3.m2[i] == f3_rd(0x1c000 + 4 * i))
			f3.m2match |= 1u << i;
	}
	f3.m2sel = 3;
	return 0;
}

/* f3chg: walk the words the firmware changed in the heap, four per call (offset, value), cursor in f3.cur; wraps to 0 after the last. */
static int f3_chg(void)
{
	u32 i, k = 0, n = 0;

	if (state != ST_IDENTIFIED || !f3.loaded || !f3.snap)
		return -EBUSY;
	memset(f3.chg4, 0, sizeof(f3.chg4));
	for (i = 0; i < f3.heap_used; i += 4) {
		u32 v = f3_rd(i);

		if (v == ((u32 *)f3.snap)[i / 4])
			continue;
		if (k >= f3.cur && n < 4) {
			f3.chg4[2 * n] = i;
			f3.chg4[2 * n + 1] = v;
			n++;
		}
		k++;
	}
	f3.chgsel = 1 + f3.cur;
	f3.cur = n < 4 ? 0 : f3.cur + 4;
	return 0;
}

/* META slave-port helpers (request 15 t3). Read = upstream pvr_meta_cr_read32; write = Apple's stop path (poll ready, MSLVCTRL0 = addr with RD_EN clear, MSLVDATAT = data, poll ready). */
#define MSLVDATAT 0x0a08

static int f3_mread(u32 addr, u32 *v)
{
	u32 c1;
	int ret = meta_wait_ready(&c1);

	if (ret)
		return ret;
	writel(addr | 1U, core_regs + MSLVCTRL0);
	mb();
	(void)readl(core_regs + MSLVCTRL0);
	ret = meta_wait_ready(&c1);
	if (ret)
		return ret;
	*v = readl(core_regs + MSLVDATAX);
	return 0;
}

static int f3_mwrite(u32 addr, u32 data)
{
	u32 c1;
	int ret = meta_wait_ready(&c1);

	if (ret)
		return ret;
	writel(addr & ~1U, core_regs + MSLVCTRL0);
	mb();
	writel(data, core_regs + MSLVDATAT);
	mb();
	return meta_wait_ready(&c1);
}

/* f3pc: three samples of thread 0's PC through the core-register port (write TXUXXRXRQ 0x0480fff8 = 0x00010005 (thread 0, PC, read), poll
 * DREADY bit 31, read TXUXXRXDT 0x0480fff0), 100 ms apart, then TXSTATUS, TXDEFR, TXTIMER. Never touches TXENABLE. m2 = pc0, pc1, pc2, status, defr, timer, tries, err. */
static int f3_pc(void)
{
	u32 i, k, v = 0, tries = 0;
	int ret;

	if (state != ST_IDENTIFIED || !f3.loaded)
		return -EBUSY;
	memset(f3.m2, 0, sizeof(f3.m2));
	for (i = 0; i < 3; i++) {
		ret = f3_mwrite(0x0480fff8, 0x00010005);
		if (ret)
			return fail(ret, "f3pc-write");
		for (k = 0; k < 100; k++) {
			ret = f3_mread(0x0480fff8, &v);
			if (ret)
				return fail(ret, "f3pc-poll");
			tries++;
			if (v & 0x80000000U)
				break;
		}
		if (k == 100) {
			f3.m2[7] = 1;
			break;
		}
		ret = f3_mread(0x0480fff0, &f3.m2[i]);
		if (ret)
			return fail(ret, "f3pc-read");
		if (i < 2)
			msleep(100);
	}
	(void)f3_mread(0x04800010, &f3.m2[3]);
	(void)f3_mread(0x048000a0, &f3.m2[4]);
	(void)f3_mread(0x04800020, &f3.m2[5]);
	f3.m2[6] = tries;
	f3.m2sel = 5;
	return 0;
}

/* f3timer: read-only, AIC timer page 0x20e101000 (the window the firmware sees), words 0 and 1, twice, 1 ms apart (request 15 P3). m2 = a0, a1, b0, b1. */
static int f3_timer(void)
{
	void __iomem *t;

	if (state != ST_IDENTIFIED)
		return -EBUSY;
	t = ioremap_np(0x20e101000ULL, 0x1000);
	if (!t)
		return fail(-ENOMEM, "f3timer-map");
	memset(f3.m2, 0, sizeof(f3.m2));
	f3.m2[0] = readl(t);
	f3.m2[1] = readl(t + 4);
	msleep(1);
	f3.m2[2] = readl(t);
	f3.m2[3] = readl(t + 4);
	iounmap(t);
	f3.m2sel = 6;
	f3.show = true;
	return 0;
}

/* f3reg A/B/C: thread 0 general registers through the core-register port (TXUXXRXRQ 0x0480fff8: RDnWR bit 16, thread bits 15:12, register bits 11:4, unit bits 3:0;
 * units: 1 = D0, 2 = D1, 3 = A0, 4 = A1, 5 = PC), value in TXUXXRXDT 0x0480fff0. Snapshot of a RUNNING thread: values can be mutually inconsistent (request 15 t3). */
static int f3_reg(int which)
{
	static const u32 req[3][8] = {
		{ 0x00010001, 0x00010011, 0x00010021, 0x00010031, 0x00010041, 0x00010051, 0x00010061, 0x00010071 },	/* D0.0..7 */
		{ 0x00010002, 0x00010012, 0x00010022, 0x00010032, 0x00010042, 0x00010052, 0x00010062, 0x00010072 },	/* D1.0..7 */
		{ 0x00010003, 0x00010013, 0x00010023, 0x00010033, 0x00010004, 0x00010014, 0x00010024, 0x00010034 },	/* A0.0..3, A1.0..3 */
	};
	u32 i, k, v = 0;
	int ret;

	if (state != ST_IDENTIFIED || !f3.loaded)
		return -EBUSY;
	memset(f3.m2, 0, sizeof(f3.m2));
	for (i = 0; i < 8; i++) {
		ret = f3_mwrite(0x0480fff8, req[which][i]);
		if (ret)
			return fail(ret, "f3reg-write");
		for (k = 0; k < 100; k++) {
			ret = f3_mread(0x0480fff8, &v);
			if (ret)
				return fail(ret, "f3reg-poll");
			if (v & 0x80000000U)
				break;
		}
		if (k == 100)
			break;
		ret = f3_mread(0x0480fff0, &f3.m2[i]);
		if (ret)
			return fail(ret, "f3reg-read");
	}
	f3.m2sel = 7 + which;	/* 7 = R0 (D0), 8 = R1 (D1), 9 = RA (A0/A1) */
	return 0;
}

/* f3pch: 200 PC samples ~1 ms apart, the six most frequent PCs with counts (histogram of where thread 0 spends its time). */
static int f3_pch(void)
{
	u32 i, k, j, v = 0, pc, ns = 0;
	u32 spc[200];
	int ret;

	if (state != ST_IDENTIFIED || !f3.loaded)
		return -EBUSY;
	for (i = 0; i < 200; i++) {
		ret = f3_mwrite(0x0480fff8, 0x00010005);
		if (ret)
			return fail(ret, "f3pch-write");
		for (k = 0; k < 100; k++) {
			ret = f3_mread(0x0480fff8, &v);
			if (ret)
				return fail(ret, "f3pch-poll");
			if (v & 0x80000000U)
				break;
		}
		if (k == 100)
			continue;
		ret = f3_mread(0x0480fff0, &pc);
		if (ret)
			return fail(ret, "f3pch-read");
		spc[ns++] = pc;
		usleep_range(500, 700);
	}
	memset(f3.hpc, 0, sizeof(f3.hpc));
	memset(f3.hcnt, 0, sizeof(f3.hcnt));
	for (i = 0; i < ns; i++) {
		bool seen = false;

		for (j = 0; j < i; j++)
			if (spc[j] == spc[i])
				seen = true;
		if (seen)
			continue;
		pc = 0;
		for (j = 0; j < ns; j++)
			if (spc[j] == spc[i])
				pc++;
		/* insert into the top six by count */
		for (j = 0; j < 6; j++)
			if (pc > f3.hcnt[j]) {
				for (k = 5; k > j; k--) {
					f3.hpc[k] = f3.hpc[k - 1];
					f3.hcnt[k] = f3.hcnt[k - 1];
				}
				f3.hpc[j] = spc[i];
				f3.hcnt[j] = pc;
				break;
			}
	}
	f3.hn = ns;
	f3.m2sel = 10;
	return 0;
}

/* f3coreA..F (request 16 follow-up, run 57): read-only dump of 8 words each from core memory: A 0x80009c40, B 0x80009c60, C 0x80009c80, D 0x80009ca0 (the hot loop at ~0x80009c74),
 * E 0x8000a000, F 0x8000a020 (the data the loop works on). Slave-port reads only. */
static int f3_core(int idx)
{
	static const u32 base[6] = { 0x80009c40, 0x80009c60, 0x80009c80, 0x80009ca0, 0x8000a000, 0x8000a020 };
	u32 i;
	int ret;

	if (state != ST_IDENTIFIED || !f3.loaded)
		return -EBUSY;
	memset(f3.m2, 0, sizeof(f3.m2));
	for (i = 0; i < 8; i++) {
		ret = f3_mread(base[idx] + 4 * i, &f3.m2[i]);
		if (ret)
			return fail(ret, "f3core-read");
	}
	f3.m2sel = 11 + idx;
	return 0;
}

/* f3tb (request 16 T1): the whole AIC timebase page 0x20e101000 (64 words) read twice 1 ms apart. m2 = nonzero words (first read), changed words, first changed
 * offset, its first value, its second value, first nonzero offset, its value, OR of all words. Read-only. */
static int f3_tb(void)
{
	void __iomem *t;
	u32 a[64], b[64], i, nz = 0, ch = 0, orr = 0, fch = 0xffffffff, fnz = 0xffffffff;

	if (state != ST_IDENTIFIED)
		return -EBUSY;
	t = ioremap_np(0x20e101000ULL, 0x1000);
	if (!t)
		return fail(-ENOMEM, "f3tb-map");
	for (i = 0; i < 64; i++)
		a[i] = readl(t + 4 * i);
	msleep(1);
	for (i = 0; i < 64; i++)
		b[i] = readl(t + 4 * i);
	iounmap(t);
	memset(f3.m2, 0, sizeof(f3.m2));
	for (i = 0; i < 64; i++) {
		orr |= a[i] | b[i];
		if (a[i]) {
			nz++;
			if (fnz == 0xffffffff)
				fnz = i;
		}
		if (a[i] != b[i]) {
			ch++;
			if (fch == 0xffffffff)
				fch = i;
		}
	}
	f3.m2[0] = nz;
	f3.m2[1] = ch;
	f3.m2[2] = fch == 0xffffffff ? fch : 4 * fch;
	f3.m2[3] = fch == 0xffffffff ? 0 : a[fch];
	f3.m2[4] = fch == 0xffffffff ? 0 : b[fch];
	f3.m2[5] = fnz == 0xffffffff ? fnz : 4 * fnz;
	f3.m2[6] = fnz == 0xffffffff ? 0 : a[fnz];
	f3.m2[7] = orr;
	f3.m2sel = 20;
	f3.show = true;
	return 0;
}

/* f3usc (request 16 U1): RGX 0xe100 + 8i and 0xe200 + 8i, i = 0..31 (the USC exception/state slots Apple's failure dump walks), through a temporary mapping (core_regs only covers 0x4000).
 * m2 = [count with bit 0 set at 0xe1xx, first such slot, its value, same for 0xe2xx x3, OR of all 0xe1xx values] and m2[7] = OR of all 0xe2xx values. Read-only, state 1 only. */
static int f3_usc(void)
{
	void __iomem *t;
	u32 i, base, cnt, first, fv, orr, k;

	if (state != ST_IDENTIFIED)
		return -EBUSY;
	if ((readl(gpc_regs + GPC_STATE) & 0x1f) != 0x01)
		return fail(-EBUSY, "f3usc-not-state-1");
	t = ioremap_np(CORE_BASE + 0xe000, 0x1000);
	if (!t)
		return fail(-ENOMEM, "f3usc-map");
	memset(f3.m2, 0, sizeof(f3.m2));
	for (k = 0; k < 2; k++) {
		base = k ? 0x200 : 0x100;
		cnt = 0;
		first = 0xffffffff;
		fv = 0;
		orr = 0;
		for (i = 0; i < 32; i++) {
			u32 v = readl(t + base + 8 * i);

			orr |= v;
			if ((v & 1) && first == 0xffffffff) {
				first = i;
				fv = v;
			}
			if (v & 1)
				cnt++;
		}
		f3.m2[3 * k] = cnt;
		f3.m2[3 * k + 1] = first;
		f3.m2[3 * k + 2] = fv;
		f3.m2[6 + k] = orr;
	}
	iounmap(t);
	f3.m2sel = 21;
	return 0;
}

/* f3halt (request 16 H1): halt thread 0 with Apple's stop write (META TXENABLE 0x04800000 <- 0xfffffffe through the slave-port write sequence), then read TXENABLE, TXSTATUS, PC (TXUXXRXRQ
 * 0x00010005) and PCX (0x00010015). m2 = txenable-after, txstatus, pc, pcx, then pc again 10 ms later, err. One-shot: the run ends with this thread stopped. */
static int f3_creg(u32 req, u32 *out)
{
	u32 k, v = 0;
	int ret = f3_mwrite(0x0480fff8, req);

	if (ret)
		return ret;
	for (k = 0; k < 100; k++) {
		ret = f3_mread(0x0480fff8, &v);
		if (ret)
			return ret;
		if (v & 0x80000000U)
			break;
	}
	if (k == 100)
		return -ETIMEDOUT;
	return f3_mread(0x0480fff0, out);
}

static int f3_halt(void)
{
	int ret;

	if (state != ST_IDENTIFIED || !f3.loaded)
		return -EBUSY;
	memset(f3.m2, 0, sizeof(f3.m2));
	ret = f3_mwrite(0x04800000, 0xfffffffe);
	if (ret)
		return fail(ret, "f3halt-write");
	msleep(2);
	ret = f3_mread(0x04800000, &f3.m2[0]);
	if (!ret)
		ret = f3_mread(0x04800010, &f3.m2[1]);
	if (!ret)
		ret = f3_creg(0x00010005, &f3.m2[2]);
	if (!ret)
		ret = f3_creg(0x00010015, &f3.m2[3]);
	msleep(10);
	if (!ret)
		ret = f3_creg(0x00010005, &f3.m2[4]);
	if (ret)
		return fail(ret, "f3halt-read");
	f3.m2sel = 22;
	return 0;
}

/* f3t1 (request 17 R1): thread 1 state: T1ENABLE 0x04801000, T1STATUS 0x04801010, PC through the core-register port (TXUXXRXRQ 0x00011005 = thread 1, unit PC, read) twice, 10 ms apart.
 * m2 = t1enable, t1status, pc, pc, 0, 0, 0, 0. Read-only. */
static int f3_t1(void)
{
	int ret;

	if (state != ST_IDENTIFIED || !f3.loaded)
		return -EBUSY;
	memset(f3.m2, 0, sizeof(f3.m2));
	ret = f3_mread(0x04801000, &f3.m2[0]);
	if (!ret)
		ret = f3_mread(0x04801010, &f3.m2[1]);
	if (!ret)
		ret = f3_creg(0x00011005, &f3.m2[2]);
	msleep(10);
	if (!ret)
		ret = f3_creg(0x00011005, &f3.m2[3]);
	if (ret)
		return fail(ret, "f3t1-read");
	f3.m2sel = 23;
	return 0;
}

/* f3kick (request 17 K1): Apple's doorbell with empty queues: Fender +0x14 <- 7 (clear all status), GPC state must be 1, then ONE write RGX 0xb00 (MTS_SCHEDULE) <- 0x10
 * (TASK_COUNTED, DM0, context 0, priority 0). Never before the firmware had its chance to post alive (run it after the poll). m2 = fender+0x14 before, after, gpc state, event write index. */
static int f3_kick(void)
{
	if (state != ST_IDENTIFIED || !f3.loaded)
		return -EBUSY;
	if ((readl(gpc_regs + GPC_STATE) & 0x1f) != 0x01)
		return fail(-EBUSY, "f3kick-not-state-1");
	memset(f3.m2, 0, sizeof(f3.m2));
	f3.m2[0] = readl(gpc_regs + 0x14);
	writel(7, gpc_regs + 0x14);
	mb();
	f3.m2[1] = readl(gpc_regs + 0x14);
	f3.m2[2] = readl(gpc_regs + GPC_STATE);
	mb();
	writel(0x10, core_regs + 0xb00);
	mb();
	msleep(50);
	f3.m2[3] = f3_rd(f3.ev_ctl + 0x10);
	f3.m2sel = 24;
	return 0;
}

/* f3t1start (K2): emulate the LDR START_THREADS record for thread 1 through the core-register port, as DDK/Apple's loader would: write data to TXUXXRXDT (0x0480fff0), then the request to
 * TXUXXRXRQ (0x0480fff8) with RDnWR clear (thread 1 = bits 15:12, register bits 11:4, unit bits 3:0): A0StP (unit 3, reg 0) <- 0x8000b3c8, PC (unit 5) <- 0x20000000; read both back;
 * then TXENABLE of thread 1 (0x04801000) <- (value | 1). Never touches thread 0. m2 = pc readback, sp readback, t1enable after, t1status after, t1 pc after 5 ms, after 50 ms, event write idx, err. */
static int f3_t1start(void)
{
	u32 v;
	int ret;

	if (state != ST_IDENTIFIED || !f3.loaded)
		return -EBUSY;
	memset(f3.m2, 0, sizeof(f3.m2));
	ret = f3_mread(0x04801000, &v);
	if (ret)
		return fail(ret, "f3t1s-read");
	if (v & 1)
		return fail(-EBUSY, "f3t1s-already-enabled");
	ret = f3_mwrite(0x0480fff0, 0x8000b3c8);
	if (!ret)
		ret = f3_mwrite(0x0480fff8, 0x00001003);
	if (!ret)
		ret = f3_mwrite(0x0480fff0, 0x20000000);
	if (!ret)
		ret = f3_mwrite(0x0480fff8, 0x00001005);
	if (ret)
		return fail(ret, "f3t1s-write");
	ret = f3_creg(0x00011005, &f3.m2[0]);
	if (!ret)
		ret = f3_creg(0x00011003, &f3.m2[1]);
	if (ret)
		return fail(ret, "f3t1s-readback");
	ret = f3_mwrite(0x04801000, v | 1);
	if (ret)
		return fail(ret, "f3t1s-enable");
	msleep(5);
	(void)f3_mread(0x04801000, &f3.m2[2]);
	(void)f3_mread(0x04801010, &f3.m2[3]);
	(void)f3_creg(0x00011005, &f3.m2[4]);
	msleep(45);
	(void)f3_creg(0x00011005, &f3.m2[5]);
	f3.m2[6] = f3_rd(f3.ev_ctl + 0x10);
	f3.m2sel = 25;
	return 0;
}

/* f3slc (request 18 E0): was the alive record posted and parked in the SLC? Our host reads uncached DRAM while the firmware's pages (valid-only PTEs, no SLC bypass) are write-back through the SLC.
 * Reads the AIC SW-int words for IRQ 138 (0x20e104010 and 0x20e104210), the event write index; flushes the SLC (RGX 0x3818 <- 1, SLC_CTRL_FLUSH_INVAL ALL), polls RGX 0x3898 & 0xff == 0xff
 * (bounded, 1 ms steps, 200 ms), then re-reads the event write index and its first record word and diffs the heap again.
 * m2 = aic0x10, aic0x210, wr before, 0x3898 after, poll iterations, wr after, record type, changed heap words after. */
static int f3_slc(void)
{
	void __iomem *t;
	u32 i, v = 0;
	int ret;

	if (state != ST_IDENTIFIED || !f3.loaded)
		return -EBUSY;
	if ((readl(gpc_regs + GPC_STATE) & 0x1f) != 0x01)
		return fail(-EBUSY, "f3slc-not-state-1");
	memset(f3.m2, 0, sizeof(f3.m2));
	t = ioremap_np(0x20e104000ULL, 0x1000);
	if (!t)
		return fail(-ENOMEM, "f3slc-map");
	f3.m2[0] = readl(t + 0x10);
	f3.m2[1] = readl(t + 0x210);
	iounmap(t);
	f3.m2[2] = f3_rd(f3.ev_ctl + 0x10);
	writel(1, core_regs + 0x3818);
	mb();
	for (i = 0; i < 200; i++) {
		v = readl(core_regs + 0x3898);
		if ((v & 0xff) == 0xff)
			break;
		msleep(1);
	}
	f3.m2[3] = v;
	f3.m2[4] = i;
	msleep(5);
	f3.m2[5] = f3_rd(f3.ev_ctl + 0x10);
	f3.m2[6] = f3_rd(f3.ev_buf);
	ret = f3_sum();
	if (ret)
		return ret;
	f3.m2[7] = f3.chg;
	f3.m2sel = 26;
	return 0;
}

static ssize_t f3_img_write(struct file *file, struct kobject *kobj, const struct bin_attribute *attr, char *buf, loff_t off, size_t count)
{
	if (!f3.cpu || f3.loaded || off < 0 || off + count > F3_BLOB)
		return -EINVAL;
	memcpy(f3.cpu + off, buf, count);
	return count;
}
static const BIN_ATTR_WO(f3_img, F3_BLOB);

static int step_h(int n, int mode)
{
	int i;
	u32 v = 0;

	if (state != ST_IDENTIFIED || !(wr.w2a_done || h_nowr) || hs.next != n)
		return -EBUSY;
	if (n == 7)
		hs.f2 = mode;
	if (n == 8)
		hs.skip20000 = mode == 3;
	hs.next = n + 1;
	if (n == 3 && mode == 20)
		return step_at();
	if (n == 6 && mode >= 10) {	/* boot 26 (research request 7): h6+h7+h8 in ONE call, no sleep, Apple's order. mode 10 empty list, 11 h7d entry. Load-backs after every store except +0x20000. */
		hs.f2 = mode;
		hs.next = 9;
		cfg_n = 0;
		writel(0x40000000, gpc_regs);
		(void)readl(gpc_regs);
		cfg_readback = true;
		if (mode == 11) {
			cfg_put(0x3808 | 0xff << 16);
			cfg_put(0);
		}
		cfg_put(0xffff0000);
		cfg_readback = false;
		wmb();
		writel(0, gpc_regs + 0x20000);
		return 0;
	}
	switch (n) {
	case 0:
		if ((readl(gpc_regs + GPC_STATE) & 0x1f) != 0x01)
			return fail(-EBUSY, "h-gpc-not-state-1");
		/* byte-identical to g0 (the passing run): no framebuffer writes in this call; run z0 before h0 for crumbs */
		writel(0x10, gpc_regs + GPC_STATE);
		return 0;
	case 1:
		hs.r1 = readl(gpc_regs + GPC_STATE);
		h_obs(0);
		return 0;
	case 2:
		for (i = 0; i < 200000; i++) {
			v = readl(gpc_regs + GPC_STATE);
			if (!(v & 0x10))
				break;
			udelay(10);
		}
		return i == 200000 ? fail(-ETIMEDOUT, "h2-poll-timeout") : 0;
	case 3:
		if (mode == 8 || mode == 12) {	/* h3pb (mode 12) = h3p plus bridge re-apply (boot 30); h3p (research request 6): Apple power-cycles GFX between the first wake and the stream. Off, read PS only, on, 2nd state-0 request. */
			int ret;

			ret = pm_runtime_put_sync(consumer);
			hs.ps_off = readl(pmgr + PM_GFX_PS);
			if (ret < 0)
				return fail(ret, "h3p-runtime-put");
			ret = pm_runtime_get_sync(consumer);
			hs.ps_on = readl(pmgr + PM_GFX_PS);
			if (ret < 0)
				return fail(ret, "h3p-runtime-get");
			if (hs.ps_on != 0x3ff)
				return fail(-EIO, "h3p-gfx-not-active");
			if (mode == 12) {	/* Apple re-applies bridge-settings-9/10 (66 stores) after every GFX power-on (request 9); the runner did it only once in batch */
				int t;

				for (t = 0; t < 2; t++)
					for (i = 0; i < 33; i++) {
						writel(bridge_plan[t][i][1], bridge_regs[t] + bridge_plan[t][i][0]);
						mb();
					}
			}
			for (i = 0; i < 200000; i++) {	/* Apple setter: poll busy, store 0x10, one load */
				if (!(readl(gpc_regs + GPC_STATE) & 0x10))
					break;
				udelay(10);
			}
			if (i == 200000)
				return fail(-ETIMEDOUT, "h3p-pre-poll");
			writel(0x10, gpc_regs + GPC_STATE);
			(void)readl(gpc_regs + GPC_STATE);
			for (i = 0; i < 200000; i++) {
				if (!(readl(gpc_regs + GPC_STATE) & 0x10))
					break;
				udelay(10);
			}
			if (i == 200000)
				return fail(-ETIMEDOUT, "h3p-post-poll");
		}
		msleep(100);
		hs.r3 = readl(gpc_regs + 0x10);
		return 0;
	case 4:
		writel(0, gpc_regs + 0x10);
		return 0;
	case 5:
		hs.r5 = readl(gpc_regs + 0x10);
		h_obs(1);
		return hs.r5 ? fail(-EIO, "h5-int-enable-not-zero") : 0;
	case 6:
		if (mode == 9) {	/* boot 25 (research request 7): read the override's reset value once, >=1 ms after the last Fender access */
			udelay(2000);
			hs.x[0] = readl(gpc_regs + 0x20000);
			udelay(2000);
		}
		writel(0x40000000, gpc_regs);
		return 0;
	case 7:
		cfg_n = 0;
		if (hs.f2 == 1) {
			cfg_put64(0x3800, 0x0003550000300001ULL);
			cfg_put(0x3808 | 0xff << 16);
			cfg_put(1);
		} else if (hs.f2 == 13) {	/* h7s (boot A, request 10): Apple's SLC_CTRL_MISC entry alone, 64-bit: 0x3800 <- 0x00035500_00300001 (decode mode 0x32 -> 0x30) */
			cfg_put64(0x3800, 0x0003550000300001ULL);
		} else if (hs.f2 == 14) {	/* h7m (boot D, request 10): META_BOOT 0x0bf8 <- 1 alone, 32-bit entry, each store loaded back. A change outside the SLC; read 0xbf8 in state 1 afterwards */
			cfg_readback = true;
			cfg_put(0x0bf8 | 0xff << 16);
			cfg_put(1);
		} else if (hs.f2 == 15) {	/* h7r (boot C, request 10): Apple's SLC framing: SOFT_RESET x3, SLC pair (0x3800, 0x3808<-1, both 64-bit), SOFT_RESET <- 0. No META_BOOT, no BIF. */
			cfg_put64(0x100, 0x00e7fffffffffc1dULL);
			cfg_put64(0x100, 0x00e7fe071ffffc1dULL);
			cfg_put64(0x100, 0x0000000100000000ULL);
			cfg_put64(0x3800, 0x0003550000300001ULL);
			cfg_put64(0x3808, 1);
			cfg_put64(0x100, 0);
		} else if (hs.f2 == 16) {	/* h7z (run 34 follow-up (1)): SOFT_RESET release alone, 64-bit 0x100 <- 0 (the current value, a no-op write) */
			cfg_put64(0x100, 0);
		} else if (hs.f2 == 17) {	/* h7y (run 34/35 follow-up (3)): SOFT_RESET x3 asserts + release, NO SLC entries */
			cfg_put64(0x100, 0x00e7fffffffffc1dULL);
			cfg_put64(0x100, 0x00e7fe071ffffc1dULL);
			cfg_put64(0x100, 0x0000000100000000ULL);
			cfg_put64(0x100, 0);
		} else if (hs.f2 == 18) {	/* h7q (R1, request 11): GARTEN-only assert (Apple's third value) + release */
			cfg_put64(0x100, 0x0000000100000000ULL);
			cfg_put64(0x100, 0);
		} else if (hs.f2 == 19) {	/* h7p (R2): SLC-only assert (bit 27, the value Apple's stop path writes) + release */
			cfg_put64(0x100, 0x0000000008000000ULL);
			cfg_put64(0x100, 0);
		} else if (hs.f2 == 21) {	/* h7k (X1, request 12): run 36's four SOFT_RESET entries, META_BOOT 0x0bf8 <- 1 last (loaded back). Use with h8n: no state-0 release, the 0->1 request applies the list */
			cfg_put64(0x100, 0x00e7fffffffffc1dULL);
			cfg_put64(0x100, 0x00e7fe071ffffc1dULL);
			cfg_put64(0x100, 0x0000000100000000ULL);
			cfg_put64(0x100, 0);
			cfg_readback = true;
			cfg_put(0x0bf8 | 0xff << 16);
			cfg_put(1);
		} else if (hs.f2 == 22) {	/* h7l (X4, request 12): X1's four SOFT_RESET entries, then the SLC pair (0x3800, 0x3808 <- 1, 64-bit), META_BOOT last (loaded back). Use with h8n; expect 0x3800/0x3808 changed at h11 */
			cfg_put64(0x100, 0x00e7fffffffffc1dULL);
			cfg_put64(0x100, 0x00e7fe071ffffc1dULL);
			cfg_put64(0x100, 0x0000000100000000ULL);
			cfg_put64(0x100, 0);
			cfg_put64(0x3800, 0x0003550000300001ULL);
			cfg_put64(0x3808, 1);
			cfg_readback = true;
			cfg_put(0x0bf8 | 0xff << 16);
			cfg_put(1);
		} else if (hs.f2 == 23) {	/* h7a (run 41 follow-up): Apple's exact order, SOFT_RESET x3 asserts, SLC pair (0x3800, 0x3808 <- 1), SOFT_RESET release, then META_BOOT last (loaded back). Use with h8n; does 0x3808 read 1 at h11? */
			cfg_put64(0x100, 0x00e7fffffffffc1dULL);
			cfg_put64(0x100, 0x00e7fe071ffffc1dULL);
			cfg_put64(0x100, 0x0000000100000000ULL);
			cfg_put64(0x3800, 0x0003550000300001ULL);
			cfg_put64(0x3808, 1);
			cfg_put64(0x100, 0);
			cfg_readback = true;
			cfg_put(0x0bf8 | 0xff << 16);
			cfg_put(1);
		} else if (hs.f2 == 24 || hs.f2 == 25) {	/* h7f1 / h7f2 (F3a): the blob's ConfigRAM list; f1 omits the final SOFT_RESET release (5 words incl. terminator), META stays in reset */
			u32 k, nw = hs.f2 == 24 ? f3.rel_idx : f3.nwords - 1;

			if (!f3.loaded)
				return fail(-EBUSY, "h7f-not-loaded");
			cfg_readback = true;
			for (k = 0; k < nw; k++)
				cfg_put(f3_rd(F3_HDR + 0x40 + 4 * k));
		} else if (hs.f2 == 7) {	/* h7g: Apple's SOFT_RESET framing (3 asserts, no META_BOOT/BIF) around the 0x3808 no-op, then release */
			cfg_put64(0x100, 0x00e7fffffffffc1dULL);
			cfg_put64(0x100, 0x00e7fe071ffffc1dULL);
			cfg_put64(0x100, 0x0000000100000000ULL);
			cfg_put64(0x3808, 0);
			cfg_put64(0x100, 0);
		} else if (hs.f2 == 6) {	/* h7f: Apple's exact 64-bit encoding of the 0x3808 no-op (0x3808 <- 0): {reg+4, hi, reg|ff, lo} */
			cfg_put64(0x3808, 0);
		} else if (hs.f2 == 5) {	/* h7e: as h7d (no-op entry) but every store is loaded back, Apple-style */
			cfg_readback = true;
			cfg_put(0x3808 | 0xff << 16);
			cfg_put(0);
		} else if (hs.f2 == 4) {	/* h7d: ONE entry writing the CURRENT value (SLC 0x3808 <- 0) */
			cfg_put(0x3808 | 0xff << 16);
			cfg_put(0);
		} else if (hs.f2 == 2) {	/* h7c: ONE 32-bit entry only (SLC 0x3808 <- 1) */
			cfg_put(0x3808 | 0xff << 16);
			cfg_put(1);
		}
		cfg_put(0xffff0000);
		cfg_readback = false;
		if (hs.f2 == 9) {	/* boot 25: empty list (run 11 sequence), then +0 (bit 29 = Fender timer sleep?) and GPC_STATE, >=1 ms apart */
			msleep(100);
			hs.x[1] = readl(gpc_regs);
			udelay(2000);
			hs.x[2] = readl(gpc_regs + GPC_STATE);
		}
		return 0;
	case 8:
		wmb();
		msleep(100);
		if (!hs.skip20000)	/* h8n: no core-word store (runs 12/13: any non-empty list hung at this store) */
			writel(0, gpc_regs + 0x20000);
		return 0;	/* no PMGR/RGX read after the store: h_obs(2) now runs at the end of h9, after the Fender poll */
	case 9:
		for (i = 0; i < 200000; i++) {
			v = readl(gpc_regs + GPC_STATE);
			if (!(v & 0x10))
				break;
			udelay(10);
		}
		if (i == 200000)
			return fail(-ETIMEDOUT, "h9-poll-timeout");
		h_obs(2);
		return 0;
	case 10:
		msleep(100);
		writel(0x11, gpc_regs + GPC_STATE);
		h_obs(3);
		return 0;
	case 11:
		for (i = 0; i < 200000; i++) {
			v = readl(gpc_regs + GPC_STATE);
			if (!(v & 0x10))
				break;
			udelay(10);
		}
		h_obs(4);
		if (i == 200000 || (v & 0x1f) != 0x01)
			return fail(-EIO, "h11-state1-not-reached");
		udelay(20);
		hs.p5 = readl(pmgr + PM_PAGE5_4);
		if (!(hs.p5 & 0x40000000))
			return fail(-EIO, "h11-pll-lock-clear");
		hs.x[0] = readl(core_regs + 0xbf8);	/* boot D: META_BOOT after the walk (state 1) */
		hs.s0 = readl(core_regs + 0x3800);
		hs.s4 = readl(core_regs + 0x3804);
		hs.s8 = readl(core_regs + 0x3808);
		hs.core = readl(core_regs + 0x20);
		return hs.core != res.core ? fail(-EIO, "h11-core-mismatch") : 0;
	case 12:
		/* only from state 1 with PLL locked (h11 passed): release the ConfigRAM walk, then re-read SLC and core */
		if (hs.p5 != 0x40000000 || (readl(gpc_regs + GPC_STATE) & 0x1f) != 0x01)
			return fail(-EBUSY, "h12-not-state-1");
		msleep(100);
		writel(0, gpc_regs + 0x20000);
		for (i = 0; i < 200000; i++) {
			v = readl(gpc_regs + GPC_STATE);
			if (!(v & 0x10))
				break;
			udelay(10);
		}
		hs.r5 = v;
		if (mode == 1)	/* h12s (X2, request 12): store + poll only, no RGX read after the release */
			return i == 200000 ? fail(-ETIMEDOUT, "h12-poll-timeout") : 0;
		hs.s0 = readl(core_regs + 0x3800);
		hs.s4 = readl(core_regs + 0x3804);
		hs.s8 = readl(core_regs + 0x3808);
		hs.x[0] = readl(core_regs + 0xbf8);	/* W1S: META_BOOT after a walk released in state 1 */
		/* SOFT_RESET read removed: it hung h12 in run 38 */
		hs.core = readl(core_regs + 0x20);
		return i == 200000 ? fail(-ETIMEDOUT, "h12-poll-timeout") : 0;
	}
	return -EINVAL;
}

/*
 * Z-steps: isolate what the passing g-run did not do. Repeatable, no hardware access except the named one.
 *   z0  blank the crumb row and draw mark 1 (framebuffer writes only)
 *   z1  msleep(100) only
 *   z2  draw mark 2 (framebuffer write only)
 *   z3  read GPC +0x1000 ten times back-to-back (no delay), recorded in status
 */
static u32 z_last[10];
static bool z3_done;

static int step_z(int n)
{
	int i;

	if (state != ST_IDENTIFIED || !wr.w2a_done)
		return -EBUSY;
	switch (n) {
	case 0:
		fb_crumb_clear();
		fb_crumb_mark(1);
		return 0;
	case 1:
		msleep(100);
		return 0;
	case 2:
		fb_crumb_mark(2);
		return 0;
	case 3:
		for (i = 0; i < 10; i++)
			z_last[i] = readl(gpc_regs + GPC_STATE);
		z3_done = true;
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
	else if (sysfs_streq(buf, "hn"))
		ret = step_hn();
	else if (sysfs_streq(buf, "pa"))
		ret = step_pa();
	else if (sysfs_streq(buf, "w2a"))
		ret = step_w2a();
	else if (sysfs_streq(buf, "z0"))
		ret = step_z(0);
	else if (sysfs_streq(buf, "z1"))
		ret = step_z(1);
	else if (sysfs_streq(buf, "z2"))
		ret = step_z(2);
	else if (sysfs_streq(buf, "z3"))
		ret = step_z(3);
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
	else if (sysfs_streq(buf, "h0"))
		ret = step_h(0, 0);
	else if (sysfs_streq(buf, "h1"))
		ret = step_h(1, 0);
	else if (sysfs_streq(buf, "h2"))
		ret = step_h(2, 0);
	else if (sysfs_streq(buf, "h3"))
		ret = step_h(3, 0);
	else if (sysfs_streq(buf, "h4"))
		ret = step_h(4, 0);
	else if (sysfs_streq(buf, "h5"))
		ret = step_h(5, 0);
	else if (sysfs_streq(buf, "h6"))
		ret = step_h(6, 0);
	else if (sysfs_streq(buf, "h7"))
		ret = step_h(7, 0);
	else if (sysfs_streq(buf, "h8"))
		ret = step_h(8, 0);
	else if (sysfs_streq(buf, "h8n"))
		ret = step_h(8, 3);
	else if (sysfs_streq(buf, "h9"))
		ret = step_h(9, 0);
	else if (sysfs_streq(buf, "h10"))
		ret = step_h(10, 0);
	else if (sysfs_streq(buf, "h11"))
		ret = step_h(11, 0);
	else if (sysfs_streq(buf, "h12"))
		ret = step_h(12, 0);
	else if (sysfs_streq(buf, "h12s"))
		ret = step_h(12, 1);
	else if (sysfs_streq(buf, "h7k"))
		ret = step_h(7, 21);
	else if (sysfs_streq(buf, "h7l"))
		ret = step_h(7, 22);
	else if (sysfs_streq(buf, "h7a"))
		ret = step_h(7, 23);
	else if (sysfs_streq(buf, "h7f1"))
		ret = step_h(7, 24);
	else if (sysfs_streq(buf, "h7f2"))
		ret = step_h(7, 25);
	else if (sysfs_streq(buf, "f3alloc"))
		ret = f3_alloc();
	else if (sysfs_streq(buf, "f3load"))
		ret = f3_load();
	else if (sysfs_streq(buf, "f3poll"))
		ret = f3_poll();
	else if (sysfs_streq(buf, "f3bif"))
		ret = f3_bif();
	else if (sysfs_streq(buf, "f3sum"))
		ret = f3_sum();
	else if (sysfs_streq(buf, "f3chg"))
		ret = f3_chg();
	else if (sysfs_streq(buf, "f3pc"))
		ret = f3_pc();
	else if (sysfs_streq(buf, "f3regA"))
		ret = f3_reg(0);
	else if (sysfs_streq(buf, "f3regB"))
		ret = f3_reg(1);
	else if (sysfs_streq(buf, "f3regC"))
		ret = f3_reg(2);
	else if (sysfs_streq(buf, "f3pch"))
		ret = f3_pch();
	else if (sysfs_streq(buf, "f3tb"))
		ret = f3_tb();
	else if (sysfs_streq(buf, "f3usc"))
		ret = f3_usc();
	else if (sysfs_streq(buf, "f3halt"))
		ret = f3_halt();
	else if (sysfs_streq(buf, "f3t1"))
		ret = f3_t1();
	else if (sysfs_streq(buf, "f3kick"))
		ret = f3_kick();
	else if (sysfs_streq(buf, "f3slc"))
		ret = f3_slc();
	else if (sysfs_streq(buf, "f3t1start"))
		ret = f3_t1start();
	else if (sysfs_streq(buf, "f3coreA"))
		ret = f3_core(0);
	else if (sysfs_streq(buf, "f3coreB"))
		ret = f3_core(1);
	else if (sysfs_streq(buf, "f3coreC"))
		ret = f3_core(2);
	else if (sysfs_streq(buf, "f3coreD"))
		ret = f3_core(3);
	else if (sysfs_streq(buf, "f3coreE"))
		ret = f3_core(4);
	else if (sysfs_streq(buf, "f3coreF"))
		ret = f3_core(5);
	else if (sysfs_streq(buf, "f3timer"))
		ret = f3_timer();
	else if (sysfs_streq(buf, "f3meta"))
		ret = f3_meta();
	else if (sysfs_streq(buf, "f3metaA"))
		ret = f3_meta2(0);
	else if (sysfs_streq(buf, "f3metaB"))
		ret = f3_meta2(1);
	else if (sysfs_streq(buf, "f3metaD"))
		ret = f3_meta2(2);
	else if (sysfs_streq(buf, "f3metaC"))
		ret = f3_meta3();
	else if (sysfs_streq(buf, "h7b"))
		ret = step_h(7, 1);
	else if (sysfs_streq(buf, "h7e"))
		ret = step_h(7, 5);
	else if (sysfs_streq(buf, "h6m"))
		ret = step_h(6, 10);
	else if (sysfs_streq(buf, "h6md"))
		ret = step_h(6, 11);
	else if (sysfs_streq(buf, "h6x"))
		ret = step_h(6, 9);
	else if (sysfs_streq(buf, "h7x"))
		ret = step_h(7, 9);
	else if (sysfs_streq(buf, "h3pb"))
		ret = step_h(3, 12);
	else if (sysfs_streq(buf, "h3p"))
		ret = step_h(3, 8);
	else if (sysfs_streq(buf, "h7g"))
		ret = step_h(7, 7);
	else if (sysfs_streq(buf, "h7f"))
		ret = step_h(7, 6);
	else if (sysfs_streq(buf, "h7s"))
		ret = step_h(7, 13);
	else if (sysfs_streq(buf, "h7m"))
		ret = step_h(7, 14);
	else if (sysfs_streq(buf, "h7r"))
		ret = step_h(7, 15);
	else if (sysfs_streq(buf, "h7z"))
		ret = step_h(7, 16);
	else if (sysfs_streq(buf, "h7y"))
		ret = step_h(7, 17);
	else if (sysfs_streq(buf, "h7q"))
		ret = step_h(7, 18);
	else if (sysfs_streq(buf, "h7p"))
		ret = step_h(7, 19);
	else if (sysfs_streq(buf, "h3at"))
		ret = step_h(3, 20);
	else if (sysfs_streq(buf, "h7d"))
		ret = step_h(7, 4);
	else if (sysfs_streq(buf, "h7c"))
		ret = step_h(7, 2);
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
	/*
	 * The host supervisor (boot/gpu-watchdog-supervisor.c) reads each stage line into char line[512]; a longer line is never
	 * forwarded and the watchdog is no longer fed. That, not a bus hang, ended the F1/f1a/z3/h0 runs of 2026-11-22..24 (lines of
	 * 558-700 bytes). Once an f/h/z3 step has output, the status is compact, and it is capped below 500 bytes in any case.
	 */
	bool compact = hs.next || autopm_done || z3_done || fr[0].done || fr[1].done || fr[2].done;

	mutex_lock(&lock);
	n = sysfs_emit(buf, "state=%s reason=%s skip_pll1=%d skip_pll4=%d crumb=%s", st_name[state], reason, skip_pll1, skip_pll4, fb_crumb_state());
	if (state >= ST_ACTIVE)
		n += sysfs_emit_at(buf, n, " gfx_ps=0x%08x gfx_vid=0x%08x", res.gfx_ps, res.vid);
	if (res.batch_done && !compact)
		n += sysfs_emit_at(buf, n,
				   " core=0x%08x id=0x%08x hi=0x%08x bvnc_rev=%u.%u.%u.%u gpc=0x%08x polls=%u page5=0x%08x bridge_ns=%llu poll_to_core_ns=%llu core_read_ns=%llu",
				   res.core, res.id, res.hi, (res.core >> 24) & 0xff, (res.core >> 16) & 0xff,
				   (res.core >> 8) & 0xff, res.core & 0xff, res.gpc_raw, res.polls, res.page5,
				   res.bridge_ns, res.poll_to_core_ns, res.core_read_ns);
	if (wr.w1_done && !compact)
		n += sysfs_emit_at(buf, n, " w1_before=0x%08x w1_after=0x%08x", wr.w1_before, wr.w1_after);
	if (z3_done)
		n += sysfs_emit_at(buf, n, " z3=%08x,%08x,%08x,%08x,%08x,%08x,%08x,%08x,%08x,%08x", z_last[0], z_last[1], z_last[2], z_last[3], z_last[4], z_last[5], z_last[6], z_last[7], z_last[8], z_last[9]);
	if (gs.next && !compact)
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
	if (autopm_done)
		n += sysfs_emit_at(buf, n, " pa=%08x,%08x", pa_x[0], pa_x[1]);
	if (f3.show) {
		n += sysfs_emit_at(buf, n, " f3=%llx,%u,w%u,s%08x,pc%08x%08x,n%u,e%u,%08x/%08x,%08x,%08x,%08x,bif%d:%08x", (u64)f3.dma, f3.loaded, f3.walk, f3.sum, f3.pw[0], f3.pw[1], f3.nwords, f3.polls, f3.wr, f3.ev_ctl, f3.rec[0], f3.rec[1], f3.rec[2], f3.fault_valid, f3.fault);
		if (f3.chgsel)
			n += sysfs_emit_at(buf, n, " chg@%u=%x:%08x,%x:%08x,%x:%08x,%x:%08x", f3.chgsel - 1, f3.chg4[0], f3.chg4[1], f3.chg4[2], f3.chg4[3], f3.chg4[4], f3.chg4[5], f3.chg4[6], f3.chg4[7]);
		else if (f3.late)
			n += sysfs_emit_at(buf, n, " f3x=c%u,%x:%08x,%x:%08x,%x:%08x,s%08x m=%08x,%08x,%08x,%08x,%08x,%08x", f3.chg, f3.chg_off[0], f3.chg_val[0], f3.chg_off[1], f3.chg_val[1], f3.chg_off[2], f3.chg_val[2], f3.sum2,
					   f3.meta[0], f3.meta[1], f3.meta[2], f3.meta[3], f3.meta[4], f3.meta[5]);
		if (f3.m2sel == 10)
			n += sysfs_emit_at(buf, n, " mH%u=%08x*%u,%08x*%u,%08x*%u,%08x*%u,%08x*%u,%08x*%u", f3.hn, f3.hpc[0], f3.hcnt[0], f3.hpc[1], f3.hcnt[1], f3.hpc[2], f3.hcnt[2], f3.hpc[3], f3.hcnt[3], f3.hpc[4], f3.hcnt[4], f3.hpc[5], f3.hcnt[5]);
		else if (f3.m2sel == 26)
			n += sysfs_emit_at(buf, n, " mSL=%08x,%08x,%08x,%08x,%u,%08x,%08x,%u", f3.m2[0], f3.m2[1], f3.m2[2], f3.m2[3], f3.m2[4], f3.m2[5], f3.m2[6], f3.m2[7]);
		else if (f3.m2sel == 25)
			n += sysfs_emit_at(buf, n, " mS1=%08x,%08x,%08x,%08x,%08x,%08x,%08x", f3.m2[0], f3.m2[1], f3.m2[2], f3.m2[3], f3.m2[4], f3.m2[5], f3.m2[6]);
		else if (f3.m2sel == 23)
			n += sysfs_emit_at(buf, n, " mT1=%08x,%08x,%08x,%08x", f3.m2[0], f3.m2[1], f3.m2[2], f3.m2[3]);
		else if (f3.m2sel == 24)
			n += sysfs_emit_at(buf, n, " mKK=%08x,%08x,%08x,%08x", f3.m2[0], f3.m2[1], f3.m2[2], f3.m2[3]);
		else if (f3.m2sel == 22)
			n += sysfs_emit_at(buf, n, " mHL=%08x,%08x,%08x,%08x,%08x", f3.m2[0], f3.m2[1], f3.m2[2], f3.m2[3], f3.m2[4]);
		else if (f3.m2sel == 20 || f3.m2sel == 21)
			n += sysfs_emit_at(buf, n, " m%s=%08x,%08x,%08x,%08x,%08x,%08x,%08x,%08x", f3.m2sel == 20 ? "TB" : "US", f3.m2[0], f3.m2[1], f3.m2[2], f3.m2[3], f3.m2[4], f3.m2[5], f3.m2[6], f3.m2[7]);
		else if (f3.m2sel >= 11)
			n += sysfs_emit_at(buf, n, " mK%c=%08x,%08x,%08x,%08x,%08x,%08x,%08x,%08x", 'A' + f3.m2sel - 11, f3.m2[0], f3.m2[1], f3.m2[2], f3.m2[3], f3.m2[4], f3.m2[5], f3.m2[6], f3.m2[7]);
		else if (f3.m2sel)
			n += sysfs_emit_at(buf, n, " m%c=%08x,%08x,%08x,%08x,%08x,%08x,%08x,%08x k%02x", f3.m2sel == 1 ? 'A' : f3.m2sel == 2 ? 'B' : f3.m2sel == 3 ? 'C' : f3.m2sel == 4 ? 'D' : f3.m2sel == 5 ? 'P' : f3.m2sel == 7 ? 'X' : f3.m2sel == 8 ? 'Y' : f3.m2sel == 9 ? 'Z' : 'T', f3.m2[0], f3.m2[1], f3.m2[2], f3.m2[3], f3.m2[4], f3.m2[5], f3.m2[6], f3.m2[7], f3.m2match);
		else if (hs.next)
			n += sysfs_emit_at(buf, n, " h_x=%08x h_next=%d h_f2=%d h_p5=%08x h_slc=%08x/%08x/%08x h_core=%08x", hs.x[0], hs.next, hs.f2, hs.p5, hs.s0, hs.s4, hs.s8, hs.core);
	} else if (hs.next)
		n += sysfs_emit_at(buf, n, " h_x=%08x,%08x,%08x h_ps=%08x,%08x h_next=%d h_f2=%d h_r1=%08x h_r3=%08x h_r5=%08x h_p5=%08x h_slc=%08x/%08x/%08x h_core=%08x h_obs=%08x,%08x,%08x/%08x,%08x,%08x/%08x,%08x,%08x/%08x,%08x,%08x/%08x,%08x,%08x h_pll=%08x,%08x,%08x,%08x,%08x",
				   hs.x[0], hs.x[1], hs.x[2], hs.ps_off, hs.ps_on, hs.next, hs.f2, hs.r1, hs.r3, hs.r5, hs.p5, hs.s0, hs.s4, hs.s8, hs.core,
				   hs.obs[0][0], hs.obs[0][1], hs.obs[0][2], hs.obs[1][0], hs.obs[1][1], hs.obs[1][2], hs.obs[2][0], hs.obs[2][1], hs.obs[2][2],
				   hs.obs[3][0], hs.obs[3][1], hs.obs[3][2], hs.obs[4][0], hs.obs[4][1], hs.obs[4][2],
				   hs.pll[0], hs.pll[1], hs.pll[2], hs.pll[3], hs.pll[4]);
	if (wr.w2a_done && !compact)
		n += sysfs_emit_at(buf, n, " w2a_set=0x%016llx w2a_clear=0x%016llx w2a_core=0x%08x", wr.w2a_set, wr.w2a_clear, wr.w2a_core);
	if (n > 480)
		n = 480;	/* cap: see above; the tail (newest fields) is cut, never the newline */
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
		ret = device_create_bin_file(consumer, &bin_attr_f3_img);
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
