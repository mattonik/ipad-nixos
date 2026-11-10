// SPDX-License-Identifier: GPL-2.0-only
/* One J81 PMGR page-5 read, triggered explicitly after module insertion. */
#include <linux/atomic.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>

#define PAGE5_BASE 0x20e005000ULL
#define PAGE5_SIZE 0x1000

static unsigned int offset;
module_param(offset, uint, 0000);
static struct device *page5_device;
static atomic_t attempted = ATOMIC_INIT(0);

static ssize_t read_once_show(struct device *dev, struct device_attribute *attr,
			      char *buf)
{
	void __iomem *regs;
	u32 value;
	(void)dev;
	(void)attr;
	if (atomic_cmpxchg(&attempted, 0, 1))
		return -EBUSY;
	/* PMGR already owns the containing resource; map only for this read. */
	regs = ioremap(PAGE5_BASE, PAGE5_SIZE);
	if (!regs)
		return -ENOMEM;
	value = readl(regs + offset);
	iounmap(regs);
	return sysfs_emit(buf, "address=0x%llx value=0x%08x\n",
			  PAGE5_BASE + offset, value);
}
static DEVICE_ATTR(read_once, 0400, read_once_show, NULL);

static int __init page5_read_once_init(void)
{
	int ret;
	if (PAGE_SIZE != PAGE5_SIZE || !of_machine_is_compatible("apple,j81") ||
	    (offset != 0 && offset != 4 && offset != 8))
		return -ENODEV;
	page5_device = root_device_register("j81-page5-read-once");
	if (IS_ERR(page5_device))
		return PTR_ERR(page5_device);
	ret = device_create_file(page5_device, &dev_attr_read_once);
	if (ret)
		root_device_unregister(page5_device);
	else
		__module_get(THIS_MODULE);
	return ret;
}
module_init(page5_read_once_init);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("One-shot read-only J81 PMGR page-5 observation");
