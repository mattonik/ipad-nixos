/* Host harness: runs the REAL pcie-apple-t7000-bcm-probe.c probe against a fake BCM4350 and
 * prints every device access. Scenarios inject unsupported chips/revisions and failures. */
#include "prelude.h"
#include <stdarg.h>
#include <stdlib.h>
#include DRIVER_SOURCE

struct scenario {
	const char *name;
	u32 win0;			/* initial BAR0 window register */
	u32 chipid, eromptr, caps, otplayout, srom;
	u32 erom[8];			/* words at eromptr */
	bool reject_window;		/* config write to 0x80 is ignored */
	bool fail_enable, fail_region;
};

#define CID(rev, id) (((u32)(rev) << 16) | (id))
#define CIA(part) (((u32)(part) << 8) | 0x1)
#define CIB(rev) ((u32)(rev) << 24)
#define EROM_PTR 0x180ff000u

static struct scenario sc[] = {
	{ "ok-rev48-chipcommon", 0x18000000, CID(2, 0x4350), EROM_PTR, 0x00080000, 0x00010000, 0x31, { 0, CIA(0x800), CIB(48) } },
	{ "ok-rev49-gci", 0x18000000, CID(2, 0x4350), EROM_PTR, 0x00080000, 0x00010000, 0x20, { CIA(0x800), CIB(49) } },
	{ "ok-rev51-chipcommon", 0x18000000, CID(2, 0x4350), EROM_PTR, 0x00080000, 0x00010000, 0x30, { CIA(0x800), CIB(51) } },
	{ "stop-rev43", 0x18000000, CID(2, 0x4350), EROM_PTR, 0x00080000, 0x00010000, 0x30, { CIA(0x800), CIB(43) } },
	{ "stop-chip-4354", 0x18000000, CID(2, 0x4354), EROM_PTR, 0, 0, 0, { CIA(0x800), CIB(48) } },
	{ "stop-chipid-allones", 0x18000000, 0xffffffff, 0xffffffff },
	{ "stop-window-rejected", 0x18100000, CID(2, 0x4350), EROM_PTR, 0, 0, 0, { CIA(0x800), CIB(48) }, true },
	{ "stop-eromptr-range", 0x18000000, CID(2, 0x4350), 0x10000000, 0, 0, 0, { CIA(0x800), CIB(48) } },
	{ "stop-first-component-not-cc", 0x18000000, CID(2, 0x4350), EROM_PTR, 0, 0, 0, { CIA(0x812), CIB(48) } },
	{ "stop-no-component", 0x18000000, CID(2, 0x4350), EROM_PTR, 0, 0, 0, { 0, 0, 0, 0, 0, 0, 0, 0 } },
	{ "stop-wrap-not-40nm", 0x18000000, CID(2, 0x4350), EROM_PTR, 0x00080000, 0x00020000, 0x30, { CIA(0x800), CIB(48) } },
	{ "restore-nondefault-window", 0x1810a000, CID(2, 0x4350), EROM_PTR, 0x00080000, 0x00010000, 0x31, { CIA(0x800), CIB(48) } },
	{ "fail-enable", 0x18000000, CID(2, 0x4350), EROM_PTR, 0, 0, 0, { CIA(0x800), CIB(48) }, false, true },
	{ "fail-region", 0x18000000, CID(2, 0x4350), EROM_PTR, 0, 0, 0, { CIA(0x800), CIB(48) }, false, false, true },
};

static struct scenario *cur;
static u32 win;
static char fake_bar[0x1000];
static int violations;

void harness_log(const char *level, const char *fmt, ...)
{
	va_list ap;
	printf("LOG %s ", level);
	va_start(ap, fmt);
	vprintf(fmt, ap);
	va_end(ap);
}

