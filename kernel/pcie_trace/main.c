/*
 * Host harness: compiles the real pcie-apple-t7000.c (DRIVER_SOURCE) into this
 * translation unit, runs apple_t7000_pcie_probe() against fake registers, and
 * prints every write and delay in order. Two scenarios: board with the J81 REG_ON
 * resource, and a generic node without it.
 */
#include "prelude.h"
#include DRIVER_SOURCE

FILE *trace_out;
unsigned long jiffies;

#define NREG 4
static struct region { const char *name; u64 phys; u8 *mem; size_t size; } regions[NREG + 1];
static int nregions;
static bool have_reg_on_prop;
static bool fill_ones;   /* registers read back as all ones, so RMW masks are visible */
static unsigned int pmu_0403 = 0x09;

static struct region *find_region(const void *addr, size_t *off)
{
	for (int i = 0; i < nregions; i++)
		if ((const u8 *)addr >= regions[i].mem && (const u8 *)addr < regions[i].mem + regions[i].size) {
			*off = (const u8 *)addr - regions[i].mem;
			return &regions[i];
		}
	return NULL;
}

static struct region *add_region(const char *name, u64 phys, size_t size)
{
	struct region *r = &regions[nregions++];

	r->name = name; r->phys = phys; r->size = size; r->mem = calloc(1, size);
	if (fill_ones)
		memset(r->mem, 0xff, size);
	return r;
}

void trace_event(const char *fmt, ...) { (void)fmt; }
void pcie_trace_log(const void *dev, const char *fmt, ...) { (void)dev; (void)fmt; }

static void trace(const char *kind, const void *addr, unsigned long long v)
{
	size_t off = 0;
	struct region *r = find_region(addr, &off);

	fprintf(trace_out, "%s %s+0x%05zx 0x%08llx\n", kind, r ? r->name : "?", off, v);
}

u8 readb(const void __iomem *a) { size_t o; struct region *r = find_region(a, &o); u8 v = r ? r->mem[o] : 0; trace("R8 ", a, v); return v; }
u16 readw(const void __iomem *a) { size_t o; struct region *r = find_region(a, &o); u16 v = 0; if (r) memcpy(&v, r->mem + o, 2); trace("R16", a, v); return v; }
u32 readl(const void __iomem *a) { size_t o; struct region *r = find_region(a, &o); u32 v = 0; if (r) memcpy(&v, r->mem + o, 4); trace("R32", a, v); return v; }
void writeb(u8 v, void __iomem *a) { size_t o; struct region *r = find_region(a, &o); trace("W8 ", a, v); if (r) r->mem[o] = v; }
void writew(u16 v, void __iomem *a) { size_t o; struct region *r = find_region(a, &o); trace("W16", a, v); if (r) memcpy(r->mem + o, &v, 2); }
void writel(u32 v, void __iomem *a) { size_t o; struct region *r = find_region(a, &o); trace("W32", a, v); if (r) memcpy(r->mem + o, &v, 4); }
void udelay(unsigned long us) { fprintf(trace_out, "UDELAY %lu\n", us); }
void msleep(unsigned int ms) { fprintf(trace_out, "MSLEEP %u\n", ms); jiffies += ms; }

int of_address_to_resource(struct device_node *np, int index, struct resource *res)
{
	(void)np;
	res->start = 0x100000000ULL + (u64)index * 0x100000;
	res->end = res->start + 0x3fff;
	return 0;
}
static void __iomem *window_for(u64 start, u64 size)
{
	for (int i = 0; i < nregions; i++)
		if (regions[i].phys == start)
			return regions[i].mem;
	char *name = malloc(24);
	snprintf(name, 24, "win%llx", (unsigned long long)((start - 0x100000000ULL) >> 20));
	return add_region(name, start, size < 0x1000 ? 0x1000 : size)->mem;
}
void __iomem *devm_ioremap_resource(struct device *d, struct resource *r) { (void)d; return window_for(r->start, resource_size(r)); }
void __iomem *devm_ioremap(struct device *d, u64 s, u64 sz) { (void)d; return window_for(s, sz); }

