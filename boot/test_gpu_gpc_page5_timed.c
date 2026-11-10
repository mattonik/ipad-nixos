#include <assert.h>
#include <stdint.h>
#include <string.h>
static uint32_t gpc[0x11000 / 4];
static unsigned writes, polls, reads, mode;
static uint32_t fake_read(const volatile void *p) {
    assert(p == &gpc[0x1000 / 4]); polls++;
    return mode == 1 ? 0x10 : mode == 2 ? 2 : mode == 3 && polls < 4 ? 0x11 : 1;
}
static void fake_write(void *p, uint32_t v) {
    assert((writes == 0 && p == &gpc[0x10000 / 4] && v == 0xffff0000) ||
           (writes == 1 && p == &gpc[0] && v == 0x40000000) ||
           (writes == 2 && p == &gpc[0x1000 / 4] && v == 0x11)); writes++;
}
static long fake_page5(int fd, char *buf, unsigned long size) {
    const char *s = mode == 4 ? "address=0x20e005004 value=garbage\n" : "address=0x20e005004 value=0x40000000\n";
    assert(fd == 7 && size >= strlen(s)); reads++; memcpy(buf, s, strlen(s)); return (long)strlen(s);
}
#define MMIO_READ32(p) fake_read(p)
#define MMIO_WRITE32(p,v) fake_write((void *)(p),v)
#define PAGE5_READ(fd,buf,size) fake_page5(fd,buf,size)
#define main probe_main
#include "gpu-gpc-page5-timed.c"
#undef main
int main(void) {
    assert(sequence(gpc, 7) == 0 && writes == 3 && polls == 1 && reads == 1);
    writes = polls = reads = 0; mode = 1; assert(sequence(gpc, 7) == 1 && polls == 1000 && reads == 0);
    writes = polls = reads = 0; mode = 2; assert(sequence(gpc, 7) == 1 && polls == 1 && reads == 0);
    writes = polls = reads = 0; mode = 3;
    struct timespec start, end;
    assert(clock_gettime(CLOCK_MONOTONIC, &start) == 0);
    assert(sequence(gpc, 7) == 0 && polls == 4 && reads == 1);
    assert(clock_gettime(CLOCK_MONOTONIC, &end) == 0);
    assert((end.tv_sec - start.tv_sec) * 1000000000LL + end.tv_nsec - start.tv_nsec >= 30000);
    writes = polls = reads = 0; mode = 4; assert(sequence(gpc, 7) == 1 && reads == 1);
    puts("PASS: GPC order, poll gates and one page-5 read"); return 0;
}
