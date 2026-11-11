/*
 * Switch named J81 PMGR power states back on, one at a time, each with a
 * host acknowledgment. The allowlist is exactly the set of domains that were
 * on when Linux started and that Linux switched off about 0.7 s into the
 * boot (genpd active_time about 685 ms, no consumer), measured 2026-11-11.
 *
 * Touches only the listed power-state words in the PMGR page 0x20e020000.
 * Never accesses the GPU, GPC, the GFX bridges, PMGR page 5, the perf block,
 * the voltage manager or the DWI block. The write is the one pmgr-dwi-on
 * uses: read the word, set the target nibble to 0xf, poll the actual nibble.
 */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#define PS_PAGE 0x20e020000ULL

static const struct {
	const char *name;
	unsigned int offset;
} domains[] = {
	{ "dwi", 0x120 },	   { "i2c1", 0x168 },	   { "i2c2", 0x170 },
	{ "i2c3", 0x178 },	   { "uart1", 0x1a8 },	   { "uart2", 0x1b0 },
	{ "uart4", 0x1c0 },	   { "uart6", 0x1d0 },	   { "uart7", 0x1d8 },
	{ "uart8", 0x1e0 },	   { "ispsens0", 0x210 },  { "ispsens1", 0x218 },
	{ "usb2host0", 0x258 },	   { "usb2host1", 0x268 }, { "usb2host2", 0x278 },
	{ "disp1_busmux", 0x2c0 }, { "isp", 0x2d0 },	   { "media", 0x2d8 },
	{ "venc", 0x300 },	   { "pcie_aux", 0x310 },
};
#define NDOMAINS (sizeof(domains) / sizeof(domains[0]))
#define MAX_ARGS 32

static int ack(const char *want)
{
	char reply[16];

	return fgets(reply, sizeof(reply), stdin) && strcmp(reply, want) == 0;
}

static int lookup(const char *name)
{
	unsigned int i;

	for (i = 0; i < NDOMAINS; i++)
		if (strcmp(name, domains[i].name) == 0)
			return (int)i;
	return -1;
}

static int is_on(uint32_t v)
{
	return (v & 0xf) == 0xf && ((v >> 4) & 0xf) == 0xf;
}

int main(int argc, char **argv)
{
	const struct timespec ms = { 0, 1000000 };
	int which[MAX_ARGS], count = argc - 1, fd, i, j, n, rc = 1;
	volatile uint32_t *ps;
	uint32_t v;
	void *map;

	if (count < 1 || count > MAX_ARGS) {
		fprintf(stderr, "usage: pmgr-ps-restore <domain>...\n");
		return 2;
	}
	for (i = 0; i < count; i++) {
		which[i] = lookup(argv[i + 1]);
		if (which[i] < 0) {
			fprintf(stderr, "not in the allowlist: %s\n", argv[i + 1]);
			return 2;
		}
		for (j = 0; j < i; j++)
			if (which[j] == which[i]) {
				fprintf(stderr, "listed twice: %s\n", argv[i + 1]);
				return 2;
			}
	}
	fd = open("/dev/mem", O_RDWR | O_SYNC);
	if (fd < 0) {
		perror("open /dev/mem");
		return 1;
	}
	map = mmap(NULL, 0x1000, PROT_READ | PROT_WRITE, MAP_SHARED, fd, PS_PAGE);
	if (map == MAP_FAILED) {
		perror("mmap PMGR");
		close(fd);
		return 1;
	}
	if (printf("stage=before-ps-read count=%d\n", count) < 0 ||
	    fflush(stdout) == EOF || !ack("READ\n"))
		goto out;
	for (i = 0; i < count; i++) {
		ps = (volatile uint32_t *)((char *)map + domains[which[i]].offset);
		printf("stage=ps-read name=%s address=0x%llx raw=0x%08x\n",
		       domains[which[i]].name,
		       PS_PAGE + domains[which[i]].offset, *ps);
	}
	fflush(stdout);
	for (i = 0; i < count; i++) {
		ps = (volatile uint32_t *)((char *)map + domains[which[i]].offset);
		v = *ps;
		if (is_on(v)) {
			printf("result=already-on name=%s raw=0x%08x\n",
			       domains[which[i]].name, v);
			continue;
		}
		if (printf("stage=before-ps-write name=%s address=0x%llx raw=0x%08x set=0xf\n",
			   domains[which[i]].name,
			   PS_PAGE + domains[which[i]].offset, v) < 0 ||
		    fflush(stdout) == EOF || !ack("WRITE\n"))
			goto out;
		*ps = v | 0xf;
		for (n = 0; n < 100; n++) {
			v = *ps;
			if (((v >> 4) & 0xf) == 0xf)
				break;
			nanosleep(&ms, NULL);
		}
		printf("result=%s name=%s raw=0x%08x polls=%d\n",
		       ((v >> 4) & 0xf) == 0xf ? "on" : "not-on",
		       domains[which[i]].name, v, n);
		fflush(stdout);
		if (((v >> 4) & 0xf) != 0xf)
			goto out; /* stop at the first domain that does not follow */
	}
	puts("result=all-on");
	rc = 0;
out:
	fflush(stdout);
	munmap(map, 0x1000);
	close(fd);
	return rc;
}
