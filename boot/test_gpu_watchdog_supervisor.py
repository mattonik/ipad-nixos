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
    child=p/'mcc-child'
    child.write_text('#!/bin/sh\n[ "$#" -eq 4 ] && [ "$1" = --run ] || exit 2\nprintf "stage=before-mcc-read address=0x200000830 width=32\\n"\nIFS= read -r reply || exit 1\n[ "$reply" = READ ] || exit 1\nprintf "stage=after-mcc-read address=0x200000830 value=0x12345678\\nstage=finished rc=0\\n"\n')
    child.chmod(0o755)
    timed=p/'timed-child'
    timed.write_text('#!/bin/sh\n[ "$#" -eq 2 ] || exit 2\nprintf "stage=before-gpc-page5 address=0x20e005004 width=32\\n"\nIFS= read -r reply || exit 1\n[ "$reply" = READ ] || exit 1\nprintf "stage=after-gpc-page5 address=0x20e005004 value=0x00000000\\nstage=finished rc=0\\n"\n')
    timed.chmod(0o755)
    page5=p/'page5-child'
    page5.write_text('#!/bin/sh\n[ "$#" -eq 5 ] && [ "$1" = --run ] || exit 2\nprintf "stage=before-page5-read address=0x20e00500%s width=32\\n" "$5"\nIFS= read -r reply || exit 1\n[ "$reply" = READ ] || exit 1\nprintf "stage=after-page5-read value=0x12345678\\nstage=finished rc=0\\n"\n')
    page5.chmod(0o755)
    (p/'gpu-watchdog-supervisor.c').write_text(source.read_text().replace('"/tmp/j81-mcc-read-once-run"', f'"{child}"').replace('"/tmp/j81-page5-read-once-run"', f'"{page5}"').replace('"/tmp/gpu-gpc-page5-timed-run"', f'"{timed}"'))
    (p/'linux'/'watchdog.h').write_text('#pragma once\n#include <stdint.h>\nstruct watchdog_info { uint32_t options, firmware_version; unsigned char identity[32]; };\n#define WDIOF_MAGICCLOSE 0x100\n#define WDIOC_GETSUPPORT 1\n#define WDIOC_SETTIMEOUT 2\n#define WDIOC_KEEPALIVE 3\n#define WDIOC_SETOPTIONS 4\n#define WDIOS_DISABLECARD 1\n')
    (p/'test.c').write_text(harness)
    subprocess.run(['cc','-D_GNU_SOURCE','-std=c11','-Wall','-Wextra','-Werror','-I',str(p),'-I',str(source.parent),str(p/'test.c'),'-o',str(p/'test')],check=True)
    run(p/'test');run(p/'test',stall=True);run(p/'test',bad_ack=True)
    proc=subprocess.Popen([str(p/'test'),'--mcc-read-once','a'*64,'b'*64,'12345678-1234-1234-1234-123456789abc'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,bufsize=0)
    try:
        line(proc,b'stage=before-watchdog-open\n');proc.stdin.write(b'ARM\n')
        line(proc,b'stage=watchdog-armed timeout=20\n')
        line(proc,b'stage=before-mcc-read address=0x200000830 width=32\n');proc.stdin.write(b'READ\n')
        line(proc,b'stage=after-mcc-read address=0x200000830 value=0x12345678\n')
        selector=selectors.DefaultSelector();selector.register(proc.stderr,selectors.EVENT_READ)
        assert not selector.select(0.1), 'watchdog fed before host acknowledgement';selector.close()
        proc.stdin.write(b'FEED 1\n')
        line(proc,b'stage=finished rc=0\n');line(proc,b'stage=watchdog-disarmed\n')
        assert proc.wait(timeout=3)==0 and proc.stderr.read()==b'fake-feed\n'
    finally:
        if proc.poll() is None: os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=3)
        for f in (proc.stdin,proc.stdout,proc.stderr): f.close()
    proc=subprocess.Popen([str(p/'test'),'--gpc-page5-timed','a'*64,'12345678-1234-1234-1234-123456789abc'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,bufsize=0)
    try:
        line(proc,b'stage=before-watchdog-open\n');proc.stdin.write(b'ARM\n')
        line(proc,b'stage=watchdog-armed timeout=20\n')
        line(proc,b'stage=before-gpc-page5 address=0x20e005004 width=32\n');proc.stdin.write(b'READ\n')
        line(proc,b'stage=after-gpc-page5 address=0x20e005004 value=0x00000000\n');proc.stdin.write(b'FEED 1\n')
        line(proc,b'stage=finished rc=0\n');line(proc,b'stage=watchdog-disarmed\n')
        assert proc.wait(timeout=3)==0 and proc.stderr.read()==b'fake-feed\n'
    finally:
        if proc.poll() is None: os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=3)
        for f in (proc.stdin,proc.stdout,proc.stderr): f.close()
    for offset in ('0','4','8'):
        proc=subprocess.Popen([str(p/'test'),'--page5-read-once','a'*64,'b'*64,'12345678-1234-1234-1234-123456789abc',offset],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,bufsize=0)
        try:
            line(proc,b'stage=before-watchdog-open\n');proc.stdin.write(b'ARM\n')
            line(proc,b'stage=watchdog-armed timeout=20\n')
            line(proc,f'stage=before-page5-read address=0x20e00500{offset} width=32\n'.encode());proc.stdin.write(b'READ\n')
            line(proc,b'stage=after-page5-read value=0x12345678\n');proc.stdin.write(b'FEED 1\n')
            line(proc,b'stage=finished rc=0\n');line(proc,b'stage=watchdog-disarmed\n')
            assert proc.wait(timeout=3)==0 and proc.stderr.read()==b'fake-feed\n'
        finally:
            if proc.poll() is None: os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=3)
            for f in (proc.stdin,proc.stdout,proc.stderr): f.close()
    assert subprocess.run([str(p/'test'),'--page5-read-once','a'*64,'b'*64,'12345678-1234-1234-1234-123456789abc','12']).returncode == 2
print('PASS: supervisor feeds only acknowledged progress and fails closed on stalls')
