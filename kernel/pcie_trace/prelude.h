/*
 * Minimal host stand-in for the Linux APIs used by pcie-apple-t7000.c, so the real
 * driver source can be compiled on the build host and its MMIO write sequence traced.
 * Every write and delay the driver performs is appended to the trace in order.
 * Not a model of any hardware behaviour: reads return the fake memory contents.
 */
#ifndef PCIE_TRACE_PRELUDE_H
#define PCIE_TRACE_PRELUDE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
#define __iomem
#define BIT(n) (1U << (n))
#define ilog2(n) (31 - __builtin_clz(n))
#define is_power_of_2(n) ((n) != 0 && (((n) & ((n) - 1)) == 0))
#define static_assert _Static_assert
#define EINVAL 22
#define ENOMEM 12
#define EIO 5
#define ENODEV 19
#define ENOSPC 28
#define EPROBE_DEFER 517
#define GFP_KERNEL 0
#define WARN_ON_ONCE(x) (x)
#define PCIE_RESET_CONFIG_WAIT_MS 100

/*
 * Logging: as in the real kernel, dev_info/dev_warn/dev_err ALWAYS evaluate their
 * arguments (so a readl() used as a log argument is a real read), while dev_dbg
 * does NOT (no_printk / disabled dynamic debug). The harness mirrors that, so moving
 * a read into a dev_dbg argument changes the traced read sequence and is caught.
 */
void pcie_trace_log(const void *dev, const char *fmt, ...);
#define dev_info(dev, ...) pcie_trace_log((dev), __VA_ARGS__)
#define dev_warn(dev, ...) pcie_trace_log((dev), __VA_ARGS__)
#define dev_err(dev, ...) pcie_trace_log((dev), __VA_ARGS__)
#define dev_dbg(dev, ...) do { if (0) pcie_trace_log((dev), __VA_ARGS__); } while (0)
#define dev_err_probe(dev, err, ...) ((void)(dev), (err))
#define MODULE_DEVICE_TABLE(a, b)
#define MODULE_DESCRIPTION(x)
#define MODULE_LICENSE(x)
#define module_platform_driver(x)

/* ---- trace ---- */
extern FILE *trace_out;
void trace_event(const char *fmt, ...);

/* ---- devices, resources, device tree ---- */
struct device_node { int id; };
struct device { struct device_node *of_node; };
struct platform_device { struct device dev; void *drvdata; };
struct resource { u64 start, end; };
#define resource_size(r) ((r)->end - (r)->start + 1)
#define to_platform_device(d) ((struct platform_device *)((char *)(d) - offsetof(struct platform_device, dev)))
#define platform_get_drvdata(p) ((p)->drvdata)
#define IS_ERR(p) false
#define PTR_ERR_OR_ZERO(p) 0
struct of_device_id { char compatible[64]; };
struct platform_driver { int (*probe)(struct platform_device *); struct { const char *name; const struct of_device_id *of_match_table; bool suppress_bind_attrs; } driver; };

int of_address_to_resource(struct device_node *np, int index, struct resource *res);
void __iomem *devm_ioremap_resource(struct device *dev, struct resource *res);
void __iomem *devm_ioremap(struct device *dev, u64 start, u64 size);
bool of_property_present(const struct device_node *np, const char *name);
struct device_node *of_parse_phandle(const struct device_node *np, const char *name, int idx);
#define of_node_put(np) do { (void)(np); } while (0)
#define put_device(d) do { (void)(d); } while (0)

/* ---- i2c / regmap (PMU) ---- */
struct i2c_client { struct device dev; };
struct regmap { int unused; };
struct i2c_client *of_find_i2c_device_by_node(struct device_node *np);
struct regmap *dev_get_regmap(struct device *dev, const char *name);
int regmap_read(struct regmap *map, unsigned int reg, unsigned int *val);
int regmap_write(struct regmap *map, unsigned int reg, unsigned int val);

/* ---- PCI host ---- */
struct list_head { struct list_head *next, *prev; };
#define container_of(ptr, type, member) ((type *)((char *)(ptr) - offsetof(type, member)))
#define list_for_each_entry(pos, head, member) \
	for (pos = container_of((head)->next, __typeof__(*pos), member); \
	     &pos->member != (head); pos = container_of(pos->member.next, __typeof__(*pos), member))
struct gpio_desc { int id; };
struct pci_host_perst { struct list_head list; struct gpio_desc *desc; };
struct pci_host_port { struct list_head list; struct list_head perst; };
struct pci_host_bridge { struct list_head ports; };
struct pci_config_window { void __iomem *win; struct device *parent; };
struct pci_ops { void *(*map_bus)(void *, unsigned int, unsigned int); int (*read)(void); int (*write)(void); };
struct pci_ecam_ops { unsigned int bus_shift; struct pci_ops pci_ops; int (*init)(struct pci_config_window *); };
void *pci_ecam_map_bus(void *a, unsigned int b, unsigned int c);
int pci_generic_config_read(void);
int pci_generic_config_write(void);
struct pci_host_bridge *devm_pci_alloc_host_bridge(struct device *dev, size_t priv);
int pci_host_common_parse_ports(struct device *dev, struct pci_host_bridge *bridge);
int pci_host_common_init(struct platform_device *pdev, struct pci_host_bridge *bridge, const struct pci_ecam_ops *ops);
int gpiod_direction_output(struct gpio_desc *desc, int value);

