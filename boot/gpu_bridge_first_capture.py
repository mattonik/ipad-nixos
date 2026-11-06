#!/usr/bin/env python3
import os, socket, sys, time
from pathlib import Path

def main():
    log = Path(sys.argv[1]); probe, supervisor, wrapper = sys.argv[2:5]
    fd=os.open(log,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb',buffering=0) as out, socket.create_connection(('172.16.42.1',23),5) as s:
        command=(f'test "$(sha256sum /tmp/gpu-watchdog-supervisor | cut -d " " -f 1)" = {supervisor} && '
                 f'test "$(sha256sum /tmp/gpu-bridge-first-run | cut -d " " -f 1)" = {wrapper} && '
                 f'/tmp/gpu-watchdog-supervisor --bridge-first {probe}\n').encode()
        s.sendall(command); buf=b''; expected=[(b'stage=before-watchdog-open',b'ARM\n'),(b'stage=watchdog-armed timeout=20',None),(b'stage=before-pmgr-read address=0x20e020320 width=32',b'READ\n'),(b'stage=after-pmgr-read raw=0x000003ff target=15 actual=15 auto=0 reset=0',b'FEED 1\n'),(b'stage=before-gpc-state address=0x201e01000 op=read value=0x00000000',b'ACCESS\n'),(None,b'FEED 2\n'),(b'stage=before-bridge-first address=0x201f00018 op=write value=0x80010004',b'ACCESS\n'),(None,b'FEED 3\n'),(b'stage=finished rc=0',None),(b'stage=watchdog-disarmed',None)]
        i=0; end=time.monotonic()+40
        while time.monotonic()<end:
            s.settimeout(1); 
            try: chunk=s.recv(4096)
            except TimeoutError: continue
            if not chunk: break
            out.write(chunk); out.flush(); buf+=chunk
            while b'\n' in buf:
                line,buf=buf.split(b'\n',1); line=line.strip(b'\r')
                if not line.startswith(b'stage='): continue
                if i>=len(expected): raise RuntimeError('unexpected stage')
                want,ack=expected[i]
                if want is not None and line!=want: raise RuntimeError('unexpected stage')
                if want is None and i==5 and not line.startswith(b'stage=after-gpc-state value=0x00000000'): raise RuntimeError('GPC not zero')
                if want is None and i==7 and line!=b'stage=after-bridge-first value=0x80010004': raise RuntimeError('write marker mismatch')
                out.write(b'host-verified '+line+b'\n'); out.flush()
                if ack: s.sendall(ack)
                i+=1
                if i==len(expected): return
        raise RuntimeError('incomplete capture; device state unknown')
if __name__=='__main__': main()
