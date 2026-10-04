#!/usr/bin/env python3
"""Validate pinned legacy Z2 packet/ACK behavior as a comparison, not J81 code.

Extracts public reference functions into temporary host C. Synthetic data only;
no bus access, firmware, calibration asset, or hardware timing validation.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

SOURCE_SHA256 = "5385aaa7463e6ac5c927a3a848256af2c1992e7b80fa064d95bd56b85f38d883"

PRELUDE = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define TRUE 1
#define FALSE 0
#define NORMAL_SPEED ((void*)0)
#define FAST_SPEED ((void*)0)
#define EnterCriticalSection() ((void)0)
#define LeaveCriticalSection() ((void)0)
#define bufferPrintf(...) ((void)0)
static int GotATN;
static uint64_t ticks;
static unsigned int tx_calls, ack_calls;
static int signal_attention=1;
static unsigned int succeed_on=1;
static uint16_t response=0x4bc1;
static uint64_t timer_get_system_microtime(void) { return ticks; }
static int has_elapsed(uint64_t start, uint64_t delay) { return ++ticks-start>=delay; }
static int mt_spi_tx(const void *settings, const uint8_t *data, int length)
{ (void)settings; (void)data; assert(length==4); tx_calls++; GotATN=signal_attention; return 0; }
static int mt_spi_txrx(const void *settings, const uint8_t *tx, int txlen, uint8_t *rx, int rxlen)
{
    (void)settings; assert(txlen==rxlen);
    assert(tx[0]==0x1a && tx[1]==0xa1);
    memset(rx,0,(size_t)rxlen); ack_calls++;
    if(txlen==2) {
        uint16_t value=ack_calls>=succeed_on ? response : 0;
        rx[0]=value>>8; rx[1]=value&255;
    } else {
        assert(txlen==8);
        for(int i=2;i<8;i+=2) assert(tx[i]==0x18 && tx[i+1]==0xe1);
        rx[2]=0x56; rx[3]=0x78; rx[4]=0x12; rx[5]=0x34;
    }
    return 0;
}
'''

TESTS = r'''
static void reset(void)
{ ticks=0; GotATN=0; tx_calls=ack_calls=0; signal_attention=1; succeed_on=1; response=0x4bc1; }
int main(void)
{
    uint8_t input[1008], packet[1022];
    for(unsigned int i=0;i<sizeof(input);i++) input[i]=(uint8_t)i;
    /* Actual callers cap calibration chunks at 0x3f0 and round to 4 bytes. */
    for(int length=4;length<=1008;length+=4) {
        memset(packet,0xcc,sizeof(packet)); int checksum=-1;
        assert(makeBootloaderDataPacket(packet,0x12345678,input,length,&checksum)==length);
        assert(packet[0]==0x30 && packet[1]==1);
        assert(packet[2]==0 && packet[3]==length/4);
        assert(packet[4]==0x56 && packet[5]==0x78 && packet[6]==0x12 && packet[7]==0x34);
        unsigned int header=0,sum=0;
        for(int i=2;i<8;i++) header+=packet[i];
        assert(packet[8]==(header>>8) && packet[9]==(header&255));
        for(int i=0;i<length;i+=2) {
            assert(packet[10+i]==input[i+1] && packet[11+i]==input[i]);
            sum+=input[i]+input[i+1];
        }
        assert(checksum==(int)sum);
        assert(packet[length+10]==((sum>>8)&255) && packet[length+11]==(sum&255));
        assert(packet[length+12]==((sum>>24)&255) && packet[length+13]==((sum>>16)&255));
    }
    uint8_t firmware[4]={0x18,0xe1,0,0};
    reset(); assert(loadConstructedFirmware(firmware,4)==TRUE && tx_calls==1 && ack_calls==1);
    reset(); succeed_on=3;
    assert(loadConstructedFirmware(firmware,4)==TRUE && tx_calls==3 && ack_calls==3);
    reset(); response=0xc14b;
    assert(loadConstructedFirmware(firmware,4)==FALSE && tx_calls==5 && ack_calls==5);
    reset(); signal_attention=0;
    assert(loadConstructedFirmware(firmware,4)==FALSE && tx_calls==5 && ack_calls==0);
    reset(); GotATN=1;
    assert(performHBPPLongATN_ACK()==0x12345678);
    puts("PASS: 252 legacy aligned packet sizes, word/byte ordering, checksum spans, ACK byte order/retries/timeout, long response decoding");
    return 0;
}
'''


def function(source: str, signature: str) -> str:
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end] + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="exact pinned openiBoot multitouch-z2.c")
    parser.add_argument("--cc", default=os.environ.get("CC", "gcc"))
    parser.add_argument("--sanitize", action="store_true")
    args = parser.parse_args()
    data = args.source.read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        parser.error("source differs from reviewed openiBoot pin")
    source = data.decode()
    definitions = "".join(function(source, signature) for signature in (
        "static uint16_t performHBPPATN_ACK()",
        "static uint32_t performHBPPLongATN_ACK()",
        "static int makeBootloaderDataPacket(",
        "static int loadConstructedFirmware("))
    with tempfile.TemporaryDirectory(prefix="legacy-z2-") as directory:
        root = Path(directory)
        harness = root / "test.c"
        harness.write_text(PRELUDE + definitions + TESTS)
        command = [args.cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-O1", "-g"]
        if args.sanitize:
            command += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
        executable = root / "test"
        subprocess.run(command + [str(harness), "-o", str(executable)], check=True)
        subprocess.run([str(executable)], check=True)
    print("Reference-only: J81 ACK/layout, GPIO, speed and destination addresses remain unconfirmed")


if __name__ == "__main__":
    main()
