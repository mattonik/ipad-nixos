#!/usr/bin/env python3
"""Test the GPC initialization program with mocked MMIO, never hardware."""
import subprocess
import tempfile
from pathlib import Path

source = Path(__file__).with_name("gpu-gpc-init.c")
harness = r'''
#include <stdint.h>
static uint32_t fake_read(volatile uint32_t *p);
static void fake_write(volatile uint32_t *p, uint32_t value);
#define GPC_READ32(a) fake_read(a)
#define GPC_WRITE32(a,v) fake_write(a,v)
#define open fake_open
#define close fake_close
#define mmap fake_mmap
#define munmap fake_munmap
#define mkdir fake_mkdir
#define fgets fake_fgets
#define main init_main
#include "gpu-gpc-init.c"
#undef main
#include <assert.h>
#include <errno.h>
#include <string.h>
static uint32_t memory[0x11000/4];
static int guard, reads, writes, acks, allow, stuck, initial_bad;
int fake_mkdir(const char *s, mode_t mode) {
    assert(!strcmp(s,"/tmp/gpu-gpc-init.once") && mode == 0700);
    if (guard++) { errno = EEXIST; return -1; } return 0;
}
char *fake_fgets(char *s,int n,FILE *stream) {
    (void)stream; assert(n >= 8); acks++;
    strcpy(s, acks <= allow ? "ACCESS\n" : "NO\n"); return s;
}
int fake_open(const char *s,int flags,...) {
    assert(!strcmp(s,"/dev/mem") && (flags & O_ACCMODE) == O_RDWR); return 7;
}
int fake_close(int fd) { assert(fd == 7); return 0; }
void *fake_mmap(void *a,size_t n,int prot,int flags,int fd,off_t off) {
    (void)a; assert(n == sizeof(memory) && prot == (PROT_READ|PROT_WRITE));
    assert(flags == MAP_SHARED && fd == 7 && (uint64_t)off == 0x201e00000ULL); return memory;
}
int fake_munmap(void *p,size_t n) { assert(p == memory && n == sizeof(memory)); return 0; }
static uint32_t fake_read(volatile uint32_t *p) {
    assert(p == &memory[0x1000/4]); reads++;
    if (reads == 1) return initial_bad ? 0x10 : 0;
    return stuck ? 0x11 : (reads < 4 ? 0x11 : 1);
}
static void fake_write(volatile uint32_t *p,uint32_t v) {
    static const unsigned offsets[] = { 0x10000, 0, 0x1000 };
    static const uint32_t values[] = { 0xffff0000, 0x40000000, 0x11 };
    assert(writes < 3 && p == &memory[offsets[writes]/4] && v == values[writes]); writes++;
}
static void reset(void) { guard=reads=writes=acks=stuck=initial_bad=0; allow=100; }
int main(void) {
    char *args[] = { "gpu-gpc-init", "bad", 0 };
    assert(init_main(2,args) == 2 && guard == 0);
    reset(); initial_bad=1; assert(init_main(1,args) == 1 && reads==1 && writes==0);
    assert(init_main(1,args) == 1 && reads==1 && writes==0);
    reset(); allow=2; assert(init_main(1,args)==1 && reads==1 && writes==1);
    reset(); stuck=1; assert(init_main(1,args)==1 && reads==65 && writes==3 && acks==68);
    reset(); assert(init_main(1,args)==0 && reads==4 && writes==3 && acks==7);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)
    (path / "test.c").write_text(harness)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(source.parent),
                    str(path / "test.c"), "-o", str(path / "test")], check=True)
    result = subprocess.run([str(path / "test")], check=True, capture_output=True, text=True)
    assert "poll limit reached" in result.stderr
    assert "stage=finished rc=0" in result.stdout
print("PASS: GPC initial-state gate, ordered writes, bounded polls and refusal")
