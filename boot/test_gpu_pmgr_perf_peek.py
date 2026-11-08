#!/usr/bin/env python3
"""Exercise the perf-state probe against fake mappings, with no hardware access."""
import subprocess
import tempfile
from pathlib import Path

source = Path(__file__).with_name("gpu-pmgr-perf-peek.c")
harness = r'''
#define open fake_open
#define close fake_close
#define mmap fake_mmap
#define munmap fake_munmap
#define fgets fake_fgets
#define main peek_main
#include "gpu-pmgr-perf-peek.c"
#undef main
#include <assert.h>
#include <errno.h>
#include <string.h>
static uint32_t perfmem[0x1000 / 4], psmem[0x1000 / 4];
static int opens, maps, unmaps, fail_open, fail_map, allow_read;
char *fake_fgets(char *s, int size, FILE *stream) {
    (void)stream; assert(size >= 6);
    strcpy(s, allow_read ? "READ\n" : "NO\n"); return s;
}
int fake_open(const char *path, int flags, ...) {
    assert(strcmp(path, "/dev/mem") == 0);
    assert((flags & O_ACCMODE) == O_RDONLY && (flags & O_SYNC));
    opens++;
    if (fail_open) { errno = EACCES; return -1; }
    return 7;
}
int fake_close(int fd) { assert(fd == 7); return 0; }
void *fake_mmap(void *addr, size_t length, int prot, int flags, int fd, off_t offset) {
    (void)addr;
    assert(length == 0x1000 && prot == PROT_READ && flags == MAP_SHARED && fd == 7);
    maps++;
    if (fail_map && maps == fail_map) { errno = ENOMEM; return MAP_FAILED; }
    if ((uint64_t)offset == 0x20e01c000ULL) return perfmem;
    assert((uint64_t)offset == 0x20e020000ULL);
    return psmem;
}
int fake_munmap(void *addr, size_t length) {
    assert((addr == perfmem || addr == psmem) && length == 0x1000);
    unmaps++; return 0;
}
int main(void) {
    char *args[] = { "gpu-pmgr-perf-peek", "x", NULL };
    for (int n = 0; n < 16; n++) perfmem[n * 4] = 0x11000000u + n;
    perfmem[0x200 / 4] = 0x80000003u;
    psmem[0x320 / 4] = 0x000000ffu;
    assert(peek_main(2, args) == 2 && opens == 0);
    fail_open = 1; assert(peek_main(1, args) == 1 && maps == 0); fail_open = 0;
    fail_map = 1; assert(peek_main(1, args) == 1 && unmaps == 0);
    maps = 0; fail_map = 2; assert(peek_main(1, args) == 1 && unmaps == 1);
    maps = 0; fail_map = 0; unmaps = 0;
    assert(peek_main(1, args) == 1 && unmaps == 2);
    allow_read = 1; unmaps = 0;
    assert(peek_main(1, args) == 0 && unmaps == 2);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)
    (path / "test.c").write_text(harness)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(source.parent),
                    str(path / "test.c"), "-o", str(path / "test")], check=True)
    out = subprocess.run([str(path / "test")], check=True, capture_output=True, text=True).stdout
    assert "stage=before-perf-read base=0x20e01c000 words=17 ps=0x20e020320" in out
    assert "ps raw=0x000000ff" in out and "ctl raw=0x80000003" in out
    assert "perf00 raw=0x11000000" in out and "perf15 raw=0x1100000f" in out
    assert out.rstrip().endswith("stage=after-perf-read")
print("PASS: read-only GFX perf-state mapping, order and cleanup")
