#!/usr/bin/env python3
"""Verify the selector-10 probe's addresses, guards and acknowledgement path."""
import subprocess
import tempfile
from pathlib import Path

source = Path(__file__).with_name('gpu-bridge10-postgpc.c')
harness = r'''
#define main probe_main
#define open fake_open
#define close fake_close
#define mmap fake_mmap
#define munmap fake_munmap
#define mkdir fake_mkdir
#define fgets fake_fgets
#include "gpu-bridge10-postgpc.c"
#undef main
#include <assert.h>
static uint32_t gpc_mem[0x2000/4], bridge_mem[0x1000/4];
static int ack, map_count, calls, guard;
int fake_mkdir(const char *path, mode_t mode) { assert(!strcmp(path,"/tmp/gpu-bridge10-postgpc.once") && mode==0700);return guard; }
int fake_open(const char *path,int flags,...) { assert(!strcmp(path,"/dev/mem") && (flags & O_ACCMODE)==O_RDONLY);return 7; }
int fake_close(int fd) { assert(fd==7);return 0; }
void *fake_mmap(void *a,size_t len,int prot,int flags,int fd,off_t off) {
 (void)a;assert(prot==PROT_READ && flags==MAP_SHARED && fd==7);map_count++;
 if(off==0x201e00000ULL){assert(len==0x2000);return gpc_mem;}
 assert(off==0x201f80000ULL && len==0x1000);return bridge_mem;
}
int fake_munmap(void *p,size_t len){assert((p==gpc_mem && len==0x2000)||(p==bridge_mem && len==0x1000));return 0;}
char *fake_fgets(char *p,int n,FILE *f){(void)n;(void)f;calls++;strcpy(p,ack?"READ\n":"NO\n");return p;}
int main(void){char *args[]={"probe",0};
 guard=1;assert(probe_main(1,args)==2 && map_count==0);
 guard=0;ack=0;assert(probe_main(1,args)==1 && calls==1);
 ack=1;calls=0;gpc_mem[0x1000/4]=0;assert(probe_main(1,args)==1 && calls==1);
 calls=0;gpc_mem[0x1000/4]=1;gpc_mem[0]=0x40000000;bridge_mem[0x18/4]=0x80010004;
 assert(probe_main(1,args)==0 && calls==3);
 return 0;
}
'''
with tempfile.TemporaryDirectory() as d:
    path=Path(d);(path/'test.c').write_text(harness)
    subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-I',str(source.parent),str(path/'test.c'),'-o',str(path/'test')],check=True)
    output=subprocess.run([str(path/'test')],capture_output=True,text=True,check=True).stdout
    assert 'stage=after-bridge10-18 raw=0x80010004' in output
print('PASS: one-shot, GPC guards, acknowledgements, read-only mapping and selector-10 value')
