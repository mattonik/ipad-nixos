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


/* ---- MSI mode: bitmap, IRQ domain and OF stand-ins ---- */
static bool msi_mode;
static bool dt_msi_controller, dt_msi_doorbell = true, aic_present = true, parent_alloc_fails;
static u32 dt_msi_nvecs = 32;
static struct device_node aic_node = { 7 };
static struct irq_domain aic_domain, msi_domain;
static const struct msi_parent_ops *created_ops;
static struct irq_domain_info created_info;
static void (*devm_action)(void *);
static void *devm_action_data;
static struct irq_data virq_data[256];

void bitmap_fill(unsigned long *b, unsigned int n) { memset(b, 0xff, ((n + 63) / 64) * 8); }
void bitmap_clear(unsigned long *b, unsigned int start, unsigned int n)
{
	for (unsigned int i = start; i < start + n; i++)
		b[i / 64] &= ~(1UL << (i % 64));
}
int bitmap_find_free_region(unsigned long *b, unsigned int bits, int order)
{
	(void)order;   /* the driver only uses order 0 */
	for (unsigned int i = 0; i < bits; i++)
		if (!(b[i / 64] & (1UL << (i % 64)))) {
			b[i / 64] |= 1UL << (i % 64);
			return (int)i;
		}
	return -ENOMEM;
}
void bitmap_release_region(unsigned long *b, unsigned int pos, int order)
{
	(void)order;
	b[pos / 64] &= ~(1UL << (pos % 64));
}
void irq_chip_mask_parent(struct irq_data *d) { (void)d; }
void irq_chip_unmask_parent(struct irq_data *d) { (void)d; }
void irq_chip_eoi_parent(struct irq_data *d) { (void)d; }
int irq_chip_set_affinity_parent(struct irq_data *d, const void *m, bool f) { (void)d; (void)m; (void)f; return 0; }
int irq_chip_set_type_parent(struct irq_data *d, unsigned int t) { (void)d; (void)t; return 0; }
bool msi_lib_init_dev_msi_info(struct device *dev, struct irq_domain *domain, struct irq_domain *rp, void *info) { (void)dev; (void)domain; (void)rp; (void)info; return true; }

bool of_property_read_bool(const struct device_node *np, const char *name) { (void)np; return !strcmp(name, "msi-controller") && dt_msi_controller; }
int of_property_read_u64(const struct device_node *np, const char *name, u64 *out)
{
	(void)np;
	if (strcmp(name, "apple,msi-doorbell") || !dt_msi_doorbell)
		return -EINVAL;
	*out = 0xbffff000ULL;
	return 0;
}
int of_parse_phandle_with_args(const struct device_node *np, const char *list, const char *cells, int index, struct of_phandle_args *out)
{
	(void)np; (void)list; (void)cells; (void)index;
	out->np = &aic_node;
	out->args_count = 3;          /* <AIC_IRQ 224 IRQ_TYPE_EDGE_RISING> */
	out->args[0] = 0;
	out->args[1] = 224;
	out->args[2] = 1;
	return 0;
}
int of_property_read_u32_index(const struct device_node *np, const char *name, u32 index, u32 *out) { (void)np; (void)name; (void)index; *out = dt_msi_nvecs; return 0; }
void of_phandle_args_to_fwspec(struct device_node *np, const u32 *args, unsigned int count, struct irq_fwspec *fw)
{
	(void)np;
	fw->param_count = (int)count;
	for (unsigned int i = 0; i < count; i++)
		fw->param[i] = args[i];
}
struct fwnode_handle *dev_fwnode(struct device *dev) { static struct fwnode_handle h; (void)dev; return &h; }
void *devm_kzalloc(struct device *dev, size_t size, int gfp) { (void)dev; (void)gfp; return calloc(1, size); }
int devm_add_action_or_reset(struct device *dev, void (*action)(void *), void *data)
{
	(void)dev;
	devm_action = action;
	devm_action_data = data;
	fprintf(trace_out, "DEVM_ACTION registered\n");
	return 0;
}
struct irq_domain *irq_find_matching_fwspec(struct irq_fwspec *fw, int token)
{
	fprintf(trace_out, "FIND_PARENT token=%d line=%u\n", token, fw->param[1]);
	return aic_present ? &aic_domain : NULL;
}
struct irq_domain *msi_create_parent_irq_domain(struct irq_domain_info *info, const struct msi_parent_ops *ops)
{
	created_info = *info;
	created_ops = ops;
	msi_domain.ops = info->ops;
	msi_domain.host_data = info->host_data;
	fprintf(trace_out, "MSI_DOMAIN create size=%u parent=%s supported=0x%lx required=0x%lx chip_flags=0x%lx token=%d\n",
		info->size, info->parent == &aic_domain ? "aic" : "?", ops->supported_flags, ops->required_flags,
		ops->chip_flags, ops->bus_select_token);
	return &msi_domain;
}
void irq_domain_remove(struct irq_domain *d) { fprintf(trace_out, "DOMAIN_REMOVE %s\n", d == &msi_domain ? "msi" : "?"); }
int irq_domain_alloc_irqs_parent(struct irq_domain *d, unsigned int virq, unsigned int nr, void *arg)
{
	struct irq_fwspec *fw = arg;

	(void)d; (void)nr;
	if (parent_alloc_fails) {
		fprintf(trace_out, "PARENT_ALLOC virq=%u line=%u -> fail\n", virq, fw->param[1]);
		return -EIO;
	}
	fprintf(trace_out, "PARENT_ALLOC virq=%u type=%u line=%u flags=%u\n", virq, fw->param[0], fw->param[1], fw->param[2]);
	return 0;
}
void irq_domain_free_irqs_parent(struct irq_domain *d, unsigned int virq, unsigned int nr) { (void)d; (void)nr; fprintf(trace_out, "PARENT_FREE virq=%u\n", virq); }
int irq_domain_set_hwirq_and_chip(struct irq_domain *d, unsigned int virq, unsigned long hwirq, const struct irq_chip *chip, void *data)
{
	(void)d;
	virq_data[virq].hwirq = hwirq;
	virq_data[virq].chip = chip;
	virq_data[virq].chip_data = data;
	fprintf(trace_out, "SET_HWIRQ virq=%u slot=%lu chip=%s\n", virq, hwirq, chip->name);
	return 0;
}
struct irq_data *irq_domain_get_irq_data(struct irq_domain *d, unsigned int virq) { (void)d; return &virq_data[virq]; }

