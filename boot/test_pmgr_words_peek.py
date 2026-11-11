#!/usr/bin/env python3
"""Exercise pmgr-words-peek against a fake mapping, with no hardware access."""
import subprocess
import tempfile
from pathlib import Path

source = Path(__file__).with_name("pmgr-words-peek.c")
harness = r'''
#define open fake_open
#define close fake_close
#define mmap fake_mmap
#define munmap fake_munmap
#define fgets fake_fgets
#define main peek_main
#include "pmgr-words-peek.c"
#undef main
#include <assert.h>
static uint32_t page[0x1000 / 4];
static unsigned long long last_base;
static int maps, allow;
char *fake_fgets(char *s, int size, FILE *stream) {
    (void)stream; (void)size; strcpy(s, allow ? "READ\n" : "NO\n"); return s;
}
int fake_open(const char *path, int flags, ...) {
    assert(strcmp(path, "/dev/mem") == 0 && (flags & O_ACCMODE) == O_RDONLY); return 7;
}
int fake_close(int fd) { assert(fd == 7); return 0; }
void *fake_mmap(void *a, size_t len, int prot, int flags, int fd, off_t offset) {
    (void)a;
    assert(len == 0x1000 && prot == PROT_READ && flags == MAP_SHARED && fd == 7);
    assert((unsigned long long)offset >= 0x20e000000ULL && ((unsigned long long)offset < 0x20e040000ULL || (unsigned long long)offset == 0x20e200000ULL));
    assert(((unsigned long long)offset & 0xfff) == 0);
    last_base = offset; maps++;
    for (unsigned i = 0; i < 0x400; i++) page[i] = (uint32_t)(offset - 0x20e000000ULL) + i * 4 + 0xa0000000u;
    return page;
}
int fake_munmap(void *a, size_t len) { assert(a == page && len == 0x1000); return 0; }
int main(void) {
    char *none[] = { "p", NULL };
    char *dwi[] = { "p", "200000", "200004", NULL }, *bad4[] = { "p", "200008", NULL };
    char *bad1[] = { "p", "40000", NULL }, *bad2[] = { "p", "1c202", NULL }, *bad3[] = { "p", "zz", NULL };
    char *ok[] = { "p", "1c200", "23004", "5010", NULL };
    assert(peek_main(1, none) == 2 && peek_main(2, bad1) == 2 && peek_main(2, bad2) == 2 && peek_main(2, bad3) == 2);
    assert(peek_main(2, bad4) == 2);
    assert(maps == 0);
    assert(peek_main(4, ok) == 1 && maps == 0);   /* no acknowledgment: no mapping, no read */
    allow = 1;
    assert(peek_main(4, ok) == 0 && maps == 3 && last_base == 0x20e005000ULL);
    assert(peek_main(3, dwi) == 0 && maps == 5 && last_base == 0x20e200000ULL);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)
    (path / "test.c").write_text(harness)
    subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-I", str(source.parent),
                    str(path / "test.c"), "-o", str(path / "test")], check=True)
    out = subprocess.run([str(path / "test")], check=True, capture_output=True, text=True).stdout
    assert "w 0x01c200 raw=0xa001c200" in out and "w 0x023004 raw=0xa0023004" in out and "w 0x005010 raw=0xa0005010" in out and "w 0x200004 raw=0xa0200004" in out
print("PASS: pmgr-words-peek validates offsets, needs the acknowledgment and only reads")
