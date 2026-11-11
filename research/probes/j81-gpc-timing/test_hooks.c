#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

unsigned char test_buffer[4096] __attribute__((aligned(16)));
uint64_t test_thread = 0x1234, ticks;
extern void test_start(void *);
static uint32_t *nested_gpc;
static int trigger_nested;
uint64_t fake_timer(void) { ticks += 50; if (trigger_nested) { trigger_nested = 0; test_start(nested_gpc); } return ticks; }
extern unsigned test_finish(void);
extern uint64_t test_flags_start(void *), test_flags_finish(void);
#define U32(o) (*(uint32_t *)(test_buffer + (o)))
#define U64(o) (*(uint64_t *)(test_buffer + (o)))

int main(void) {
    uint32_t gpc[1025] = {0};
    U64(3616) = test_thread;
    assert(test_finish() == 10 && U32(3636) == 0);
    test_start(gpc);
    assert(gpc[1024] == 0x11 && U32(3640) == 1);
    assert(test_finish() == 10 && U32(3636) == 1 && U32(3632) == 50);
    test_start(gpc);
    assert(U32(3636) == 0 && U32(3640) == 2);
    memset(test_buffer, 0, sizeof(test_buffer));
    U64(3616) = test_thread + 1;
    test_start(gpc);
    assert(gpc[1024] == 0x11 && U32(3640) == 0);
    assert(test_finish() == 10 && U32(3636) == 0);
    memset(test_buffer, 0, sizeof(test_buffer));
    U64(3616) = test_thread;
    test_start(gpc);
    test_start(gpc);
    assert(test_finish() == 10 && U32(3640) == 2 && U32(3636) == 0);
    memset(test_buffer, 0, sizeof(test_buffer));
    U64(3616) = test_thread;
    test_start(gpc);
    nested_gpc = gpc; trigger_nested = 1;
    assert(test_finish() == 10 && U32(3640) == 2 && U32(3636) == 0);
    memset(test_buffer, 0, sizeof(test_buffer));
    U64(3616) = test_thread;
    assert(test_flags_start(gpc) == 0xa0000000 && test_flags_finish() == 0xa0000000);
    puts("PASS: request store, elapsed ticks, skipped path, thread and reentry guards");
}