int pci_host_common_init(struct platform_device *pdev, struct pci_host_bridge *b, const struct pci_ecam_ops *ops)
{
	struct region *ecam = add_region("ecam", 0x300000000ULL, 0x10000);
	struct pci_config_window cfg = { .win = ecam->mem, .parent = &pdev->dev };
	u8 *dev1 = ecam->mem + 0x8000;      /* bus 0, device 1, function 0 */

	if (msi_mode)
		fprintf(trace_out, "HOST_INIT\n");
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

static void exercise_domain(void)
{
	struct irq_domain *d = &msi_domain;
	int ret;

	for (unsigned int i = 0; i < 9; i++) {
		ret = d->ops->alloc(d, 100 + i, 1, NULL);
		fprintf(trace_out, "ALLOC virq=%u -> %d\n", 100 + i, ret);
	}
	{
		struct msi_msg msg = { 0, 0, 0 };

		virq_data[103].chip->irq_compose_msi_msg(&virq_data[103], &msg);
		fprintf(trace_out, "COMPOSE virq=103 hi=0x%08x lo=0x%08x data=%u\n", msg.address_hi, msg.address_lo, msg.data);
	}
	d->ops->free(d, 103, 1);
	ret = d->ops->alloc(d, 120, 1, NULL);
	fprintf(trace_out, "REALLOC virq=120 -> %d (expect the freed slot)\n", ret);
	ret = d->ops->alloc(d, 121, 2, NULL);
	fprintf(trace_out, "ALLOC two-vector -> %d (multi-MSI must be refused)\n", ret);
	d->ops->free(d, 100, 1);
	parent_alloc_fails = true;
	ret = d->ops->alloc(d, 122, 1, NULL);
	fprintf(trace_out, "ALLOC with parent failure -> %d\n", ret);
	parent_alloc_fails = false;
	ret = d->ops->alloc(d, 123, 1, NULL);
	fprintf(trace_out, "ALLOC after failure -> %d (slot must have been returned)\n", ret);
	if (devm_action)
		devm_action(devm_action_data);
}

static int msi_scenarios(void)
{
	int rc = 0;

	msi_mode = true;
	dt_msi_controller = true;
	rc |= run_scenario("msi/board", true, false);
	exercise_domain();

	devm_action = NULL;
	aic_present = false;
	rc |= run_scenario("msi/no-aic-defers", true, false) == -EPROBE_DEFER ? 0 : 1;
	aic_present = true;
	dt_msi_nvecs = 16;
	rc |= run_scenario("msi/wrong-vector-count", true, false) == -EINVAL ? 0 : 1;
	dt_msi_nvecs = 32;
	dt_msi_doorbell = false;
	rc |= run_scenario("msi/no-doorbell", true, false) == -EINVAL ? 0 : 1;
	dt_msi_doorbell = true;
	dt_msi_controller = false;
	rc |= run_scenario("msi/not-declared", true, false);
	return rc;
}

int main(int argc, char **argv)
{
	trace_out = stdout;
	if (argc > 1 && !strcmp(argv[1], "msi"))
		return msi_scenarios();
	int rc = 0;

	rc |= run_scenario("j81-reg-on/zeros", true, false);
	rc |= run_scenario("generic-no-reg-on/zeros", false, false);
	rc |= run_scenario("j81-reg-on/ones", true, true);
	rc |= run_scenario("generic-no-reg-on/ones", false, true);
	return rc ? 1 : 0;
}
