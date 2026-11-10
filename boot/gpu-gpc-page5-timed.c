/* J81 GPC setup and one existing page-5 sysfs read, supervised as one batch. */
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
#define MMIO_READ32(p) (*(volatile const uint32_t *)(p))
#define MMIO_WRITE32(p, v) (*(volatile uint32_t *)(p) = (v))
#endif
#ifndef PAGE5_READ
#define PAGE5_READ(fd, buf, size) read((fd), (buf), (size))
#endif

static int sequence(void *gpc, int page5_fd)
{
    volatile uint32_t *r = gpc;
    uint32_t state, value;
    unsigned i;
    char result[128], expected[128], tail;
    ssize_t n;
    struct timespec before, after, delay;
    if (puts("checkpoint=before-gpc-writes") == EOF || fflush(stdout)) return 1;
    MMIO_WRITE32(r + 0x10000 / 4, 0xffff0000); __sync_synchronize();
    MMIO_WRITE32(r, 0x40000000); __sync_synchronize();
    MMIO_WRITE32(r + 0x1000 / 4, 0x11); __sync_synchronize();
    if (puts("checkpoint=before-gpc-poll") == EOF || fflush(stdout)) return 1;
    for (i = 0; i < 1000; i++) {
        state = MMIO_READ32(r + 0x1000 / 4); __sync_synchronize();
        if (!(state & 0x10)) break;
        delay = (struct timespec){0, 10000};
        while (nanosleep(&delay, &delay)) if (errno != EINTR) return 1;
    }
    if (i == 1000 || (state & 0x1f) != 1) {
        printf("checkpoint=gpc-poll-failed raw=0x%08x polls=%u\n", state, i == 1000 ? i : i + 1);
        fflush(stdout);
        return 1;
    }
    if (clock_gettime(CLOCK_MONOTONIC, &before)) return 1;
    if (puts("checkpoint=before-page5-read") == EOF || fflush(stdout)) return 1;
    n = PAGE5_READ(page5_fd, result, sizeof(result) - 1);
    if (clock_gettime(CLOCK_MONOTONIC, &after) || n <= 0) return 1;
    result[n] = 0;
    if (sscanf(result, "address=0x20e005004 value=0x%8x%c", &value, &tail) != 2 || tail != '\n') return 1;
    if (snprintf(expected, sizeof(expected), "address=0x20e005004 value=0x%08x\n", value) < 0 || strcmp(result, expected)) return 1;
    if (printf("checkpoint=gpc-poll-ok raw=0x%08x polls=%u\n", state, i + 1) < 0 ||
        printf("checkpoint=poll-to-sysfs-return-ns value=%lld\n", (long long)(after.tv_sec - before.tv_sec) * 1000000000LL + after.tv_nsec - before.tv_nsec) < 0 ||
        printf("stage=after-gpc-page5 address=0x20e005004 value=0x%08x\n", value) < 0 || fflush(stdout)) return 1;
    return 0;
}

int main(int argc, char **argv)
{
    void *gpc = MAP_FAILED;
    uint32_t state;
    int mem = -1, page5 = -1, rc = 1;
    char reply[16];
    (void)argv;
    if (argc != 1 || mkdir("/tmp/gpu-gpc-page5-timed.once", 0700)) return 2;
    mem = open("/dev/mem", O_RDWR | O_SYNC);
    page5 = open("/sys/devices/j81-page5-read-once/read_once", O_RDONLY | O_CLOEXEC);
    if (mem < 0 || page5 < 0) goto out;
    gpc = mmap(NULL, 0x11000, PROT_READ | PROT_WRITE, MAP_SHARED, mem, 0x201e00000ULL);
    if (gpc == MAP_FAILED) goto out;
    if (puts("stage=before-gpc-state address=0x201e01000 width=32") == EOF || fflush(stdout) ||
        !fgets(reply, sizeof(reply), stdin) || strcmp(reply, "READ\n")) goto out;
    state = MMIO_READ32((char *)gpc + 0x1000); __sync_synchronize();
    if (printf("stage=after-gpc-state raw=0x%08x\n", state) < 0 || fflush(stdout) || state != 0) goto out;
    if (puts("stage=before-gpc-page5 address=0x20e005004 width=32") == EOF || fflush(stdout) ||
        !fgets(reply, sizeof(reply), stdin) || strcmp(reply, "READ\n")) goto out;
    if (sequence(gpc, page5)) goto out;
    rc = 0;
out:
    printf("stage=finished rc=%d\n", rc); fflush(stdout);
    if (gpc != MAP_FAILED) munmap(gpc, 0x11000);
    if (page5 >= 0) close(page5);
    if (mem >= 0) close(mem);
    return rc;
}
