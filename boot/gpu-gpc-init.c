/* Experimental GPC state-1 request; no GPU-core access or automatic rollback. */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#ifndef GPC_READ32
#define GPC_READ32(address) (*(volatile const uint32_t *)(address))
#define GPC_WRITE32(address, value) (*(volatile uint32_t *)(address) = (value))
#endif

static int access_reg(void *map, const char *name, unsigned offset,
                      int write, uint32_t *value)
{
	char reply[16];
	volatile uint32_t *address = (volatile uint32_t *)((char *)map + offset);

	if (printf("stage=before-%s address=0x%llx op=%s value=0x%08x\n", name,
	           0x201e00000ULL + offset, write ? "write" : "read", *value) < 0 ||
	    fflush(stdout) == EOF)
		return 1;
	if (!fgets(reply, sizeof(reply), stdin) || strcmp(reply, "ACCESS\n") != 0)
		return 1;
	if (write)
		GPC_WRITE32(address, *value);
	else
		*value = GPC_READ32(address);
	__sync_synchronize();
	if (printf("stage=after-%s value=0x%08x\n", name, *value) < 0 ||
	    fflush(stdout) == EOF)
		return 1;
	return 0;
}

int main(int argc, char **argv)
{
	int fd, rc = 1;
	unsigned i;
	uint32_t value = 0;
	void *map;
	char name[32];

	(void)argv;
	if (argc != 1) {
		fprintf(stderr, "usage: gpu-gpc-init\n");
		return 2;
	}
	if (mkdir("/tmp/gpu-gpc-init.once", 0700) != 0) {
		perror("one-shot guard");
		return 1;
	}
	fd = open("/dev/mem", O_RDWR | O_SYNC);
	if (fd < 0) {
		perror("open /dev/mem");
		return 1;
	}
	map = mmap(NULL, 0x11000, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0x201e00000ULL);
	if (map == MAP_FAILED) {
		perror("mmap GPC");
		close(fd);
		return 1;
	}
	if (access_reg(map, "initial-state", 0x1000, 0, &value) || value != 0)
		goto out;
	value = 0xffff0000;
	if (access_reg(map, "setup-mask", 0x10000, 1, &value)) goto out;
	value = 0x40000000;
	if (access_reg(map, "setup-control", 0, 1, &value)) goto out;
	value = 0x11;
	if (access_reg(map, "request-state", 0x1000, 1, &value)) goto out;
	for (i = 0; i < 64; i++) {
		if (snprintf(name, sizeof(name), "poll-%02u", i) < 0) goto out;
		value = 0;
		if (access_reg(map, name, 0x1000, 0, &value)) goto out;
		if ((value & 0x10) == 0) {
			if ((value & 0xf) == 1) rc = 0;
			goto out;
		}
	}
	fprintf(stderr, "poll limit reached; state unknown\n");
out:
	printf("stage=finished rc=%d\n", rc);
	fflush(stdout);
	munmap(map, 0x11000);
	close(fd);
	return rc;
}
