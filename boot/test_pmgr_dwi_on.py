#!/usr/bin/env python3
"""Exercise pmgr-dwi-on against a fake mapping, with no hardware access."""
import subprocess
import tempfile
from pathlib import Path

source = Path(__file__).with_name("pmgr-dwi-on.c")
harness = r'''
#define open fake_open
#define close fake_close
#define mmap fake_mmap
#define munmap fake_munmap
#define fgets fake_fgets
#define nanosleep fake_nanosleep
#define main dwi_main
#include "pmgr-dwi-on.c"
#undef main
#include <assert.h>
static uint32_t memory[0x1000 / 4], snapshot[0x1000 / 4];
static const char *replies[4];
static int reply_index, sleeps, follow;
char *fake_fgets(char *s, int size, FILE *stream) {
    (void)stream; (void)size;
    if (!replies[reply_index]) return NULL;
    strcpy(s, replies[reply_index++]);
    return s;
}
int fake_nanosleep(const struct timespec *a, struct timespec *b) {
    (void)a; (void)b; sleeps++;
    /* model hardware: actual follows target after two polls */
    if (follow && sleeps == 2) memory[0x120 / 4] |= (memory[0x120 / 4] & 0xf) << 4;
    return 0;
}
int fake_open(const char *path, int flags, ...) {
    assert(strcmp(path, "/dev/mem") == 0 && (flags & O_ACCMODE) == O_RDWR);
    return 7;
}
int fake_close(int fd) { assert(fd == 7); return 0; }
void *fake_mmap(void *addr, size_t length, int prot, int flags, int fd, off_t offset) {
    (void)addr;
    assert(length == 0x1000 && prot == (PROT_READ | PROT_WRITE) && flags == MAP_SHARED);
    assert(fd == 7 && (uint64_t)offset == 0x20e020000ULL);
    return memory;
}
int fake_munmap(void *addr, size_t length) { assert(addr == memory && length == 0x1000); return 0; }
static void reset(uint32_t v, const char *a, const char *b, int f) {
    memset(memory, 0x5a, sizeof(memory)); memory[0x120 / 4] = v;
    memcpy(snapshot, memory, sizeof(memory));
    replies[0] = a; replies[1] = b; replies[2] = NULL; reply_index = 0; sleeps = 0; follow = f;
}
static void only_dwi_changed(void) {
    snapshot[0x120 / 4] = memory[0x120 / 4];
    assert(memcmp(snapshot, memory, sizeof(memory)) == 0);
}
int main(void) {
    char *args[] = { "pmgr-dwi-on", "x", NULL };
    assert(dwi_main(2, args) == 2);
    reset(0x80000000, "NO\n", NULL, 1);            /* no read ack: nothing happens */
    assert(dwi_main(1, args) == 1 && memory[0x120 / 4] == 0x80000000);
    reset(0x80000000, "READ\n", "NO\n", 1);        /* no write ack: no write */
    assert(dwi_main(1, args) == 1 && memory[0x120 / 4] == 0x80000000);
    reset(0x800000ff, "READ\n", NULL, 1);          /* already on: no write */
    assert(dwi_main(1, args) == 0 && memory[0x120 / 4] == 0x800000ff);
    reset(0x80000000, "READ\n", "WRITE\n", 1);     /* normal */
    assert(dwi_main(1, args) == 0 && memory[0x120 / 4] == 0x800000ff);
    only_dwi_changed();
    reset(0x80000000, "READ\n", "WRITE\n", 0);     /* actual never follows */
    assert(dwi_main(1, args) == 1 && memory[0x120 / 4] == 0x8000000f && sleeps == 100);
    only_dwi_changed();
    return 0;
}
'''
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)
    (path / "test.c").write_text(harness)
    subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-I", str(source.parent),
                    str(path / "test.c"), "-o", str(path / "test")], check=True)
    out = subprocess.run([str(path / "test")], check=True, capture_output=True, text=True).stdout
    assert "stage=before-dwi-write address=0x20e020120 set=0xf" in out
    assert "result=on polls=2" in out and "result=not-on polls=100" in out
    assert "result=already-on" in out
print("PASS: pmgr-dwi-on touches only the dwi power-state word, with both acks")
