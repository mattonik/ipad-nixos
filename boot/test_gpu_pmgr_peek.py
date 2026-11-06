#!/usr/bin/env python3
"""Exercise the PMGR probe against a fake mapping, with no hardware access."""
import subprocess
import tempfile
from pathlib import Path

source = Path(__file__).with_name("gpu-pmgr-peek.c")
harness = r'''
#define open fake_open
#define close fake_close
#define mmap fake_mmap
#define munmap fake_munmap
#define fgets fake_fgets
#define main peek_main
#include "gpu-pmgr-peek.c"
#undef main
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <string.h>
static uint32_t memory[0x1000 / 4];
static int opens, maps, fail_open, fail_map;
static int allow_read;
char *fake_fgets(char *s, int size, FILE *stream) {
    (void)stream;
    assert(size >= 6);
    strcpy(s, allow_read ? "READ\n" : "NO\n");
    return s;
}
int fake_open(const char *path, int flags, ...) {
    assert(strcmp(path, "/dev/mem") == 0);
    assert((flags & O_ACCMODE) == O_RDONLY);
    opens++;
    if (fail_open) { errno = EACCES; return -1; }
    return 7;
}
int fake_close(int fd) { assert(fd == 7); return 0; }
void *fake_mmap(void *addr, size_t length, int prot, int flags, int fd, off_t offset) {
    (void)addr;
    assert(length == 0x1000 && prot == PROT_READ && flags == MAP_SHARED);
    assert(fd == 7 && (uint64_t)offset == 0x20e020000ULL);
    maps++;
    if (fail_map) { errno = ENOMEM; return MAP_FAILED; }
    return memory;
}
int fake_munmap(void *addr, size_t length) {
    assert(addr == memory && length == sizeof(memory)); return 0;
}
int main(void) {
    char *args[] = { "gpu-pmgr-peek", "unexpected", NULL };
    memory[0x320 / 4] = 0x900000f4;
    assert(peek_main(2, args) == 2 && opens == 0);
    fail_open = 1;
    assert(peek_main(1, args) == 1 && opens == 1 && maps == 0);
    fail_open = 0; fail_map = 1;
    assert(peek_main(1, args) == 1 && opens == 2 && maps == 1);
    fail_map = 0;
    assert(peek_main(1, args) == 1 && opens == 3 && maps == 2);
    allow_read = 1;
    assert(peek_main(1, args) == 0 && opens == 4 && maps == 3);
    assert(memory[0x320 / 4] == 0x900000f4);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)
    (path / "test.c").write_text(harness)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(source.parent),
                    str(path / "test.c"), "-o", str(path / "test")], check=True)
    result = subprocess.run([str(path / "test")], check=True, capture_output=True, text=True)
    assert "stage=before-pmgr-read address=0x20e020320 width=32" in result.stdout
    assert "raw=0x900000f4 target=4 actual=15 auto=1 reset=1" in result.stdout
print("PASS: fixed read-only PMGR mapping and decode")