static struct device_node pmic_node = { 1 };
static struct i2c_client pmic_client;
static struct regmap pmic_map;
bool of_property_present(const struct device_node *np, const char *n) { (void)np; (void)n; return have_reg_on_prop; }
struct device_node *of_parse_phandle(const struct device_node *np, const char *n, int i) { (void)np; (void)n; (void)i; return &pmic_node; }
struct i2c_client *of_find_i2c_device_by_node(struct device_node *np) { (void)np; return &pmic_client; }
struct regmap *dev_get_regmap(struct device *d, const char *n) { (void)d; (void)n; return &pmic_map; }
int regmap_read(struct regmap *m, unsigned int reg, unsigned int *v) { (void)m; *v = reg == 0x0403 ? pmu_0403 : 0xff; return 0; }
int regmap_write(struct regmap *m, unsigned int reg, unsigned int v)
{
	(void)m;
	fprintf(trace_out, "PMU_W 0x%04x 0x%02x\n", reg, v);
	if (reg == 0x0403)
		pmu_0403 = v;
	return 0;
}

static struct pci_host_bridge bridge;
static struct pci_host_port port;
static struct pci_host_perst perst;
static struct gpio_desc perst_gpio = { 1 };
void *pci_ecam_map_bus(void *a, unsigned int b, unsigned int c) { (void)a; (void)b; (void)c; return NULL; }
int pci_generic_config_read(void) { return 0; }
int pci_generic_config_write(void) { return 0; }
struct pci_host_bridge *devm_pci_alloc_host_bridge(struct device *d, size_t p) { (void)d; (void)p; return &bridge; }
int pci_host_common_parse_ports(struct device *d, struct pci_host_bridge *b) { (void)d; (void)b; return 0; }
int gpiod_direction_output(struct gpio_desc *d, int v) { (void)d; fprintf(trace_out, "GPIO_OUT %d\n", v); return 0; }

int pci_host_common_init(struct platform_device *pdev, struct pci_host_bridge *b, const struct pci_ecam_ops *ops)
{
	struct region *ecam = add_region("ecam", 0x300000000ULL, 0x10000);
	struct pci_config_window cfg = { .win = ecam->mem, .parent = &pdev->dev };
	u8 *dev1 = ecam->mem + 0x8000;      /* bus 0, device 1, function 0 */

	pdev->drvdata = b;
	/* Root-port config space: capability list -> PCI Express cap at 0x70. */
	dev1[0x34] = 0x70;
	dev1[0x70] = 0x10; dev1[0x71] = 0x00;
	if (!fill_ones) {
		u32 lnkcap = 1U << 20; memcpy(dev1 + 0x70 + 0x0c, &lnkcap, 4);     /* DLLLARC */
		u32 lnkcap2 = 1U << 1; memcpy(dev1 + 0x70 + 0x2c, &lnkcap2, 4);    /* Gen1 supported */
		u16 lnksta = 1U << 13; memcpy(dev1 + 0x70 + 0x12, &lnksta, 2);     /* DLLLA */
	}   /* all-ones mode already has DLLARC, Gen1-supported and DLLLA set */
	return ops->init(&cfg);
}

static int run_scenario(const char *name, bool reg_on, bool ones)
{
	struct platform_device pdev;
	struct device_node node = { 0 };
	int ret;

	nregions = 0;
	have_reg_on_prop = reg_on;
	fill_ones = ones;
	pmu_0403 = 0x09;
	memset(&pdev, 0, sizeof(pdev));
	pdev.dev.of_node = &node;
	bridge.ports.next = bridge.ports.prev = &port.list;
	port.list.next = port.list.prev = &bridge.ports;
	port.perst.next = port.perst.prev = &perst.list;
	perst.list.next = perst.list.prev = &port.perst;
	perst.desc = &perst_gpio;
	fprintf(trace_out, "== scenario %s\n", name);
	ret = apple_t7000_pcie_probe(&pdev);
	fprintf(trace_out, "== probe returned %d\n", ret);
	return ret;
}

int main(int argc, char **argv)
{
	(void)argc; (void)argv;
	trace_out = stdout;
	int rc = 0;

	rc |= run_scenario("j81-reg-on/zeros", true, false);
	rc |= run_scenario("generic-no-reg-on/zeros", false, false);
	rc |= run_scenario("j81-reg-on/ones", true, true);
	rc |= run_scenario("generic-no-reg-on/ones", false, true);
	return rc ? 1 : 0;
}
