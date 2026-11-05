#!/usr/bin/env python3
"""Exercise the GPC observation using a fake, read-only mapping."""
import subprocess
import tempfile
from pathlib import Path

source = Path(__file__).with_name("gpu-gpc-peek.c")
harness = r'''
#define open fake_open
#define close fake_close
#define mmap fake_mmap
#define munmap fake_munmap
#define mkdir fake_mkdir
#define fgets fake_fgets
#define main peek_main
#include "gpu-gpc-peek.c"
#undef main
#include <assert.h>
#include <errno.h>
#include <string.h>
static uint32_t memory[0x2000 / 4];
static int opened, mapped, guard, answers, stop_after, poison_mapping;
int fake_mkdir(const char *name, mode_t mode) {
    assert(strcmp(name, "/tmp/gpu-gpc-peek.once") == 0 && mode == 0700);
    if (guard++) { errno = EEXIST; return -1; }
    return 0;
}
char *fake_fgets(char *s, int n, FILE *stream) {
    (void)stream; assert(n >= 6); answers++;
    strcpy(s, answers <= stop_after ? "READ\n" : "NO\n"); return s;
}
int fake_open(const char *name, int flags, ...) {
    assert(strcmp(name, "/dev/mem") == 0 && (flags & O_ACCMODE) == O_RDONLY);
    opened++; return 7;
}
int fake_close(int fd) { assert(fd == 7); return 0; }
void *fake_mmap(void *addr, size_t length, int prot, int flags, int fd, off_t offset) {
    (void)addr; assert(length == sizeof(memory) && prot == PROT_READ && flags == MAP_SHARED);
    assert(fd == 7 && (uint64_t)offset == 0x201e00000ULL); mapped++; return poison_mapping ? (void *)1 : memory;
}
int fake_munmap(void *addr, size_t length) {
    assert(addr == (poison_mapping ? (void *)1 : (void *)memory) && length == sizeof(memory)); return 0;
}
int main(void) {
    char *args[] = { "gpu-gpc-peek", "extra", NULL };
    char *map_args[] = { "gpu-gpc-peek", "--map-only", NULL };
    memory[0x1000/4] = 0x12340001; memory[0] = 0x20000000;
    assert(peek_main(2,args) == 2 && !guard && !opened);
    poison_mapping = 1;
    assert(peek_main(2,map_args) == 0 && !guard && opened == 1 && mapped == 1 && !answers);
    poison_mapping = 0;
    stop_after = 1;
    assert(peek_main(1,args) == 1 && answers == 2 && opened == 2 && mapped == 2);
    assert(peek_main(1,args) == 1 && opened == 2);
    guard = answers = 0; stop_after = 2;
    assert(peek_main(1,args) == 0 && answers == 2 && opened == 3 && mapped == 3);
    guard = answers = 0; memory[0x1000/4] = 0x10;
    assert(peek_main(1,args) == 1 && answers == 1);
    assert(memory[0x1000/4] == 0x10 && memory[0] == 0x20000000);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)
    (path / "test.c").write_text(harness)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(source.parent),
                    str(path / "test.c"), "-o", str(path / "test")], check=True)
    result = subprocess.run([str(path / "test")], check=True, capture_output=True, text=True)
    assert "stage=gpc-mapped-no-access" in result.stdout
    assert result.stdout.count("stage=after-gpc-state raw=0x12340001") == 2
    assert result.stdout.count("stage=after-gpc-control raw=0x20000000") == 1
    assert "stage=blocked-gpc-state" in result.stdout
print("PASS: one-shot GPC observation, acknowledgements, and read-only mapping")
