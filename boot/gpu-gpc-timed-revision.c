/* One GPC init and timed core read; the core access may hang the bus. */
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#ifndef MMIO_READ32
#define MMIO_READ32(address) (*(volatile const uint32_t *)(address))
#define MMIO_WRITE32(address, value) (*(volatile uint32_t *)(address) = (value))
#endif

static int timed_sequence(void *gpc, const void *gpu, uint32_t *revision,
                          long long *elapsed)
{
    volatile uint32_t *regs = gpc;
    uint32_t value;
    struct timespec start, now, delay = {0, 10000};
    struct timespec poll_delay;
    unsigned i;
    puts("checkpoint=before-gpc-writes"); fflush(stdout);
    MMIO_WRITE32(regs + 0x10000 / 4, 0xffff0000); __sync_synchronize();
    MMIO_WRITE32(regs, 0x40000000); __sync_synchronize();
    MMIO_WRITE32(regs + 0x1000 / 4, 0x11); __sync_synchronize();
    puts("checkpoint=before-gpc-poll"); fflush(stdout);
    for (i = 0; i < 1000; i++) {
        value = MMIO_READ32(regs + 0x1000 / 4); __sync_synchronize();
        if (!(value & 0x10)) break;
        poll_delay = (struct timespec){0, 10000};
        while (nanosleep(&poll_delay, &poll_delay)) if (errno != EINTR) return 1;
    }
    if (i == 1000 || (value & 0xf) != 1) {
        printf("checkpoint=gpc-poll-failed raw=0x%08x polls=%u\n", value,
               i == 1000 ? i : i + 1);
        fflush(stdout);
        return 1;
    }
    if (clock_gettime(CLOCK_MONOTONIC, &start)) return 1;
    if (printf("checkpoint=gpc-poll-ok raw=0x%08x polls=%u\n", value, i + 1) < 0 ||
        puts("checkpoint=before-gpu-revision") == EOF || fflush(stdout) == EOF) return 1;
    while (nanosleep(&delay, &delay)) if (errno != EINTR) return 1;
    if (clock_gettime(CLOCK_MONOTONIC, &now)) return 1;
    /* Checkpoints use the supervisor pipe without waiting for host acknowledgement. */
    *revision = MMIO_READ32((const char *)gpu + 0x20);
    __sync_synchronize();
    *elapsed = (long long)(now.tv_sec - start.tv_sec) * 1000000000LL + now.tv_nsec - start.tv_nsec;
    return 0;
}

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
    uint32_t value, revision;
    long long elapsed;
    char reply[16];
    int fd, rc = 1;
    (void)argv;
    if (argc != 1 || mkdir("/tmp/gpu-gpc-timed-revision.once", 0700)) return 2;
    fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd < 0) return 1;
    pmgr = mmap(NULL, 0x1000, PROT_READ, MAP_SHARED, fd, 0x20e020000ULL);
    gpc = mmap(NULL, 0x11000, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0x201e00000ULL);
    gpu = mmap(NULL, 0x1000, PROT_READ, MAP_SHARED, fd, 0x201000000ULL);
    if (pmgr == MAP_FAILED || gpc == MAP_FAILED || gpu == MAP_FAILED) goto out;
    if (read32(pmgr, 0x320, "pmgr-read", 0x20e020320ULL, &value) || value != 0x3ff) goto out;
    if (read32(gpc, 0x1000, "gpc-state", 0x201e01000ULL, &value) || value != 0) goto out;
    if (puts("stage=before-timed-sequence address=0x201000020 width=32") == EOF ||
        fflush(stdout) == EOF || !fgets(reply, sizeof(reply), stdin) || strcmp(reply, "READ\n")) goto out;
    if (timed_sequence(gpc, gpu, &revision, &elapsed)) goto out;
    printf("checkpoint=gpc-poll-to-read-ns value=%lld\n", elapsed);
    if (printf("stage=after-timed-sequence raw=0x%08x\n", revision) < 0 || fflush(stdout) ||
        revision == 0 || revision == UINT32_MAX) goto out;
    rc = 0;
out:
    printf("stage=finished rc=%d\n", rc); fflush(stdout);
    if (gpu != MAP_FAILED) munmap(gpu, 0x1000);
    if (gpc != MAP_FAILED) munmap(gpc, 0x11000);
    if (pmgr != MAP_FAILED) munmap(pmgr, 0x1000);
    close(fd);
    return rc;
}
