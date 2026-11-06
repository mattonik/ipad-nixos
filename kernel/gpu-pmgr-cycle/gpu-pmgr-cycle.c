// SPDX-License-Identifier: GPL-2.0-only
/* One-shot J81 GFX reset-generation consumer; no GPU MMIO. */
#include <linux/atomic.h>
#include <linux/device.h>
#include <linux/init.h>
#include <linux/module.h>
#include <linux/mfd/syscon.h>
#include <linux/of.h>
#include <linux/of_address.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/pm_domain.h>
#include <linux/pm_runtime.h>
#include <linux/regmap.h>

#define GFX_NODE "/soc/power-management@20e000000/power-controller@20320"

extern const bool j81_gpu_pmgr_failstop_v1;
static struct device *consumer;
static struct regmap *pmgr;
static bool ready;
static atomic_t attempted = ATOMIC_INIT(0);

static ssize_t cycle_once_store(struct device *dev, struct device_attribute *attr,
				const char *buf, size_t count)
{
	u32 state;
	int ret;

	(void)attr;
	if (!sysfs_streq(buf, "1"))
		return -EINVAL;
	if (!smp_load_acquire(&ready))
		return -EAGAIN;
	if (atomic_cmpxchg(&attempted, 0, 1))
		return -EBUSY;
	ret = regmap_read(pmgr, 0x20320, &state);
	if (ret || state != 0x00000300)
		return ret ?: -EBUSY;
	ret = pm_runtime_get_sync(dev);
	if (ret < 0)
		return ret;
	ret = pm_runtime_put_sync(dev);
	if (ret < 0)
		return ret;
	ret = pm_runtime_get_sync(dev);
	if (ret < 0)
		return ret;
	return count;
}
static DEVICE_ATTR_WO(cycle_once);

static int __init gpu_pmgr_cycle_init(void)
{
	struct device_node *gfx;
	struct platform_device *provider;
	struct of_phandle_args domain = { .args_count = 0 };
	struct resource parent_resource;
	u32 reg[2], cells;
	bool bound;
	int ret = -EINVAL;

	if (!j81_gpu_pmgr_failstop_v1 || !of_machine_is_compatible("apple,j81"))
		return -ENODEV;
	gfx = of_find_node_by_path(GFX_NODE);
	if (!gfx)
		return -ENODEV;
	if (!of_device_is_available(gfx) ||
	    !of_device_is_compatible(gfx, "apple,t7000-pmgr-pwrstate") ||
	    of_property_read_bool(gfx, "experimental,j81-gpu-test-no-poweroff") ||
	    of_property_read_bool(gfx, "power-domains") ||
	    of_property_read_u32(gfx, "#power-domain-cells", &cells) || cells ||
	    of_property_count_u32_elems(gfx, "reg") != 2 ||
	    of_property_read_u32_array(gfx, "reg", reg, 2) || reg[0] != 0x20320 ||
	    reg[1] != 4 || of_address_to_resource(gfx->parent, 0, &parent_resource) ||
	    parent_resource.start != 0x20e000000ULL || resource_size(&parent_resource) < 0x20324)
		goto out_node;
	provider = of_find_device_by_node(gfx);
	if (!provider)
		goto out_node;
	device_lock(&provider->dev);
	bound = device_is_bound(&provider->dev) && provider->dev.driver &&
		!strcmp(provider->dev.driver->name, "apple-pmgr-pwrstate");
	device_unlock(&provider->dev);
	put_device(&provider->dev);
	if (!bound)
		goto out_node;
	pmgr = syscon_node_to_regmap(gfx->parent);
	if (IS_ERR(pmgr)) {
		ret = PTR_ERR(pmgr);
		goto out_node;
	}
	consumer = root_device_register("gpu-pmgr-cycle");
	if (IS_ERR(consumer)) {
		ret = PTR_ERR(consumer);
		goto out_node;
	}
	ret = device_create_file(consumer, &dev_attr_cycle_once);
	if (ret)
		goto out_device;
	ret = pm_runtime_set_suspended(consumer);
	if (ret)
		goto out_file;
	domain.np = gfx;
	ret = of_genpd_add_device(&domain, consumer);
	if (ret)
		goto out_file;
	pm_runtime_enable(consumer);
	smp_store_release(&ready, true);
	of_node_put(gfx);
	return 0;
out_file:
	device_remove_file(consumer, &dev_attr_cycle_once);
out_device:
	root_device_unregister(consumer);
out_node:
	of_node_put(gfx);
	return ret;
}
module_init(gpu_pmgr_cycle_init);
/* No exit: the final runtime-PM reference remains held until reboot. */
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("One-shot J81 GFX PMGR reset-generation diagnostic");