/* ---- MMIO and time ---- */
u8 readb(const void __iomem *addr);
u16 readw(const void __iomem *addr);
u32 readl(const void __iomem *addr);
void writeb(u8 v, void __iomem *addr);
void writew(u16 v, void __iomem *addr);
void writel(u32 v, void __iomem *addr);
void udelay(unsigned long us);
void msleep(unsigned int ms);
extern unsigned long jiffies;
#define msecs_to_jiffies(ms) ((unsigned long)(ms))
#define time_before(a, b) ((long)((a) - (b)) < 0)

/* ---- bitmap, mutex, IRQ domains, MSI ---- */
#define DECLARE_BITMAP(name, bits) unsigned long name[((bits) + 63) / 64]
void bitmap_fill(unsigned long *bitmap, unsigned int nbits);
void bitmap_clear(unsigned long *bitmap, unsigned int start, unsigned int nbits);
int bitmap_find_free_region(unsigned long *bitmap, unsigned int bits, int order);
void bitmap_release_region(unsigned long *bitmap, unsigned int pos, int order);
struct mutex { int unused; };
#define mutex_init(m) do { (void)(m); } while (0)
#define mutex_lock(m) do { (void)(m); } while (0)
#define mutex_unlock(m) do { (void)(m); } while (0)
#define upper_32_bits(n) ((u32)(((n) >> 16) >> 16))
#define lower_32_bits(n) ((u32)((n) & 0xffffffffu))

struct fwnode_handle { int unused; };
struct irq_domain;
struct irq_chip;
struct msi_msg { u32 address_lo; u32 address_hi; u32 data; };
struct irq_fwspec { struct fwnode_handle *fwnode; int param_count; u32 param[16]; };
struct irq_data { unsigned long hwirq; void *chip_data; const struct irq_chip *chip; };
struct irq_chip {
	const char *name;
	void (*irq_mask)(struct irq_data *);
	void (*irq_unmask)(struct irq_data *);
	void (*irq_eoi)(struct irq_data *);
	int (*irq_set_affinity)(struct irq_data *, const void *, bool);
	int (*irq_set_type)(struct irq_data *, unsigned int);
	void (*irq_compose_msi_msg)(struct irq_data *, struct msi_msg *);
};
void irq_chip_mask_parent(struct irq_data *d);
void irq_chip_unmask_parent(struct irq_data *d);
void irq_chip_eoi_parent(struct irq_data *d);
int irq_chip_set_affinity_parent(struct irq_data *d, const void *m, bool f);
int irq_chip_set_type_parent(struct irq_data *d, unsigned int t);
struct irq_domain_ops {
	int (*alloc)(struct irq_domain *, unsigned int, unsigned int, void *);
	void (*free)(struct irq_domain *, unsigned int, unsigned int);
};
struct irq_domain { const struct irq_domain_ops *ops; void *host_data; };
struct irq_domain_info {
	struct fwnode_handle *fwnode;
	unsigned int size;
	const struct irq_domain_ops *ops;
	void *host_data;
	struct irq_domain *parent;
};
struct msi_parent_ops {
	unsigned long supported_flags;
	unsigned long required_flags;
	unsigned long chip_flags;
	int bus_select_token;
	bool (*init_dev_msi_info)(struct device *, struct irq_domain *, struct irq_domain *, void *);
};
#define MSI_GENERIC_FLAGS_MASK 0x0fUL
#define MSI_FLAG_USE_DEF_DOM_OPS (1UL << 0)
#define MSI_FLAG_USE_DEF_CHIP_OPS (1UL << 1)
#define MSI_FLAG_PCI_MSI_MASK_PARENT (1UL << 9)
#define MSI_FLAG_MULTI_PCI_MSI (1UL << 20)
#define MSI_FLAG_PCI_MSIX (1UL << 21)
#define MSI_CHIP_FLAG_SET_EOI (1UL << 0)
#define DOMAIN_BUS_WIRED 1
#define DOMAIN_BUS_PCI_MSI 2
bool msi_lib_init_dev_msi_info(struct device *dev, struct irq_domain *domain, struct irq_domain *real_parent, void *info);
struct irq_domain *msi_create_parent_irq_domain(struct irq_domain_info *info, const struct msi_parent_ops *ops);
struct irq_domain *irq_find_matching_fwspec(struct irq_fwspec *fwspec, int bus_token);
int irq_domain_alloc_irqs_parent(struct irq_domain *domain, unsigned int virq, unsigned int nr, void *arg);
void irq_domain_free_irqs_parent(struct irq_domain *domain, unsigned int virq, unsigned int nr);
int irq_domain_set_hwirq_and_chip(struct irq_domain *domain, unsigned int virq, unsigned long hwirq, const struct irq_chip *chip, void *chip_data);
struct irq_data *irq_domain_get_irq_data(struct irq_domain *domain, unsigned int virq);
#define irq_data_get_irq_chip_data(d) ((d)->chip_data)
void irq_domain_remove(struct irq_domain *domain);
struct of_phandle_args { struct device_node *np; int args_count; u32 args[16]; };
bool of_property_read_bool(const struct device_node *np, const char *name);
int of_property_read_u64(const struct device_node *np, const char *name, u64 *out);
int of_property_read_u32_index(const struct device_node *np, const char *name, u32 index, u32 *out);
int of_parse_phandle_with_args(const struct device_node *np, const char *list, const char *cells, int index, struct of_phandle_args *out);
void of_phandle_args_to_fwspec(struct device_node *np, const u32 *args, unsigned int count, struct irq_fwspec *fwspec);
struct fwnode_handle *dev_fwnode(struct device *dev);
void *devm_kzalloc(struct device *dev, size_t size, int gfp);
int devm_add_action_or_reset(struct device *dev, void (*action)(void *), void *data);
#endif
