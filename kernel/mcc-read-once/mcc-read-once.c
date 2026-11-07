// SPDX-License-Identifier: GPL-2.0-only
/* One acknowledged J81 MCC read; no writes or automatic MMIO at module load. */
#include <linux/atomic.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/ioport.h>

#define MCC_BASE 0x200000000ULL
#define MCC_SIZE 0x1000
#define MCC_OFFSET 0x830

static struct device *mcc_device;
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
	if (!request_mem_region(MCC_BASE, MCC_SIZE, "j81-mcc-read-once"))
		return -EBUSY;
	regs = ioremap(MCC_BASE, MCC_SIZE);
	if (!regs) {
		release_mem_region(MCC_BASE, MCC_SIZE);
		return -ENOMEM;
	}
	value = readl(regs + MCC_OFFSET);
	iounmap(regs);
	release_mem_region(MCC_BASE, MCC_SIZE);
	return sysfs_emit(buf, "address=0x%llx value=0x%08x\n",
			  MCC_BASE + MCC_OFFSET, value);
}
static DEVICE_ATTR_RO(read_once);

static int __init mcc_read_once_init(void)
{
	int ret;

	if (PAGE_SIZE != MCC_SIZE || !of_machine_is_compatible("apple,j81"))
		return -ENODEV;
	mcc_device = root_device_register("j81-mcc-read-once");
	if (IS_ERR(mcc_device))
		return PTR_ERR(mcc_device);
	ret = device_create_file(mcc_device, &dev_attr_read_once);
	if (ret)
		root_device_unregister(mcc_device);
	else
		__module_get(THIS_MODULE);
	return ret;
}
module_init(mcc_read_once_init);
/* Pin module text until reboot so the sysfs endpoint and one-shot guard survive. */
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("One-shot read-only J81 MCC observation");
