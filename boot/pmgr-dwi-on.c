/*
 * Switch the J81 PMGR "dwi" power state on, once, with host acknowledgment.
 * Touches only the PMGR power-state word 0x20e020120. Never accesses the
 * GPU, GPC, the GFX bridges, PMGR page 5, the perf block or the DWI block.
 */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#define PS_PAGE 0x20e020000ULL
#define DWI_PS 0x120

static int ack(const char *want)
{
	char reply[16];

	return fgets(reply, sizeof(reply), stdin) && strcmp(reply, want) == 0;
}

static void show(const char *stage, uint32_t v)
{
	printf("stage=%s raw=0x%08x target=%u actual=%u\n", stage, v, v & 0xf,
	       (v >> 4) & 0xf);
	fflush(stdout);
}

int main(int argc, char **argv)
{
	const struct timespec ms = { 0, 1000000 };
	volatile uint32_t *ps;
	uint32_t v;
	void *map;
	int fd, n, rc = 1;

	(void)argv;
	if (argc != 1) {
		fprintf(stderr, "usage: pmgr-dwi-on\n");
		return 2;
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
	ps = (volatile uint32_t *)((char *)map + DWI_PS);
	if (puts("stage=before-dwi-read address=0x20e020120 width=32") == EOF ||
	    fflush(stdout) == EOF || !ack("READ\n"))
		goto out;
	v = *ps;
	show("after-dwi-read", v);
	if ((v & 0xf) == 0xf && ((v >> 4) & 0xf) == 0xf) {
		puts("result=already-on");
		rc = 0;
		goto out;
	}
	if (puts("stage=before-dwi-write address=0x20e020120 set=0xf") == EOF ||
	    fflush(stdout) == EOF || !ack("WRITE\n"))
		goto out;
	*ps = v | 0xf;
	for (n = 0; n < 100; n++) {
		v = *ps;
		if (((v >> 4) & 0xf) == 0xf)
			break;
		nanosleep(&ms, NULL);
	}
	show("after-dwi-write", v);
	printf("result=%s polls=%d\n", ((v >> 4) & 0xf) == 0xf ? "on" : "not-on", n);
	rc = ((v >> 4) & 0xf) == 0xf ? 0 : 1;
out:
	fflush(stdout);
	munmap(map, 0x1000);
	close(fd);
	return rc;
}
