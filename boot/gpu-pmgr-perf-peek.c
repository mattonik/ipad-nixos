/*
 * Read only the J81 GFX perf-state block and the GFX PMGR state word.
 * Never touches RGX, GPC, the GFX bridges, Fender or the MCC.
 *
 *   0x20e01c000 + n*0x10, n = 0..15   GFX perf-state table (LLB writes it)
 *   0x20e01c004 + n*0x10, n = 0..15   second word of each perf-state entry
 *   0x20e01c200                       GFX perf-state control (LLB sets bit 31)
 *   0x20e01c300                       LLB tunable word (LLB writes 0x40000001)
 *   0x20e020320                       GFX PMGR power state (read in test4)
 */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#define PERF_BASE 0x20e01c000ULL
#define PS_BASE 0x20e020000ULL
#define PAGE 0x1000

static uint32_t rd(const void *map, unsigned off)
{
	return *(volatile const uint32_t *)((const char *)map + off);
}

int main(int argc, char **argv)
{
	int fd, rc = 1;
	void *perf, *ps = MAP_FAILED;
	char reply[16];
	unsigned n;

	(void)argv;
	if (argc != 1) {
		fprintf(stderr, "usage: gpu-pmgr-perf-peek\n");
		return 2;
	}
	fd = open("/dev/mem", O_RDONLY | O_SYNC);
	if (fd < 0) {
		perror("open /dev/mem");
		return 1;
	}
	perf = mmap(NULL, PAGE, PROT_READ, MAP_SHARED, fd, PERF_BASE);
	if (perf == MAP_FAILED) {
		perror("mmap PMGR perf");
		goto out_fd;
	}
	ps = mmap(NULL, PAGE, PROT_READ, MAP_SHARED, fd, PS_BASE);
	if (ps == MAP_FAILED) {
		perror("mmap PMGR ps");
		goto out_perf;
	}
	if (puts("stage=before-perf-read base=0x20e01c000 words=34 ps=0x20e020320") == EOF ||
	    fflush(stdout) == EOF)
		goto out_ps;
	if (!fgets(reply, sizeof(reply), stdin) || strcmp(reply, "READ\n") != 0)
		goto out_ps;
	printf("ps raw=0x%08x\n", rd(ps, 0x320));
	fflush(stdout);
	printf("ctl raw=0x%08x\n", rd(perf, 0x200));
	fflush(stdout);
	for (n = 0; n < 16; n++) {
		printf("perf%02u raw=0x%08x\n", n, rd(perf, n * 0x10));
		fflush(stdout);
	}
	for (n = 0; n < 16; n++) {
		printf("perf%02u+4 raw=0x%08x\n", n, rd(perf, n * 0x10 + 4));
		fflush(stdout);
	}
	printf("w300 raw=0x%08x\n", rd(perf, 0x300));
	fflush(stdout);
	puts("stage=after-perf-read");
	fflush(stdout);
	rc = 0;
out_ps:
	munmap(ps, PAGE);
out_perf:
	munmap(perf, PAGE);
out_fd:
	close(fd);
	return rc;
}
