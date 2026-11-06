// Read-only J81 Fender status interface; no reset, wake, or RGX access.
#include <linux/device.h>
#include <linux/init.h>
#include <linux/io.h>
#include <linux/module.h>

#define FENDER_BASE 0x201e00000ULL
#define FENDER_SIZE 0x21000
#define STATE_OFF 0x1000
#define CONTROL_OFF 0x0
#define HOLD_OFF 0x20000

static void __iomem *fender;
static struct device *status_device;

static ssize_t state_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	(void)dev; (void)attr;
	return sysfs_emit(buf, "0x%08x\n", readl(fender + STATE_OFF));
}
static ssize_t control_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	(void)dev; (void)attr;
	return sysfs_emit(buf, "0x%08x\n", readl(fender + CONTROL_OFF));
}
static ssize_t hold_show(struct device *dev, struct device_attribute *attr, char *buf)
{
	(void)dev; (void)attr;
	return sysfs_emit(buf, "0x%08x\n", readl(fender + HOLD_OFF));
}
static DEVICE_ATTR_RO(state);
static DEVICE_ATTR_RO(control);
static DEVICE_ATTR_RO(hold);

static int __init fender_status_init(void)
{
	int ret;
	fender = ioremap(FENDER_BASE, FENDER_SIZE);
	if (!fender) return -ENOMEM;
	status_device = root_device_register("gpu-fender-status");
	if (IS_ERR(status_device)) { ret = PTR_ERR(status_device); goto unmap; }
	ret = device_create_file(status_device, &dev_attr_state);
	if (ret) goto unregister;
	ret = device_create_file(status_device, &dev_attr_control);
	if (ret) goto remove_state;
	ret = device_create_file(status_device, &dev_attr_hold);
	if (ret) goto remove_control;
	return 0;
remove_control: device_remove_file(status_device, &dev_attr_control);
remove_state: device_remove_file(status_device, &dev_attr_state);
unregister: root_device_unregister(status_device);
unmap: iounmap(fender); return ret;
}

static void __exit fender_status_exit(void)
{
	device_remove_file(status_device, &dev_attr_hold);
	device_remove_file(status_device, &dev_attr_control);
	device_remove_file(status_device, &dev_attr_state);
	root_device_unregister(status_device);
	iounmap(fender);
}

module_init(fender_status_init);
module_exit(fender_status_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Read-only J81 Fender status");
