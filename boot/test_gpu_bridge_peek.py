#!/usr/bin/env python3
"""Check the exact read-only one-shot sequence with fake mappings."""
import subprocess
import tempfile
from pathlib import Path

source = Path(__file__).with_name('gpu-bridge-peek.c')
harness = r'''
#define open fake_open
#define close fake_close
#define mmap fake_mmap
#define munmap fake_munmap
#define mkdir fake_mkdir
#define fgets fake_fgets
#define main peek_main
#include "gpu-bridge-peek.c"
#undef main
#include <assert.h>
#include <errno.h>
static uint32_t gpc[0x2000/4],bridge[0x1000/4];
static int guard,acks,allow,maps;
int fake_mkdir(const char *p,mode_t m){assert(!strcmp(p,"/tmp/gpu-bridge-peek.once")&&m==0700);if(guard++){errno=EEXIST;return -1;}return 0;}
char *fake_fgets(char *p,int n,FILE *f){(void)n;(void)f;strcpy(p,++acks<=allow?"ACCESS\n":"NO\n");return p;}
int fake_open(const char *p,int f,...){assert(!strcmp(p,"/dev/mem")&&(f&O_ACCMODE)==O_RDONLY);return 9;}
int fake_close(int fd){assert(fd==9);return 0;}
void *fake_mmap(void *p,size_t n,int prot,int flags,int fd,off_t off){(void)p;assert(prot==PROT_READ&&flags==MAP_SHARED&&fd==9);maps++;
 if(off==0x201e00000ULL){assert(n==sizeof(gpc));return gpc;}
 assert(off==0x201f00000ULL&&n==sizeof(bridge));return bridge;}
int fake_munmap(void *p,size_t n){assert((p==gpc&&n==sizeof(gpc))||(p==bridge&&n==sizeof(bridge)));return 0;}
int main(void){char *args[]={"test","bad",0};bridge[0x18/4]=0x12345678;
 assert(peek_main(2,args)==2&&!guard&&!maps);allow=1;assert(peek_main(1,args)==1&&acks==2);
 assert(peek_main(1,args)==1);guard=acks=0;allow=2;gpc[0x1000/4]=1;assert(peek_main(1,args)==1&&acks==1);
 guard=acks=0;gpc[0x1000/4]=0;assert(peek_main(1,args)==0&&acks==2);return 0;}
'''
with tempfile.TemporaryDirectory() as d:
    p=Path(d);(p/'test.c').write_text(harness)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(source.parent),str(p/'test.c'),'-o',str(p/'test')],check=True)
    out=subprocess.run([str(p/'test')],check=True,capture_output=True,text=True).stdout
    assert out.count('stage=after-bridge-peek value=0x12345678')==1
print('PASS: bridge peek uses read-only mappings, one-shot and GPC/acknowledgement gates')
