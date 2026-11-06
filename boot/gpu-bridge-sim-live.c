/* Exercise the production bridge protocol using RAM in place of all MMIO. */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
int sim_open(const char *, int, ...);
int sim_close(int);
int sim_mkdir(const char *, mode_t);
void *sim_mmap(void *, size_t, int, int, int, off_t);
int sim_munmap(void *, size_t);
static uint32_t sim_read32(const void *p);
static void sim_write32(void *p, uint32_t value);
#define open sim_open
#define close sim_close
#define mkdir sim_mkdir
#define mmap sim_mmap
#define munmap sim_munmap
#define BRIDGE_READ32(p) sim_read32(p)
#define BRIDGE_WRITE32(p,v) sim_write32(p,v)
#include "gpu-bridge-once.c"
#undef open
#undef close
#undef mkdir
#undef mmap
#undef munmap
static uint32_t gpc[0x2000/4], fabric[0x101000/4];
int sim_open(const char *name, int flags, ...)
{
	if (!strcmp(name, "/dev/mem")) return 9876;
	if (strcmp(name, "/tmp/gfx-bridge-plan.bin") || (flags & O_ACCMODE) != O_RDONLY) return -1;
	return open(name, flags);
}
int sim_close(int fd) { return fd == 9876 ? 0 : close(fd); }
int sim_mkdir(const char *name, mode_t mode)
{
	if (strcmp(name, "/tmp/gpu-bridge-once.once")) return -1;
	return mkdir("/tmp/gpu-bridge-sim-live.once", mode);
}
void *sim_mmap(void *addr, size_t length, int prot, int flags, int fd, off_t offset)
{
	(void)addr;
	if (flags != MAP_SHARED || fd != 9876) return MAP_FAILED;
	if (offset == 0x201e00000ULL && length == sizeof(gpc) && prot == PROT_READ) return gpc;
	if (length != 0x81000 || prot != PROT_WRITE) return MAP_FAILED;
	if (offset == 0x201f00000ULL) return fabric;
	if (offset == 0x201f80000ULL) return fabric + 0x80000/4;
	return MAP_FAILED;
}
int sim_munmap(void *p, size_t n) { (void)p; (void)n; return 0; }
static uint32_t sim_read32(const void *p) { return *(const uint32_t *)p; }
static void sim_write32(void *p, uint32_t value) { *(uint32_t *)p = value; }
