#!/usr/bin/env python3
"""Validate watchdog actions and early refusal without touching a watchdog."""
from pathlib import Path
import subprocess
import tempfile

source = Path(__file__).with_name('watchdog-control-test.c')
harness = r'''
#include <fcntl.h>
#include <linux/watchdog.h>
#include <stdio.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <assert.h>
#include <stdarg.h>
#include <setjmp.h>
int fake_open(const char *,int,...); int fake_ioctl(int,unsigned long,...);
ssize_t fake_write(int,const void *,size_t); int fake_close(int); int fake_pause(void);
char *fake_fgets(char *,int,FILE *);
#define open fake_open
#define ioctl fake_ioctl
#define write fake_write
#define close fake_close
#define pause fake_pause
#define fgets fake_fgets
#define main watchdog_main
#include "watchdog-control-test.c"
#undef main
static int opens, writes, closes, allow=1, bad_timeout;
static jmp_buf j;
int fake_open(const char *s,int f,...){assert(!strcmp(s,"/dev/watchdog0")&&(f&O_ACCMODE)==O_WRONLY);opens++;return 5;}
int fake_ioctl(int fd,unsigned long req,...){va_list a;void *p;assert(fd==5);va_start(a,req);p=va_arg(a,void *);va_end(a);
 if(req==WDIOC_GETSUPPORT){((struct watchdog_info *)p)->options=WDIOF_MAGICCLOSE;return 0;}
 assert(req==WDIOC_SETTIMEOUT);if(bad_timeout)*(int *)p=99;return 0;}
ssize_t fake_write(int fd,const void *p,size_t n){assert(fd==5&&n==1&&*(char *)p=='V');writes++;return 1;}
int fake_close(int fd){assert(fd==5);closes++;return 0;}
int fake_pause(void){longjmp(j,1);return 0;}
char *fake_fgets(char *p,int n,FILE *f){(void)n;(void)f;strcpy(p,allow?"ARM\n":"NO\n");return p;}
int main(void){char *bad[]={"test","bad",0},*check[]={"test","--check",0},*expire[]={"test","--expire",0};
 assert(watchdog_main(2,bad)==2&&!opens);allow=0;assert(watchdog_main(2,check)==1&&!opens);
 allow=1;assert(watchdog_main(2,check)==0&&opens==1&&writes==1&&closes==1);
 bad_timeout=1;assert(watchdog_main(2,expire)==1&&opens==2&&writes==2&&closes==2);
 bad_timeout=0;if(!setjmp(j)){watchdog_main(2,expire);assert(0);}assert(opens==3&&writes==2&&closes==2);return 0;}
'''
with tempfile.TemporaryDirectory() as d:
    p=Path(d); (p/'linux').mkdir()
    (p/'linux'/'watchdog.h').write_text('#pragma once\n#include <stdint.h>\nstruct watchdog_info { uint32_t options, firmware_version; unsigned char identity[32]; };\n#define WDIOF_MAGICCLOSE 0x100\n#define WDIOC_GETSUPPORT 1\n#define WDIOC_SETTIMEOUT 2\n')
    (p/'test.c').write_text(harness)
    subprocess.run(['cc','-D_GNU_SOURCE','-std=c11','-Wall','-Wextra','-Werror','-I',str(p),'-I',str(source.parent),str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True,capture_output=True)
print('PASS: watchdog refusal, disarm, bad timeout and expiry path')
