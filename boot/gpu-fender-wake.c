/* One-shot post-PMGR-cycle Fender wake experiment; never touches RGX. */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#ifndef FENDER_READ32
#define FENDER_READ32(address) (*(volatile const uint32_t *)(address))
#define FENDER_WRITE32(address, value) (*(volatile uint32_t *)(address) = (value))
#endif

static int access_reg(void *map, const char *name, unsigned offset, int write,
                      uint32_t *value)
{
	char reply[16];
	volatile uint32_t *address = (volatile uint32_t *)((char *)map + offset);
	if (printf("stage=before-%s address=0x%llx op=%s value=0x%08x\n", name,
	           0x201e00000ULL + offset, write ? "write" : "read", *value) < 0 ||
	    fflush(stdout) == EOF)
		return 1;
	if (!fgets(reply, sizeof(reply), stdin) || strcmp(reply, "ACCESS\n") != 0)
		return 1;
	if (write) FENDER_WRITE32(address, *value); else *value = FENDER_READ32(address);
	__sync_synchronize();
	if (printf("stage=after-%s value=0x%08x\n", name, *value) < 0 || fflush(stdout) == EOF)
		return 1;
	return 0;
}

static int poll_state(void *map, const char *prefix, int want_zero, unsigned limit)
{
	char name[32]; uint32_t value;
	for (unsigned i = 0; i < limit; i++) {
		if (snprintf(name, sizeof(name), "%s-%02u", prefix, i) < 0) return 1;
		value = 0;
		if (access_reg(map, name, 0x1000, 0, &value)) return 1;
		if (want_zero ? value == 0 : (value & 0x10) == 0) return 0;
	}
	fprintf(stderr, "%s poll limit reached; state unknown\n", prefix); return 1;
}

int main(int argc, char **argv)
{
	int fd, rc = 1; uint32_t value; void *map; (void)argv;
	if (argc != 1) { fprintf(stderr, "usage: gpu-fender-wake\n"); return 2; }
	if (mkdir("/tmp/gpu-fender-wake.once", 0700) != 0) { perror("one-shot guard"); return 1; }
	fd = open("/dev/mem", O_RDWR | O_SYNC);
	if (fd < 0) { perror("open /dev/mem"); return 1; }
	map = mmap(NULL, 0x21000, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0x201e00000ULL);
	if (map == MAP_FAILED) { perror("mmap Fender"); close(fd); return 1; }
	value = 0;
	if (access_reg(map, "initial-state", 0x1000, 0, &value) || value != 0) goto out;
	value = 0;
	if (access_reg(map, "reset", 0x20000, 1, &value) || poll_state(map, "reset-clear", 0, 64)) goto out;
	value = 0x10;
	if (access_reg(map, "reset-state", 0x1000, 1, &value) || poll_state(map, "reset-zero", 1, 64)) goto out;
	value = 0x20;
	if (access_reg(map, "hold", 0x20000, 1, &value)) goto out;
	value = 0;
	if (access_reg(map, "hold-confirm", 0x20000, 0, &value) || value != 0x20) goto out;
	value = 0xffff0000;
	if (access_reg(map, "setup-mask", 0x10000, 1, &value)) goto out;
	value = 0x40000000;
	if (access_reg(map, "setup-control", 0, 1, &value)) goto out;
	value = 0x11;
	if (access_reg(map, "request-state", 0x1000, 1, &value) || poll_state(map, "wake", 0, 64)) goto out;
	rc = 0;
out:
	printf("stage=finished rc=%d\n", rc); fflush(stdout); munmap(map, 0x21000); close(fd); return rc;
}
