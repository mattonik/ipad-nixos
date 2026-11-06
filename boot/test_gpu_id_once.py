#!/usr/bin/env python3
"""Check guarded GPU ID probe against mocked mappings, without hardware."""
import subprocess
import tempfile
from pathlib import Path

source = Path(__file__).with_name("gpu-id-once.c")
harness = r'''
#include <stdint.h>
static uint32_t fake_read(const void *p);
#define GPU_READ32(a) fake_read(a)
#define open fake_open
#define close fake_close
#define mmap fake_mmap
#define munmap fake_munmap
#define mkdir fake_mkdir
#define fgets fake_fgets
#define main id_main
#include "gpu-id-once.c"
#undef main
#include <assert.h>
#include <errno.h>
#include <string.h>
static uint32_t gpc[0x2000/4], gpu[0x1000/4];
static int guard, reads, acks, allow;
int fake_mkdir(const char *s, mode_t m) { assert(!strcmp(s,"/tmp/gpu-id-once.once") && m==0700); if(guard++){errno=EEXIST;return -1;} return 0; }
char *fake_fgets(char *s,int n,FILE *f) { (void)f; assert(n>=6); acks++; strcpy(s,acks<=allow?"READ\n":"NO\n");return s; }
int fake_open(const char *s,int flags,...) { assert(!strcmp(s,"/dev/mem") && (flags&O_ACCMODE)==O_RDONLY);return 7; }
int fake_close(int fd) { assert(fd==7);return 0; }
void *fake_mmap(void *a,size_t n,int prot,int flags,int fd,off_t off) {
    (void)a; assert(prot==PROT_READ && flags==MAP_SHARED && fd==7);
    if ((uint64_t)off==0x201e00000ULL) { assert(n==sizeof(gpc)); return gpc; }
    assert((uint64_t)off==0x201000000ULL && n==sizeof(gpu)); return gpu;
}
int fake_munmap(void *p,size_t n) { assert((p==gpc && n==sizeof(gpc)) || (p==gpu && n==sizeof(gpu)));return 0; }
static uint32_t fake_read(const void *p) {
    const void *expected[] = {&gpc[0x1000/4], &gpc[0], &gpu[0x20/4], &gpu[0x18/4]};
    assert(reads<4 && p==expected[reads]); reads++; return *(const uint32_t *)p;
}
static void reset(void) { guard=reads=acks=0; allow=4;gpc[0x1000/4]=1;gpc[0]=0; }
int main(void) {
    char *args[]={"gpu-id-once","bad",0};gpu[0x20/4]=0x070300;gpu[0x18/4]=0x0803;
    assert(id_main(2,args)==2 && guard==0);
    reset();gpc[0x1000/4]=0;assert(id_main(1,args)==1 && reads==1);
    assert(id_main(1,args)==1 && reads==1);
    reset();gpc[0]=1U<<29;assert(id_main(1,args)==1 && reads==2);
    reset();allow=2;assert(id_main(1,args)==1 && reads==2);
    reset();allow=3;assert(id_main(1,args)==1 && reads==3);
    reset();gpu[0x20/4]=0;assert(id_main(1,args)==1 && reads==3);gpu[0x20/4]=0x070300;
    reset();assert(id_main(1,args)==0 && reads==4 && acks==4);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as directory:
    p=Path(directory);(p/"test.c").write_text(harness)
    subprocess.run(["cc","-std=c11","-Wall","-Wextra","-Werror","-I",str(source.parent),str(p/"test.c"),"-o",str(p/"test")],check=True)
    out=subprocess.run([str(p/"test")],check=True,capture_output=True,text=True).stdout
    assert "stage=after-gpu-revision raw=0x00070300" in out
    assert "stage=after-gpu-core-id raw=0x00000803" in out
print("PASS: guarded GPU ID read order and refusal paths")
