/* One-shot legacy GPU ID reads; read-only MMIO can still hang the bus. */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#ifndef GPU_READ32
#define GPU_READ32(address) (*(volatile const uint32_t *)(address))
#endif

static int read_reg(const void *map, const char *name, uint64_t base,
                    unsigned offset, uint32_t *value)
{
	char reply[16];
	if (printf("stage=before-%s address=0x%llx width=32\n", name,
	           (unsigned long long)(base + offset)) < 0 || fflush(stdout) == EOF)
		return 1;
	if (!fgets(reply, sizeof(reply), stdin) || strcmp(reply, "READ\n") != 0)
		return 1;
	*value = GPU_READ32((const char *)map + offset);
	__sync_synchronize();
	if (printf("stage=after-%s raw=0x%08x\n", name, *value) < 0 || fflush(stdout) == EOF)
		return 1;
	return 0;
}

int main(int argc, char **argv)
{
	int fd, rc = 1;
	void *gpc, *gpu;
	uint32_t state, control, revision, core;
	(void)argv;
	if (argc != 1) { fprintf(stderr, "usage: gpu-id-once\n"); return 2; }
	if (mkdir("/tmp/gpu-id-once.once", 0700) != 0) { perror("one-shot guard"); return 1; }
	fd = open("/dev/mem", O_RDONLY | O_SYNC);
	if (fd < 0) { perror("open /dev/mem"); return 1; }
	gpc = mmap(NULL, 0x2000, PROT_READ, MAP_SHARED, fd, 0x201e00000ULL);
	if (gpc == MAP_FAILED) { perror("mmap GPC"); close(fd); return 1; }
	gpu = mmap(NULL, 0x1000, PROT_READ, MAP_SHARED, fd, 0x201000000ULL);
	if (gpu == MAP_FAILED) { perror("mmap GPU"); munmap(gpc, 0x2000); close(fd); return 1; }
	if (read_reg(gpc,"gpc-state",0x201e00000ULL,0x1000,&state) || (state & 0x1f) != 1)
		goto out;
	if (read_reg(gpc,"gpc-control",0x201e00000ULL,0,&control) || (control & (1U << 29)))
		goto out;
	if (read_reg(gpu,"gpu-revision",0x201000000ULL,0x20,&revision) ||
	    revision == 0 || revision == UINT32_MAX) goto out;
	if (read_reg(gpu,"gpu-core-id",0x201000000ULL,0x18,&core)) goto out;
	rc = 0;
out:
	printf("stage=finished rc=%d\n", rc);
	fflush(stdout);
	munmap(gpu, 0x1000);
	munmap(gpc, 0x2000);
	close(fd);
	return rc;
}