int pci_read_config_dword(struct pci_dev *pdev, int where, u32 *val)
{
	if (where != 0x80) { printf("VIOLATION config read of 0x%x\n", where); violations++; *val = 0; return 0; }
	*val = win;
	printf("CFGR 0x80 -> 0x%08x\n", win);
	return 0;
}

int pci_write_config_dword(struct pci_dev *pdev, int where, u32 val)
{
	if (where != 0x80) { printf("VIOLATION config write of 0x%x\n", where); violations++; return 0; }
	printf("CFGW 0x80 <- 0x%08x%s\n", val, cur->reject_window && val != cur->win0 ? " (ignored)" : "");
	if (!cur->reject_window)
		win = val;
	return 0;
}

int pci_enable_device_mem(struct pci_dev *pdev)
{
	printf("ENABLE_MEM%s\n", cur->fail_enable ? " (fails)" : "");
	return cur->fail_enable ? -EIO : 0;
}
void pci_disable_device(struct pci_dev *pdev) { printf("DISABLE\n"); }
int pci_request_region(struct pci_dev *pdev, int bar, const char *name)
{
	printf("REQUEST_REGION %d%s\n", bar, cur->fail_region ? " (fails)" : "");
	return cur->fail_region ? -EBUSY : 0;
}
void pci_release_region(struct pci_dev *pdev, int bar) { printf("RELEASE_REGION %d\n", bar); }
void *pci_iomap_range(struct pci_dev *pdev, int bar, unsigned long offset, unsigned long maxlen)
{
	printf("IOMAP bar=%d off=0x%lx len=0x%lx\n", bar, offset, maxlen);
	return maxlen <= sizeof(fake_bar) ? fake_bar : NULL;
}
void pci_iounmap(struct pci_dev *pdev, void *addr) { printf("IOUNMAP\n"); }

u32 ioread32(void *addr)
{
	unsigned off = (unsigned)((char *)addr - fake_bar), v = 0xdeadbeef;
	if (off >= sizeof(fake_bar)) { printf("VIOLATION read past the mapped window 0x%x\n", off); violations++; return 0; }
	if (win == 0x18000000) {
		switch (off) {
		case BCM_CC_CHIPID: v = cur->chipid; break;
		case BCM_CC_EROMPTR: v = cur->eromptr; break;
		case BCM_CC_CAPABILITIES: v = cur->caps; break;
		case BCM_CC_OTPLAYOUT: v = cur->otplayout; break;
		case BCM_CC_SROMCONTROL: v = cur->srom; break;
		default: printf("VIOLATION unexpected ChipCommon read at 0x%x\n", off); violations++; v = 0; break;
		}
	} else if (win == (cur->eromptr & ~0xfffu)) {
		unsigned base = cur->eromptr & 0xfff, idx = (off - base) / 4;
		if (off < base || idx >= 8) { printf("VIOLATION EROM read outside the scanned words 0x%x\n", off); violations++; v = 0; }
		else v = cur->erom[idx];
	} else {
		printf("VIOLATION read in unexpected window 0x%08x off 0x%x\n", win, off);
		violations++;
		v = 0;
	}
	printf("RD win=0x%08x off=0x%03x -> 0x%08x\n", win, off, v);
	return v;
}

int main(int argc, char **argv)
{
	int failed = 0;
	for (size_t i = 0; i < sizeof(sc) / sizeof(sc[0]); i++) {
		struct pci_dev pdev = { { "0000:01:00.0" } };
		cur = &sc[i];
		win = cur->win0;
		violations = 0;
		printf("== scenario %s\n", cur->name);
		int ret = harness_driver->probe(&pdev, &harness_driver->id_table[0]);
		printf("PROBE_RET %d\nFINAL_WINDOW 0x%08x INITIAL 0x%08x\nVIOLATIONS %d\n", ret, win, cur->win0, violations);
		/* The window register is restored unless the fake refused every write (then it never moved). */
		if (ret != -ENODEV || violations || win != cur->win0)
			failed = 1;
	}
	return failed;
}
