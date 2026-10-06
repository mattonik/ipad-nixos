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
	bool fail_kmalloc, fail_debugfs, otp_allones;	/* shadow-capture scenarios (patch 0062) */
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

#ifdef HARNESS_SHADOW
#define J81CAPS 0x58680009u	/* OTP size encoding 5 -> 384 words */
#define J81OTPL 0x10115200u
static struct scenario sc_shadow[] = {
	{ "shadow-j81-enc5-384", 0x18003000, CID(5, 0x4350), 0x1810d000, J81CAPS, J81OTPL, 0x32, { CIA(0x800), CIB(47) } },
	{ "shadow-enc7-512", 0x18000000, CID(2, 0x4350), EROM_PTR, 7u << 19, 0x00010000, 0x30, { CIA(0x800), CIB(48) } },
	{ "shadow-enc0-refused", 0x18000000, CID(2, 0x4350), EROM_PTR, 0, 0x00010000, 0x30, { CIA(0x800), CIB(48) } },
	{ "shadow-srom-present-refused", 0x18000000, CID(2, 0x4350), EROM_PTR, 5u << 19, 0x00010000, 0x31, { CIA(0x800), CIB(48) } },
	{ "shadow-otpsel-clear-refused", 0x18000000, CID(2, 0x4350), EROM_PTR, 5u << 19, 0x00010000, 0x20, { CIA(0x800), CIB(48) } },
	{ "shadow-gci-refused", 0x18000000, CID(2, 0x4350), EROM_PTR, 5u << 19, 0x00010000, 0x30, { CIA(0x800), CIB(49) } },
	{ "shadow-kmalloc-fails", 0x18000000, CID(2, 0x4350), EROM_PTR, 5u << 19, 0x00010000, 0x30, { CIA(0x800), CIB(48) }, false, false, false, true },
	{ "shadow-debugfs-fails", 0x18000000, CID(2, 0x4350), EROM_PTR, 5u << 19, 0x00010000, 0x30, { CIA(0x800), CIB(48) }, false, false, false, false, true },
	{ "shadow-device-returns-allones", 0x18000000, CID(2, 0x4350), EROM_PTR, 5u << 19, 0x00010000, 0x30, { CIA(0x800), CIB(48) }, false, false, false, false, false, true },
};
#endif

static struct scenario *cur;
static int rd16_n, rd16_contig, allocs, frees, kept;
static unsigned rd16_first, rd16_last;
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

u16 ioread16(void *addr)
{
	unsigned off = (unsigned)((char *)addr - fake_bar);
	if (win != 0x18000000 || off < 0x800 || off >= 0xc00 || (off & 1)) {
		printf("VIOLATION 16-bit read outside the ChipCommon shadow: win=0x%08x off=0x%x\n", win, off);
		violations++;
		return 0;
	}
	if (rd16_n == 0) { rd16_first = off; rd16_contig = 1; }
	else if (off != rd16_last + 2) rd16_contig = 0;
	rd16_last = off;
	rd16_n++;
	/* Distinctive fake data: 0xBEEx. It must never appear in the log. */
	return cur->otp_allones ? 0xffff : (u16)(0xBEE0 + (((off - 0x800) / 2) & 0xf));
}

void *kmalloc_array(size_t n, size_t size, int flags)
{
	if (cur->fail_kmalloc) { printf("KMALLOC fails\n"); return NULL; }
	allocs++;
	printf("KMALLOC %zu bytes\n", n * size);
	return malloc(n * size);
}
void kfree(const void *p) { frees++; printf("KFREE\n"); free((void *)p); }

u32 crc32_le(u32 crc, const u8 *p, size_t len)
{
	while (len--) {
		crc ^= *p++;
		for (int k = 0; k < 8; k++)
			crc = (crc >> 1) ^ (0xedb88320u & -(crc & 1));
	}
	return crc;
}

struct dentry *debugfs_create_blob(const char *name, unsigned short mode, struct dentry *parent,
				   struct debugfs_blob_wrapper *blob)
{
	if (cur->fail_debugfs) { printf("DEBUGFS_BLOB %s fails\n", name); return NULL; }
	kept++;
	printf("DEBUGFS_BLOB name=%s mode=%o size=%lu crc=0x%08x\n", name, mode, blob->size,
	       crc32_le(~0u, blob->data, blob->size));
	return (struct dentry *)1;
}

int main(int argc, char **argv)
{
	int failed = 0;
	size_t nbase = sizeof(sc) / sizeof(sc[0]);
#ifdef HARNESS_SHADOW
	size_t nall = nbase + sizeof(sc_shadow) / sizeof(sc_shadow[0]);
#else
	size_t nall = nbase;
#endif
	for (size_t i = 0; i < nall; i++) {
		struct pci_dev pdev = { { "0000:01:00.0" } };
#ifdef HARNESS_SHADOW
		cur = i < nbase ? &sc[i] : &sc_shadow[i - nbase];
#else
		cur = &sc[i];
#endif
		win = cur->win0;
		violations = rd16_n = allocs = frees = kept = 0;
		printf("== scenario %s\n", cur->name);
		int ret = harness_driver->probe(&pdev, &harness_driver->id_table[0]);
		printf("RD16 count=%d first=0x%03x last=0x%03x contiguous=%d\n", rd16_n, rd16_first, rd16_last, rd16_contig);
		printf("ALLOC allocs=%d frees=%d kept=%d\n", allocs, frees, kept);
		printf("PROBE_RET %d\nFINAL_WINDOW 0x%08x INITIAL 0x%08x\nVIOLATIONS %d\n", ret, win, cur->win0, violations);
		/* The window register is restored unless the fake refused every write (then it never moved). */
		if (ret != -ENODEV || violations || win != cur->win0)
			failed = 1;
	}
	return failed;
}
