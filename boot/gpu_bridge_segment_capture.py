#!/usr/bin/env python3
import os,socket,sys,time
from pathlib import Path
def main():
 log=Path(sys.argv[1]);probe,supervisor,wrapper=sys.argv[2:5];fd=os.open(log,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb',buffering=0) as o,socket.create_connection(('172.16.42.1',23),5) as s:
  s.sendall((f'test "$(sha256sum /tmp/gpu-watchdog-supervisor|cut -d " " -f1)" = {supervisor} && test "$(sha256sum /tmp/gpu-bridge-segment-run|cut -d " " -f1)" = {wrapper} && /tmp/gpu-watchdog-supervisor --bridge-segment {probe}\n').encode());b=b'';i=0;end=time.monotonic()+60
  while time.monotonic()<end:
   s.settimeout(1)
   try:d=s.recv(4096)
   except TimeoutError:continue
   if not d:break
   o.write(d);b+=d
   while b'\n' in b:
    line,b=b.split(b'\n',1);line=line.strip(b'\r')
    if not line.startswith(b'stage='):continue
    if line==b'stage=before-watchdog-open':ack=b'ARM\n'
    elif line==b'stage=watchdog-armed timeout=20':ack=None
    elif line==b'stage=before-pmgr-read address=0x20e020320 width=32':ack=b'READ\n'
    elif line==b'stage=after-pmgr-read raw=0x000003ff target=15 actual=15 auto=0 reset=0':ack=b'FEED 1\n'
    elif line==b'stage=before-gpc-state address=0x201e01000 op=read value=0x00000000':ack=b'ACCESS\n'
    elif line==b'stage=after-gpc-state value=0x00000000':ack=b'FEED 2\n'
    elif line.startswith(b'stage=before-bridge-segment-') and b'op=write' in line:ack=b'ACCESS\n'
    elif line.startswith(b'stage=after-bridge-segment-'):ack=f'FEED {i+3}\n'.encode();i+=1
    elif line==b'stage=finished rc=0':ack=None
    elif line==b'stage=watchdog-disarmed':ack=None
    else: raise RuntimeError('unexpected stage: '+line.decode())
    o.write(b'host-verified '+line+b'\n');o.flush()
    if ack:s.sendall(ack)
    if line==b'stage=watchdog-disarmed':return
  raise RuntimeError('incomplete capture')
if __name__=='__main__':main()
