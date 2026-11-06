#!/usr/bin/env python3
"""Exercise the real supervisor with a fake watchdog and real child pipes."""
import os
import selectors
import signal
import subprocess
import tempfile
from pathlib import Path

source = Path(__file__).with_name('gpu-watchdog-supervisor.c')
harness = r'''
#include <fcntl.h>
#include <linux/watchdog.h>
#include <sys/ioctl.h>
#include <stdarg.h>
#include <stdio.h>
int fake_open(const char *,int,...);
int fake_ioctl(int,unsigned long,...);
#define open fake_open
#define ioctl fake_ioctl
#include "gpu-watchdog-supervisor.c"
#undef open
#undef ioctl
int fake_open(const char *path,int flags,...){(void)path;(void)flags;return open("/dev/null",O_WRONLY);}
int fake_ioctl(int fd,unsigned long req,...){va_list a;void *p;(void)fd;
 if(req==WDIOC_KEEPALIVE){fputs("fake-feed\n",stderr);fflush(stderr);return 0;}
 va_start(a,req);p=va_arg(a,void *);va_end(a);
 if(req==WDIOC_GETSUPPORT){((struct watchdog_info *)p)->options=WDIOF_MAGICCLOSE;return 0;}
 if(req==WDIOC_SETTIMEOUT||req==WDIOC_SETOPTIONS)return 0;return -1;}
'''

def line(p, expected):
    selector=selectors.DefaultSelector();selector.register(p.stdout,selectors.EVENT_READ)
    assert selector.select(3), f'missing {expected!r}'
    value=p.stdout.readline();assert value==expected,(value,expected)
    selector.close()

def run(binary, stall=False, bad_ack=False):
    p=subprocess.Popen([str(binary), '--simulate-stall' if stall else '--simulate-ok'],
                       stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                       start_new_session=True,bufsize=0)
    try:
        line(p,b'stage=before-watchdog-open\n');p.stdin.write(b'ARM\n')
        line(p,b'stage=watchdog-armed timeout=20\n')
        line(p,b'stage=before-sim address=0x0 op=read value=0x00000000\n');p.stdin.write(b'ACCESS\n')
        line(p,b'stage=after-sim value=0x00000000\n')
        p.stdin.write(b'FEED 99\n' if bad_ack else b'FEED 1\n')
        if not stall and not bad_ack:
            line(p,b'stage=finished rc=0\n');line(p,b'stage=watchdog-disarmed\n')
            assert p.wait(timeout=3)==0
            assert p.stderr.read()==b'fake-feed\n'
        else:
            try:p.wait(timeout=0.3);raise AssertionError('failure path terminated')
            except subprocess.TimeoutExpired:pass
    finally:
        if p.poll() is None:os.killpg(p.pid,signal.SIGKILL)
        p.wait(timeout=3)
        if stall: assert p.stderr.read()==b'fake-feed\n'
        if bad_ack: assert p.stderr.read()==b''
        for f in (p.stdin,p.stdout,p.stderr): f.close()

with tempfile.TemporaryDirectory() as d:
    p=Path(d);(p/'linux').mkdir()
    (p/'linux'/'watchdog.h').write_text('#pragma once\n#include <stdint.h>\nstruct watchdog_info { uint32_t options, firmware_version; unsigned char identity[32]; };\n#define WDIOF_MAGICCLOSE 0x100\n#define WDIOC_GETSUPPORT 1\n#define WDIOC_SETTIMEOUT 2\n#define WDIOC_KEEPALIVE 3\n#define WDIOC_SETOPTIONS 4\n#define WDIOS_DISABLECARD 1\n')
    (p/'test.c').write_text(harness)
    subprocess.run(['cc','-D_GNU_SOURCE','-std=c11','-Wall','-Wextra','-Werror','-I',str(p),'-I',str(source.parent),str(p/'test.c'),'-o',str(p/'test')],check=True)
    run(p/'test');run(p/'test',stall=True);run(p/'test',bad_ack=True)
print('PASS: supervisor feeds only acknowledged progress and fails closed on stalls')
