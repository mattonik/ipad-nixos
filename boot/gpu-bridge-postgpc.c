/* One-shot post-GPC bridge readback; no RGX access and no writes. */
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
	void *gpc = MAP_FAILED, *bridge = MAP_FAILED;
	uint32_t state, control, b18, b1c;
	int fd, rc = 1;
	(void)argv;
	if (argc != 1 || mkdir("/tmp/gpu-bridge-postgpc.once", 0700)) return 2;
	fd = open("/dev/mem", O_RDONLY | O_SYNC);
	if (fd < 0) return 1;
	gpc = mmap(NULL, 0x2000, PROT_READ, MAP_SHARED, fd, 0x201e00000ULL);
	bridge = mmap(NULL, 0x1000, PROT_READ, MAP_SHARED, fd, 0x201f00000ULL);
	if (gpc == MAP_FAILED || bridge == MAP_FAILED) goto out;
	if (read32(gpc, 0x1000, "gpc-state", 0x201e01000ULL, &state) || state != 1) goto out;
	if (read32(gpc, 0, "gpc-control", 0x201e00000ULL, &control) || control & (1U << 29)) goto out;
	if (read32(bridge, 0x18, "bridge-18", 0x201f00018ULL, &b18)) goto out;
	if (read32(bridge, 0x1c, "bridge-1c", 0x201f0001cULL, &b1c)) goto out;
	(void)b18; (void)b1c;
	rc = 0;
out:
	printf("stage=finished rc=%d\n", rc); fflush(stdout);
	if (bridge != MAP_FAILED) munmap(bridge, 0x1000);
	if (gpc != MAP_FAILED) munmap(gpc, 0x2000);
	close(fd);
	return rc;
}
