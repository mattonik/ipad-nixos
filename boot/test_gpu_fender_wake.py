#!/usr/bin/env python3
"""Verify Fender wake ordering and bounds with fake MMIO only."""
import subprocess, tempfile
from pathlib import Path

source = Path(__file__).with_name("gpu-fender-wake.c")
harness = r'''
#include <assert.h>
#include <errno.h>
#include <string.h>
#include <stdint.h>
static uint32_t fake_read(volatile uint32_t *p); static void fake_write(volatile uint32_t *p,uint32_t v);
#define FENDER_READ32(a) fake_read(a)
#define FENDER_WRITE32(a,v) fake_write(a,v)
#define open fake_open
#define close fake_close
#define mmap fake_mmap
#define munmap fake_munmap
#define mkdir fake_mkdir
#define fgets fake_fgets
#define main wake_main
#include "gpu-fender-wake.c"
#undef main
static uint32_t memory[0x21000/4]; static int guard,reads,writes,acks,allow,stuck;
int fake_mkdir(const char *s, mode_t m){assert(!strcmp(s,"/tmp/gpu-fender-wake.once")&&m==0700);if(guard++){errno=EEXIST;return -1;}return 0;}
char *fake_fgets(char *s,int n,FILE *f){(void)f;assert(n>=8);acks++;strcpy(s,acks<=allow?"ACCESS\n":"NO\n");return s;}
int fake_open(const char *s,int f,...){assert(!strcmp(s,"/dev/mem")&&(f&O_ACCMODE)==O_RDWR);return 7;}
int fake_close(int f){assert(f==7);return 0;}
void *fake_mmap(void *a,size_t n,int p,int f,int d,off_t o){(void)a;assert(n==sizeof(memory)&&p==(PROT_READ|PROT_WRITE)&&f==MAP_SHARED&&d==7&&(uint64_t)o==0x201e00000ULL);return memory;}
int fake_munmap(void *p,size_t n){assert(p==memory&&n==sizeof(memory));return 0;}
static uint32_t fake_read(volatile uint32_t *p){assert(p==&memory[0x1000/4]||p==&memory[0x20000/4]);if(p==&memory[0x20000/4])return 0x20;reads++;if(reads==1)return 0;if(stuck)return 0x10;return reads<4?0x10:0;}
static void fake_write(volatile uint32_t *p,uint32_t v){static const unsigned o[]={0x20000,0x1000,0x20000,0x10000,0,0x1000};static const uint32_t x[]={0,0x10,0x20,0xffff0000,0x40000000,0x11};assert(writes<6&&p==&memory[o[writes]/4]&&v==x[writes]);writes++;}
static void reset(void){guard=reads=writes=acks=stuck=0;allow=100;}
int main(void){char *a[]={"gpu-fender-wake",0};reset();assert(wake_main(1,a)==0&&writes==6&&reads==6);assert(wake_main(1,a)==1);reset();stuck=1;assert(wake_main(1,a)==1&&writes==1);return 0;}
'''
with tempfile.TemporaryDirectory() as d:
    p = Path(d); (p / "test.c").write_text(harness)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-I", str(source.parent), str(p / "test.c"), "-o", str(p / "test")], check=True)
    subprocess.run([str(p / "test")], check=True, capture_output=True)
print("PASS: Fender reset/hold/wake order, one-shot guard and bounded polls")
