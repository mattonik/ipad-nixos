#!/usr/bin/env python3
"""Host-check guards, fixed offsets and one-shot behavior of the page-5 module."""
from pathlib import Path
import subprocess
import tempfile

source = Path(__file__).resolve().parent / "page5-read-once/page5-read-once.c"
harness = r'''
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
typedef uint32_t u32; typedef int atomic_t;
#define ATOMIC_INIT(v) (v)
#define __iomem
#define __init
#define PAGE_SIZE 4096
#define module_init(fn)
#define module_param(n,t,m)
#define MODULE_LICENSE(v)
#define MODULE_DESCRIPTION(v)
#define THIS_MODULE ((struct module *)1)
#define IS_ERR(p) ((p) == (void *)-1)
#define PTR_ERR(p) (-ENOMEM)
#define DEVICE_ATTR(n,m,show,store) struct device_attribute dev_attr_##n = {.mode=(m)}
struct device {}; struct device_attribute { unsigned int mode; }; struct module {};
static struct device fake_device; static struct device_attribute dev_attr_read_once;
static bool is_j81=true, map_ok=true; static int reads,maps,unmaps,creates,pins; static unsigned expected_offset;
static struct device *root_device_register(const char *name) { assert(!strcmp(name,"j81-page5-read-once")); return &fake_device; }
static int device_create_file(struct device *d,struct device_attribute *a) { assert(d==&fake_device && a==&dev_attr_read_once); creates++; return 0; }
static void root_device_unregister(struct device *d) { assert(d==&fake_device); }
static void __module_get(struct module *m) { assert(m==THIS_MODULE); pins++; }
static bool of_machine_is_compatible(const char *name) { assert(!strcmp(name,"apple,j81")); return is_j81; }
static int atomic_cmpxchg(atomic_t *p,int old,int v) { int previous=*p; if(previous==old)*p=v; return previous; }
static void *ioremap(uint64_t start,uint64_t size) { assert(start==0x20e005000ULL && size==0x1000);maps++;return map_ok?(void *)0x1000:NULL; }
static u32 readl(void *p) { assert((uintptr_t)p==0x1000+expected_offset);reads++;return 0x12345678; }
static void iounmap(void *p) { assert((uintptr_t)p==0x1000);unmaps++; }
static int sysfs_emit(char *b,const char *f,...) { va_list a;va_start(a,f);int n=vsprintf(b,f,a);va_end(a);return n; }
#include "page5-read-once.c"
int main(void) {
 char out[128],want[128];
 assert(dev_attr_read_once.mode==0400);
 is_j81=false; assert(page5_read_once_init()==-ENODEV && creates==0);
 is_j81=true; offset=12; assert(page5_read_once_init()==-ENODEV && creates==0);
 offset=0; assert(page5_read_once_init()==0 && creates==1 && reads==0 && pins==1);
 for(unsigned i=0;i<3;i++){offset=4*i;expected_offset=offset;attempted=0;
  assert(read_once_show(&fake_device,&dev_attr_read_once,out)>0);
  snprintf(want,sizeof(want),"address=0x%llx value=0x12345678\n",0x20e005000ULL+offset);
  assert(!strcmp(out,want));assert(read_once_show(&fake_device,&dev_attr_read_once,out)==-EBUSY);
 }
 assert(reads==3 && maps==3 && unmaps==3);
 attempted=0;map_ok=false;assert(read_once_show(&fake_device,&dev_attr_read_once,out)==-ENOMEM);
 assert(read_once_show(&fake_device,&dev_attr_read_once,out)==-EBUSY && reads==3);
 return 0;
}
'''
with tempfile.TemporaryDirectory() as td:
    root=Path(td);(root/'linux').mkdir()
    for name in ('atomic.h','io.h','module.h','of.h','platform_device.h'):
        (root/'linux'/name).write_text('')
    (root/'test.c').write_text(harness)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I',str(root),'-I',str(source.parent),str(root/'test.c'),'-o',str(root/'test')],check=True)
    subprocess.run([str(root/'test')],check=True)
print('PASS: J81 guard, fixed page-5 offsets, one-shot and failed mapping')
