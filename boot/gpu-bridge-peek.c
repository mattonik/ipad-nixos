/* One checkpointed 32-bit bridge read; reads may have undocumented effects. */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

static int read_word(void *map, unsigned offset, const char *name, unsigned long long address, uint32_t *value)
{
	char reply[16];
	if (printf("stage=before-%s address=0x%llx op=read value=0x00000000\n", name, address) < 0 ||
	    fflush(stdout) || !fgets(reply, sizeof(reply), stdin) || strcmp(reply, "ACCESS\n")) return 1;
	*value = *(volatile const uint32_t *)((const char *)map + offset);
	__sync_synchronize();
	return printf("stage=after-%s value=0x%08x\n", name, *value) < 0 || fflush(stdout);
}

int main(int argc, char **argv)
{
	void *gpc = MAP_FAILED, *bridge = MAP_FAILED;
	uint32_t state, value;
	int fd, rc = 1;
	(void)argv;
	if (argc != 1) return 2;
	if (mkdir("/tmp/gpu-bridge-peek.once", 0700)) return 1;
	fd = open("/dev/mem", O_RDONLY | O_SYNC);
	if (fd < 0) return 1;
	gpc = mmap(NULL, 0x2000, PROT_READ, MAP_SHARED, fd, 0x201e00000ULL);
	if (gpc == MAP_FAILED) goto out;
	bridge = mmap(NULL, 0x1000, PROT_READ, MAP_SHARED, fd, 0x201f00000ULL);
	if (bridge == MAP_FAILED) goto out;
	if (read_word(gpc, 0x1000, "gpc-state", 0x201e01000ULL, &state) || state != 0) goto out;
	if (read_word(bridge, 0x18, "bridge-peek", 0x201f00018ULL, &value)) goto out;
	rc = 0;
out:
	printf("stage=finished rc=%d\n", rc); fflush(stdout);
	if (bridge != MAP_FAILED) munmap(bridge, 0x1000);
	if (gpc != MAP_FAILED) munmap(gpc, 0x2000);
	close(fd);
	return rc;
}
