/* Minimal kernel-API stubs for compiling pcie-apple-t7000-bcm-probe.c on the host. Only what
 * the probe may legitimately use exists: anything else (iowrite32, pci_set_master, firmware,
 * DMA) is deliberately undefined so a regression fails to compile. */
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
#define __iomem
#define ENODEV 19
#define EIO 5
#define ENOMEM 12
#define ENOENT 2
#define ERANGE 34
#define EBUSY 16

struct device { const char *name; };
struct pci_dev { struct device dev; };
struct pci_device_id { u32 vendor, device; };
#define PCI_VENDOR_ID_BROADCOM 0x14e4
#define PCI_DEVICE(v, d) .vendor = (v), .device = (d)
struct pci_driver {
	const char *name;
	const struct pci_device_id *id_table;
	int (*probe)(struct pci_dev *, const struct pci_device_id *);
};

#define MODULE_DEVICE_TABLE(a, b)
#define MODULE_DESCRIPTION(x)
#define MODULE_LICENSE(x)
#define module_pci_driver(drv) struct pci_driver *harness_driver = &drv

void harness_log(const char *level, const char *fmt, ...);
#define dev_info(dev, ...) harness_log("INFO", __VA_ARGS__)
#define dev_err(dev, ...) harness_log("ERR", __VA_ARGS__)

int pci_read_config_dword(struct pci_dev *pdev, int where, u32 *val);
int pci_write_config_dword(struct pci_dev *pdev, int where, u32 val);
int pci_enable_device_mem(struct pci_dev *pdev);
void pci_disable_device(struct pci_dev *pdev);
int pci_request_region(struct pci_dev *pdev, int bar, const char *name);
void pci_release_region(struct pci_dev *pdev, int bar);
void *pci_iomap_range(struct pci_dev *pdev, int bar, unsigned long offset, unsigned long maxlen);
void pci_iounmap(struct pci_dev *pdev, void *addr);
u32 ioread32(void *addr);

/* Shadow-capture stubs (patch 0062). The Kconfig symbol is off unless the test passes -D. */
#ifndef CONFIG_PCIE_APPLE_T7000_BCM_PROBE_SHADOW
#define CONFIG_PCIE_APPLE_T7000_BCM_PROBE_SHADOW 0
#endif
#define IS_ENABLED(x) (x)
#define GFP_KERNEL 0
struct dentry;
static inline bool IS_ERR_OR_NULL(const void *p) { return !p || (unsigned long)p >= (unsigned long)-4095; }
struct debugfs_blob_wrapper { void *data; unsigned long size; };
struct dentry *debugfs_create_blob(const char *name, unsigned short mode, struct dentry *parent,
				   struct debugfs_blob_wrapper *blob);
void *kmalloc_array(size_t n, size_t size, int flags);
void kfree(const void *p);
u32 crc32_le(u32 crc, const u8 *p, size_t len);
u16 ioread16(void *addr);
