#!/usr/bin/env python3
"""Exercise the bridge map-only path with deliberately invalid fake mappings."""
import subprocess
import tempfile
from pathlib import Path

source = Path(__file__).with_name('gpu-bridge-map.c')
harness = r'''
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stdio.h>
#include <assert.h>
int fake_open(const char *, int, ...);
void *fake_mmap(void *, size_t, int, int, int, off_t);
int fake_munmap(void *, size_t);
int fake_close(int);
#define open fake_open
#define mmap fake_mmap
#define munmap fake_munmap
#define close fake_close
#define main bridge_main
#include "gpu-bridge-map.c"
#undef main
static int count, unmapped, closed, fail_second;
int fake_open(const char *s,int flags,...){(void)s;assert((flags&O_ACCMODE)==O_RDWR);return 5;}
void *fake_mmap(void *a,size_t n,int p,int f,int fd,off_t off){
 (void)a;assert(n==0x81000&&p==PROT_WRITE&&f==MAP_SHARED&&fd==5);
 assert((count==0 && off==0x201f00000ULL)||(count==1 && off==0x201f80000ULL));
 count++;return (fail_second && count==2)?MAP_FAILED:(void *)(uintptr_t)(count*4096);
}
int fake_munmap(void *p,size_t n){assert(p!=(void *)0 && n==0x81000);unmapped++;return 0;}
int fake_close(int fd){assert(fd==5);closed++;return 0;}
int main(void){char *args[]={"test","bad",NULL};
 assert(bridge_main(2,args)==2 && count==0);
 assert(bridge_main(1,args)==0 && count==2 && unmapped==2 && closed==1);
 count=unmapped=closed=0;fail_second=1;
 assert(bridge_main(1,args)==1 && count==2 && unmapped==1 && closed==1);return 0;}
'''
with tempfile.TemporaryDirectory() as d:
    p = Path(d)
    (p/'test.c').write_text('#include <stdint.h>\n' + harness)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(source.parent),str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True,capture_output=True)
print('PASS: bridge map-only success, refusal and cleanup without MMIO')
