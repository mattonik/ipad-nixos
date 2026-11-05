/* J81 bridge replay prototype: no automatic rollback after any MMIO. */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#ifndef BRIDGE_READ32
#define BRIDGE_READ32(address) (*(volatile const uint32_t *)(address))
#define BRIDGE_WRITE32(address, value) (*(volatile uint32_t *)(address) = (value))
#endif

struct pair { uint32_t offset, value; };
static int checkpoint(const char *name, uint64_t address, const char *op, uint32_t value)
{
	char reply[16];
	if (printf("stage=before-%s address=0x%llx op=%s value=0x%08x\n", name,
	           (unsigned long long)address, op, value) < 0 || fflush(stdout) == EOF)
		return 1;
	return !fgets(reply, sizeof(reply), stdin) || strcmp(reply, "ACCESS\n") != 0;
}

int main(int argc, char **argv)
{
	struct pair tables[2][33];
	char name[32];
	unsigned t, i;
	int fd, input, rc = 1;
	uint32_t state;
	void *gpc = MAP_FAILED, *bridge[2] = { MAP_FAILED, MAP_FAILED };
	const uint64_t bases[2] = { 0x201f00000ULL, 0x201f80000ULL };
	(void)argv;
	if (argc != 1) { fprintf(stderr, "usage: gpu-bridge-once\n"); return 2; }
	input = open("/tmp/gfx-bridge-plan.bin", O_RDONLY);
	if (input < 0) { perror("open bridge plan"); return 1; }
	if (read(input, tables, sizeof(tables)) != (ssize_t)sizeof(tables) ||
	    read(input, name, 1) != 0) { close(input); return 1; }
	close(input);
	for (t = 0; t < 2; t++)
		for (i = 0; i < 33; i++)
			if (tables[t][i].offset != (i ? 0x40000 + (i - 1) * 4 : 0x18))
				return 1;
	if (mkdir("/tmp/gpu-bridge-once.once", 0700) != 0) { perror("one-shot guard"); return 1; }
	fd = open("/dev/mem", O_RDWR | O_SYNC);
	if (fd < 0) { perror("open /dev/mem"); return 1; }
	gpc = mmap(NULL, 0x2000, PROT_READ, MAP_SHARED, fd, 0x201e00000ULL);
	if (gpc == MAP_FAILED) goto out;
	for (t = 0; t < 2; t++) {
		bridge[t] = mmap(NULL, 0x81000, PROT_WRITE, MAP_SHARED, fd, (off_t)bases[t]);
		if (bridge[t] == MAP_FAILED) goto out;
	}
	if (checkpoint("gpc-state", 0x201e01000ULL, "read", 0)) goto out;
	state = BRIDGE_READ32((const char *)gpc + 0x1000);
	__sync_synchronize();
	if (printf("stage=after-gpc-state value=0x%08x\n", state) < 0 || fflush(stdout) == EOF || state != 0)
		goto out;
	for (t = 0; t < 2; t++) {
		for (i = 0; i < 33; i++) {
			if (snprintf(name, sizeof(name), "bridge-%u-%02u", t + 9, i) < 0) goto out;
			if (checkpoint(name, bases[t] + tables[t][i].offset, "write", tables[t][i].value)) goto out;
			BRIDGE_WRITE32((char *)bridge[t] + tables[t][i].offset, tables[t][i].value);
			__sync_synchronize();
			if (printf("stage=after-%s value=0x%08x\n", name, tables[t][i].value) < 0 || fflush(stdout) == EOF)
				goto out;
		}
	}
	rc = 0;
out:
	printf("stage=finished rc=%d\n", rc);
	fflush(stdout);
	for (t = 0; t < 2; t++) if (bridge[t] != MAP_FAILED) munmap(bridge[t], 0x81000);
	if (gpc != MAP_FAILED) munmap(gpc, 0x2000);
	close(fd);
	return rc;
}
