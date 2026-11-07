/* One-shot J81 GPC-gated revision read; the core window can still hang. */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

static int read32(const void *map, unsigned off, const char *name,
		  unsigned long long addr, uint32_t *value)
{
	char reply[16];
	if (printf("stage=before-%s address=0x%llx width=32\n", name, addr) < 0 ||
	    fflush(stdout) == EOF || !fgets(reply, sizeof(reply), stdin) ||
	    strcmp(reply, "READ\n")) return 1;
	*value = *(volatile const uint32_t *)((const char *)map + off);
	__sync_synchronize();
	return printf("stage=after-%s raw=0x%08x\n", name, *value) < 0 || fflush(stdout);
}

int main(int argc, char **argv)
{
	void *pmgr = MAP_FAILED, *gpc = MAP_FAILED, *gpu = MAP_FAILED;
	uint32_t power, state, control, revision;
	int fd, rc = 1;
	(void)argv;
	if (argc != 1 || mkdir("/tmp/gpu-core-revision-once.once", 0700)) return 2;
	fd = open("/dev/mem", O_RDONLY | O_SYNC);
	if (fd < 0) return 1;
	pmgr = mmap(NULL, 0x1000, PROT_READ, MAP_SHARED, fd, 0x20e020000ULL);
	gpc = mmap(NULL, 0x2000, PROT_READ, MAP_SHARED, fd, 0x201e00000ULL);
	gpu = mmap(NULL, 0x1000, PROT_READ, MAP_SHARED, fd, 0x201000000ULL);
	if (pmgr == MAP_FAILED || gpc == MAP_FAILED || gpu == MAP_FAILED) goto out;
	if (read32(pmgr, 0x320, "pmgr-read", 0x20e020320ULL, &power) || power != 0x3ff) goto out;
	if (read32(gpc, 0x1000, "gpc-state", 0x201e01000ULL, &state) || state != 1) goto out;
	if (read32(gpc, 0, "gpc-control", 0x201e00000ULL, &control) || control != 0x40000000) goto out;
	if (read32(gpu, 0x20, "gpu-revision", 0x201000020ULL, &revision) || revision == 0 || revision == UINT32_MAX) goto out;
	rc = 0;
out:
	printf("stage=finished rc=%d\n", rc); fflush(stdout);
	if (gpu != MAP_FAILED) munmap(gpu, 0x1000);
	if (gpc != MAP_FAILED) munmap(gpc, 0x2000);
	if (pmgr != MAP_FAILED) munmap(pmgr, 0x1000);
	close(fd);
	return rc;
}
