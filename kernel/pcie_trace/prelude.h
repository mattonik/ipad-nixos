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
#define EINVAL 22
#define ENOMEM 12
#define EIO 5
#define ENODEV 19
#define EPROBE_DEFER 517
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
#endif
