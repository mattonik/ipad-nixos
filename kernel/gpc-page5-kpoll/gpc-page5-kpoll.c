// SPDX-License-Identifier: GPL-2.0-only
/*
 * TEST ONLY. One J81 GPC state-1 request and a page-5 sample taken in the
 * same kernel context as the successful GPC poll.
 *
 * It never writes page 5 and never touches the GPU core (0x201000000).
 * Results are returned only after the whole batch; a stall loses them.
 *
 * Ranges (J81 only):
 *   GPC   0x201e00000 + 0x11000  no Linux driver or DT node claims it; the
 *                                earlier probes reached it through /dev/mem.
 *   page5 0x20e005000 + 0x1000   inside the PMGR node's resource; mapped here
 *                                a second time for one or two reads at +4.
 * Both are mapped at module load, before any device access, so a failed
 * mapping cannot leave the GPC half programmed.
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

#define GPC_BASE 0x201e00000ULL
#define GPC_SIZE 0x11000
#define GPC_STATE 0x1000
#define GPC_MASK 0x10000
#define PAGE5_BASE 0x20e005000ULL
#define PAGE5_SIZE 0x1000
#define PAGE5_OFFSET 4
#define POLL_LIMIT 1000
#define POLL_SLEEP_MIN_US 10
#define POLL_SLEEP_MAX_US 20
#define LATER_DELAY_US 100

enum { MODE_IMMEDIATE, MODE_PAIRED, MODE_DELAYED };
static const char *const mode_names[] = { "immediate", "paired", "delayed" };

static char *mode;
module_param(mode, charp, 0000);
static int mode_id = -1;
static struct device *kpoll_device;
static void __iomem *gpc_regs, *page5_regs;
static atomic_t state_attempted = ATOMIC_INIT(0);
static atomic_t batch_attempted = ATOMIC_INIT(0);
static int state_known;
static u32 initial_state;

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
	u64 t_prewrite, t_postwrite, t_poll = 0, t_first = 0, t_later = 0;
	u32 state = 0, first = 0, later = 0;
	unsigned long flags;
	unsigned int i;
	bool ok = false;

	(void)dev;
	(void)attr;
	if (atomic_cmpxchg(&batch_attempted, 0, 1))
		return -EBUSY;
	/* Same precondition the host enforced for the userspace probes. */
	if (!state_known || initial_state != 0)
		return -EINVAL;

	/*
	 * The three validated GPC setup stores, in the validated order. Device
	 * memory stores are issued in program order; mb() repeats the full
	 * barrier the userspace probe placed after each store.
	 */
	writel(0xffff0000, gpc_regs + GPC_MASK);
	mb();
	writel(0x40000000, gpc_regs);
	mb();
	local_irq_save(flags);
	t_prewrite = ktime_get_raw_fast_ns();
	writel(0x11, gpc_regs + GPC_STATE);
	mb();
	t_postwrite = ktime_get_raw_fast_ns();
	local_irq_restore(flags);

	for (i = 0; i < POLL_LIMIT; i++) {
		/*
		 * Local interrupts stay masked from the timestamp before the
		 * poll load until the last page-5 load and its timestamp, so
		 * this CPU cannot be preempted or take an IRQ in between. FIQ,
		 * SError, other CPUs and bus latency are not controlled.
		 */
		local_irq_save(flags);
		t_poll = ktime_get_raw_fast_ns();
		state = readl(gpc_regs + GPC_STATE);
		if (!(state & 0x10)) {
			if ((state & 0x1f) == 1) {
				if (mode_id != MODE_DELAYED) {
					first = readl(page5_regs + PAGE5_OFFSET);
					t_first = ktime_get_raw_fast_ns();
				}
				if (mode_id != MODE_IMMEDIATE) {
					udelay(LATER_DELAY_US);
					later = readl(page5_regs + PAGE5_OFFSET);
					t_later = ktime_get_raw_fast_ns();
				}
				ok = true;
			}
			local_irq_restore(flags);
			i++;
			break;
		}
		local_irq_restore(flags);
		usleep_range(POLL_SLEEP_MIN_US, POLL_SLEEP_MAX_US);
	}
	if (!ok)
		return sysfs_emit(buf, "result=poll-failed mode=%s raw=0x%08x polls=%u\n",
				  mode_names[mode_id], state, i);
	return sysfs_emit(buf,
			  "result=ok mode=%s raw=0x%08x polls=%u prewrite_ns=%llu postwrite_ns=%llu first_valid=%u first=0x%08x first_ns=%llu later_valid=%u later=0x%08x later_ns=%llu\n",
			  mode_names[mode_id], state, i,
			  t_poll - t_prewrite, t_poll - t_postwrite,
			  mode_id != MODE_DELAYED, first,
			  mode_id != MODE_DELAYED ? t_first - t_poll : 0ULL,
			  mode_id != MODE_IMMEDIATE, later,
			  mode_id != MODE_IMMEDIATE ? t_later - t_poll : 0ULL);
}
static DEVICE_ATTR(batch, 0400, batch_show, NULL);

static int __init gpc_page5_kpoll_init(void)
{
	int ret, i;

	if (PAGE_SIZE != PAGE5_SIZE || !of_machine_is_compatible("apple,j81") || !mode)
		return -ENODEV;
	for (i = 0; i < 3; i++)
		if (!strcmp(mode, mode_names[i]))
			mode_id = i;
	if (mode_id < 0)
		return -ENODEV;
	gpc_regs = ioremap(GPC_BASE, GPC_SIZE);
	if (!gpc_regs)
		return -ENOMEM;
	page5_regs = ioremap(PAGE5_BASE, PAGE5_SIZE);
	if (!page5_regs) {
		ret = -ENOMEM;
		goto unmap_gpc;
	}
	kpoll_device = root_device_register("j81-gpc-page5-kpoll");
	if (IS_ERR(kpoll_device)) {
		ret = PTR_ERR(kpoll_device);
		goto unmap_page5;
	}
	ret = device_create_file(kpoll_device, &dev_attr_gpc_state);
	if (!ret)
		ret = device_create_file(kpoll_device, &dev_attr_batch);
	if (ret) {
		root_device_unregister(kpoll_device);
		goto unmap_page5;
	}
	/* No exit path: the module and its two mappings stay for this boot. */
	__module_get(THIS_MODULE);
	return 0;
unmap_page5:
	iounmap(page5_regs);
unmap_gpc:
	iounmap(gpc_regs);
	return ret;
}
module_init(gpc_page5_kpoll_init);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("One-shot J81 GPC state request with an in-kernel page-5 sample");
