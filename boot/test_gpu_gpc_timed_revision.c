#include <assert.h>
#include <stdint.h>
#include <stdio.h>

static uint32_t gpc[0x11000 / 4], gpu[0x1000 / 4];
static unsigned writes, polls, reads, mode;
static uint32_t fake_read(const volatile void *p)
{
    if (p == &gpc[0x1000 / 4]) {
        polls++;
        return mode == 1 ? 0x10 : mode == 2 ? 2 : mode == 3 && polls < 4 ? 0x11 : 1;
    }
    assert(p == &gpu[0x20 / 4]);
    reads++;
    return 0x70300;
}
static void fake_write(void *p, uint32_t v)
{
    assert((writes == 0 && p == &gpc[0x10000 / 4] && v == 0xffff0000) ||
           (writes == 1 && p == &gpc[0] && v == 0x40000000) ||
           (writes == 2 && p == &gpc[0x1000 / 4] && v == 0x11));
    writes++;
}
#define MMIO_READ32(p) fake_read(p)
#define MMIO_WRITE32(p, v) fake_write((void *)(p), v)
#define main gpu_probe_main
#include "gpu-gpc-timed-revision.c"
#undef main

int main(void)
{
    uint32_t revision = 0;
    long long elapsed = 0;
    assert(timed_sequence(gpc, gpu, &revision, &elapsed) == 0);
    assert(writes == 3 && polls == 1 && reads == 1 && revision == 0x70300 && elapsed >= 10000);
    writes = polls = reads = 0; mode = 1;
    assert(timed_sequence(gpc, gpu, &revision, &elapsed) == 1);
    assert(writes == 3 && polls == 1000 && reads == 0);
    writes = polls = reads = 0; mode = 2;
    assert(timed_sequence(gpc, gpu, &revision, &elapsed) == 1);
    assert(writes == 3 && polls == 1 && reads == 0);
    writes = polls = reads = 0; mode = 3;
    assert(timed_sequence(gpc, gpu, &revision, &elapsed) == 0);
    assert(writes == 3 && polls == 4 && reads == 1);
    puts("PASS: timed GPC writes, poll gates, delay, and one revision read");
    return 0;
}
