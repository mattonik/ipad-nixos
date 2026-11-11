/*
 * Read-only sample of J81 PMGR words named on the command line.
 * Offsets are relative to PMGR region 0 (0x20e000000), 4-byte aligned,
 * below 0x40000, at most 64 per run. The two DWI configuration words at
 * 0x200000 and 0x200004 are also accepted; they must only be read while the
 * dwi power state is on. Maps /dev/mem read-only and never writes. Never
 * touches the GPU, GPC or the GFX bridges.
 */
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#define PMGR_BASE 0x20e000000ULL
#define PMGR_SIZE 0x40000UL
#define DWI_CFG 0x200000UL
#define MAX_WORDS 64
#define PAGE 0x1000UL

int main(int argc, char **argv)
{
	unsigned long off[MAX_WORDS];
	char reply[16], *end;
	void *map;
	int fd, i, n = argc - 1;

	if (n < 1 || n > MAX_WORDS) {
		fprintf(stderr, "usage: pmgr-words-peek <hex-offset>... (1..%d)\n", MAX_WORDS);
		return 2;
	}
	for (i = 0; i < n; i++) {
		errno = 0;
		off[i] = strtoul(argv[i + 1], &end, 16);
		if (errno || end == argv[i + 1] || *end || (off[i] & 3) ||
		    (off[i] >= PMGR_SIZE && off[i] != DWI_CFG && off[i] != DWI_CFG + 4)) {
			fprintf(stderr, "bad offset: %s\n", argv[i + 1]);
			return 2;
		}
	}
	fd = open("/dev/mem", O_RDONLY | O_SYNC);
	if (fd < 0) {
		perror("open /dev/mem");
		return 1;
	}
	printf("stage=before-pmgr-words-read base=0x20e000000 words=%d\n", n);
	if (fflush(stdout) == EOF || !fgets(reply, sizeof(reply), stdin) ||
	    strcmp(reply, "READ\n") != 0) {
		close(fd);
		return 1;
	}
	for (i = 0; i < n; i++) {
		map = mmap(NULL, PAGE, PROT_READ, MAP_SHARED, fd,
			   (off_t)(PMGR_BASE + (off[i] & ~(PAGE - 1))));
		if (map == MAP_FAILED) {
			perror("mmap PMGR");
			close(fd);
			return 1;
		}
		printf("w 0x%06lx raw=0x%08x\n", off[i],
		       *(volatile const uint32_t *)((const char *)map + (off[i] & (PAGE - 1))));
		fflush(stdout);
		munmap(map, PAGE);
	}
	puts("stage=after-pmgr-words-read");
	fflush(stdout);
	close(fd);
	return 0;
}
