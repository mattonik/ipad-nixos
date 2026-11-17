#!/usr/bin/env python3
"""Exercise pmgr-ps-restore against a fake mapping, with no hardware access."""
import subprocess
import tempfile
from pathlib import Path

source = Path(__file__).with_name("pmgr-ps-restore.c")
harness = r'''
#define open fake_open
#define close fake_close
#define mmap fake_mmap
#define munmap fake_munmap
#define fgets fake_fgets
#define nanosleep fake_nanosleep
#define main restore_main
#include "pmgr-ps-restore.c"
#undef main
#include <assert.h>
static uint32_t memory[0x1000 / 4], snapshot[0x1000 / 4];
static const char *replies[8];
static int reply_index, sleeps, stuck_offset;
char *fake_fgets(char *s, int size, FILE *stream) {
    (void)stream; (void)size;
    if (!replies[reply_index]) return NULL;
    strcpy(s, replies[reply_index++]);
    return s;
}
int fake_nanosleep(const struct timespec *a, struct timespec *b) {
    unsigned int i;
    (void)a; (void)b; sleeps++;
    /* model hardware: actual follows target on the first poll, except one */
    for (i = 0; i < 0x1000 / 4; i++)
        if ((int)(i * 4) != stuck_offset && (memory[i] & 0xf) == 0xf && (memory[i] >> 28) != 5)
            memory[i] |= 0xf0;
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
static void reset(const char *a, const char *b, const char *c, int stuck) {
    unsigned int i;
    /* 0x5... marks words the tool must never write; they do not "follow" */
    for (i = 0; i < 0x1000 / 4; i++) memory[i] = 0x50000300;
    memory[0x120 / 4] = 0x00000200; memory[0x2d8 / 4] = 0x0f000300; memory[0x2d0 / 4] = 0x000000ff;
    memcpy(snapshot, memory, sizeof(memory));
    replies[0] = a; replies[1] = b; replies[2] = c; replies[3] = NULL;
    reply_index = 0; sleeps = 0; stuck_offset = stuck;
}
static void only_changed(unsigned int a, unsigned int b) {
    snapshot[a / 4] = memory[a / 4]; snapshot[b / 4] = memory[b / 4];
    assert(memcmp(snapshot, memory, sizeof(memory)) == 0);
}
int main(void) {
    char *none[] = { "pmgr-ps-restore", NULL };
    char *bad[] = { "pmgr-ps-restore", "gfx", NULL };
    char *twice[] = { "pmgr-ps-restore", "dwi", "dwi", NULL };
    char *args[] = { "pmgr-ps-restore", "dwi", "media", "isp", NULL };
    assert(restore_main(1, none) == 2);
    assert(restore_main(2, bad) == 2);            /* gfx is not in the allowlist */
    assert(restore_main(3, twice) == 2);
    reset("NO\n", NULL, NULL, -1);                /* no read ack: nothing happens */
    assert(restore_main(4, args) == 1); only_changed(0x120, 0x120);
    assert(memory[0x120 / 4] == 0x00000200);
    reset("READ\n", "NO\n", NULL, -1);            /* no write ack: no write */
    assert(restore_main(4, args) == 1 && memory[0x120 / 4] == 0x00000200);
    reset("READ\n", "WRITE\n", "NO\n", -1);       /* second write refused */
    assert(restore_main(4, args) == 1 && memory[0x120 / 4] == 0x000002ff);
    assert(memory[0x2d8 / 4] == 0x0f000300); only_changed(0x120, 0x120);
    reset("READ\n", "WRITE\n", "WRITE\n", -1);    /* normal; isp is already on */
    assert(restore_main(4, args) == 0);
    assert(memory[0x120 / 4] == 0x000002ff && memory[0x2d8 / 4] == 0x0f0003ff);
    assert(memory[0x2d0 / 4] == 0x000000ff); only_changed(0x120, 0x2d8);
    reset("READ\n", "WRITE\n", "WRITE\n", 0x120); /* dwi never follows: stop there */
    assert(restore_main(4, args) == 1 && memory[0x120 / 4] == 0x0000020f);
    assert(memory[0x2d8 / 4] == 0x0f000300 && sleeps == 100); only_changed(0x120, 0x120);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)
    (path / "test.c").write_text(harness)
    subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-I", str(source.parent),
                    str(path / "test.c"), "-o", str(path / "test")], check=True)
    out = subprocess.run([str(path / "test")], check=True, capture_output=True, text=True).stdout
    assert "stage=before-ps-write name=media address=0x20e0202d8 raw=0x0f000300 set=0xf" in out
    assert "result=already-on name=isp raw=0x000000ff" in out
    assert "result=all-on" in out and "result=not-on name=dwi" in out
print("PASS: pmgr-ps-restore writes only acknowledged, allowlisted power-state words")
