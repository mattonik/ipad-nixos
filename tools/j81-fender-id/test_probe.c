#include "probe.h"

#include <assert.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>

static void expected_fault(int sig)
{
    _exit(sig == SIGBUS || sig == SIGSEGV ? 42 : 1);
}

int main(void)
{
    size_t bytes = (size_t)getpagesize();
    uint32_t *pages = mmap(NULL, 3 * bytes, PROT_READ | PROT_WRITE,
                           MAP_PRIVATE | MAP_ANON, -1, 0);
    volatile struct j81_sample *r = mmap(NULL, bytes, PROT_READ | PROT_WRITE,
                                         MAP_SHARED | MAP_ANON, -1, 0);
    uint32_t *blocked = mmap(NULL, bytes, PROT_NONE, MAP_PRIVATE | MAP_ANON, -1, 0);
    assert(pages != MAP_FAILED && (void *)r != MAP_FAILED && blocked != MAP_FAILED);
    uint32_t *fender = pages + bytes / sizeof(*pages);
    uint32_t *core = fender + bytes / sizeof(*pages);

    j81_sample_fender_id(blocked, NULL, blocked, r);
    assert(r->stage == J81_MISSING_MAP);
    pages[1] = 0x20000001;
    j81_sample_fender_id(pages, blocked, blocked, r);
    assert(r->stage == J81_PAGE5_READ && r->page5 == 0x20000001);
    assert(r->fender == 0 && r->gpu_id == 0);

    pages[1] |= 1u << 30;
    for (unsigned bit = 0; bit <= 1; ++bit) {
        assert(mprotect(pages, 3 * bytes, PROT_READ | PROT_WRITE) == 0);
        fender[0] = 0x40001234u | (bit << 29);
        core[8] = bit ? 0 : 0x00070500;
        assert(mprotect(pages, 3 * bytes, PROT_READ) == 0);
        j81_sample_fender_id(pages, fender, core, r);
        assert(r->stage == J81_ID_READ && r->page5 == pages[1]);
        assert(r->fender == fender[0] && r->gpu_id == core[8]);
    }

    pid_t pid = fork();
    assert(pid >= 0);
    if (pid == 0) {
        signal(SIGBUS, expected_fault);
        signal(SIGSEGV, expected_fault);
        j81_sample_fender_id(pages, fender, blocked, r);
        _exit(1);
    }
    int status;
    assert(waitpid(pid, &status, 0) == pid);
    assert(WIFEXITED(status) && WEXITSTATUS(status) == 42);
    assert(r->stage == J81_FENDER_READ && r->fender == fender[0]);
    assert(r->page5 == pages[1] && r->gpu_id == 0);
    puts("PASS: missing map, closed gate, bit 29 clear/set, zero ID, pre-ID fault checkpoint");
    return 0;
}
