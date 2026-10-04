#!/usr/bin/env python3
"""Compile actual pinned Z2 receive/upload parsers with host SPI/input stubs.

No firmware assets, GPIO, device connection or bus transactions are used.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

SOURCE_SHA256 = "de82c35ccbc760b0ad59376902a3fbcd06bf4843cb917d6f5b7ba874376ca347"
SOURCE_PATH = "drivers/input/touchscreen/apple_z2.c"
PATCH = Path(__file__).with_name("patches") / "0011-touchscreen-apple-z2-add-j81.patch"

PRELUDE = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint16_t __le16;
typedef uint32_t __le32;
#define __packed __attribute__((packed))
#define __free(x)
#define __force
#define cpu_to_le16(x) ((u16)(x))
#define le16_to_cpu(x) ((u16)(x))
#define le32_to_cpu(x) ((u32)(x))
#define round_up(x,y) (((x)+(y)-1)&~((y)-1))
#define dev_warn(...) ((void)0)
#define dev_err(...) ((void)0)
#define MT_TOOL_FINGER 0
#define ABS_MT_WIDTH_MAJOR 1
#define ABS_MT_WIDTH_MINOR 2
#define ABS_MT_ORIENTATION 3
#define ABS_MT_TOUCH_MAJOR 4
#define ABS_MT_TOUCH_MINOR 5
#define IS_ERR(x) ((uintptr_t)(x) >= (uintptr_t)-4095)
#define PTR_ERR(x) ((int)(intptr_t)(x))
struct spi_device { int dev; };
struct input_dev { int unused; };
struct touchscreen_properties { int unused; };
struct apple_z2 {
    struct spi_device *spidev;
    struct input_dev *input_dev;
    struct touchscreen_properties props;
    int index_parity;
    u8 *tx_buf, *rx_buf;
    const char *fw_name;
    bool booted;
};
struct spi_transfer { const void *tx_buf; void *rx_buf; size_t len; };
struct firmware { size_t size; const u8 *data; };
static const struct firmware *fixture_fw;
static unsigned int slot_calls, sync_calls, read_calls, blob_calls;
static size_t read_length;
static u16 advertised;
static int sync_error, read_error;
static bool reply_marker = true;
static u32 le32_to_cpup(const __le32 *p) { u32 v; memcpy(&v,p,4); return v; }
static u16 get_unaligned_le16(const u8 *p) { return p[0] | ((u16)p[1] << 8); }
static int input_mt_get_slot_by_key(struct input_dev *d, int key)
{ (void)d; (void)key; slot_calls++; return 0; }
static void input_mt_slot(struct input_dev *d, int slot) { (void)d; (void)slot; }
static bool input_mt_report_slot_state(struct input_dev *d, int tool, bool active)
{ (void)d; (void)tool; return active; }
static void touchscreen_report_pos(struct input_dev *d, struct touchscreen_properties *p,
                                  int x, int y, bool mt)
{ (void)d; (void)p; (void)x; (void)y; (void)mt; }
static void input_report_abs(struct input_dev *d, int axis, int value)
{ (void)d; (void)axis; (void)value; }
static void input_mt_sync_frame(struct input_dev *d) { (void)d; sync_calls++; }
static void input_sync(struct input_dev *d) { (void)d; }
static int spi_sync_transfer(struct spi_device *d, struct spi_transfer *t, int count)
{
    (void)d; assert(count == 1 && t->len == 16);
    const u8 *tx = t->tx_buf;
    assert(tx[0] == 0xeb && (tx[1] == 1 || tx[1] == 2));
    assert(get_unaligned_le16(tx + 14) == 0xeb + tx[1]);
    u8 *rx = t->rx_buf;
    memset(rx,0,16); rx[0] = reply_marker ? 0xe1 : 0;
    rx[1] = advertised & 255; rx[2] = advertised >> 8;
    return sync_error;
}
static int spi_read(struct spi_device *d, void *rx, size_t size)
{
    (void)d; (void)rx; read_calls++; read_length = size;
    /* Intentionally don't copy: baseline oversized transfer can be observed
       without simulating a device/controller memory overwrite. */
    return read_error;
}
static int request_firmware(const struct firmware **fw, const char *name, void *dev)
{ (void)name; (void)dev; *fw = fixture_fw; return 0; }
static int apple_z2_send_firmware_blob(struct apple_z2 *z2, const u8 *data, u32 size, bool init)
{ (void)z2; (void)data; (void)size; (void)init; blob_calls++; return 0; }
static const u8 *apple_z2_build_cal_blob(struct apple_z2 *z2, u32 address, size_t *size)
{ (void)z2; (void)address; (void)size; return NULL; }
'''

TESTS = r'''
int main(int argc, char **argv)
{
    u8 tx[16] = {0}, rx[4000] = {0};
    struct spi_device spi = {0};
    struct input_dev input = {0};
    struct apple_z2 z = {.spidev=&spi,.input_dev=&input,.tx_buf=tx,.rx_buf=rx};
    assert(sizeof(struct apple_z2_finger)==30);
    assert(sizeof(struct apple_z2_hbpp_blob_hdr)==12);
    if (argc == 2 && !strcmp(argv[1], "original-short-firmware")) {
        u8 *bytes = malloc(1); assert(bytes); bytes[0]=0;
        struct firmware fw={.size=1,.data=bytes}; fixture_fw=&fw;
        int ret=before_upload(&z); free(bytes); return ret;
    }
    assert(argc==1);
    advertised=65535; read_calls=0;
    assert(before_read(&z)==0 && read_calls==1 && read_length>4000);
    /* Exhaust every 16-bit advertised length and check pre-transfer rejection. */
    for (unsigned int n=0;n<=65535;n++) {
        advertised=(u16)n; read_calls=0;
        size_t length=(n+8)&~3U;
        int ret=after_read(&z);
        if (length>4000) assert(ret==-EMSGSIZE && read_calls==0);
        else assert(ret==0 && read_calls==1 && read_length==length);
    }
    sync_error=-EIO; read_calls=0;
    assert(after_read(&z)==-EIO && read_calls==0); sync_error=0;
    reply_marker=false; assert(after_read(&z)==0 && read_calls==0); reply_marker=true;
    advertised=0; read_error=-EIO;
    assert(after_read(&z)==-EIO); read_error=0;
    /* Exact allocations, all count values, and one-byte-short record arrays. */
    for (unsigned int count=0;count<=255;count++) {
        size_t size=24+count*sizeof(struct apple_z2_finger);
        u8 *msg=calloc(1,size); assert(msg); msg[16]=(u8)count;
        for (unsigned int i=0;i<count;i++)
            msg[24+i*sizeof(struct apple_z2_finger)+1]=(i%2) ? 4 : 3;
        slot_calls=sync_calls=0; after_parse(&z,msg,size);
        assert(slot_calls==count && sync_calls==1);
        if(count) {
            slot_calls=sync_calls=0; after_parse(&z,msg,size-1);
            assert(slot_calls==0 && sync_calls==0);
        }
        free(msg);
    }
    for(size_t size=0;size<24;size++) {
        u8 *msg=size ? calloc(1,size) : NULL; assert(!size || msg);
        slot_calls=sync_calls=0; after_parse(&z,msg,size);
        assert(slot_calls==0 && sync_calls==0); free(msg);
    }
    u8 valid[8]={0x5a,0x32,0x46,0x57,1,0,0,0};
    struct firmware fw={.data=valid}; fixture_fw=&fw;
    for(size_t size=0;size<8;size++) {
        fw.size=size; z.booted=false; blob_calls=0;
        assert(after_upload(&z)==-EINVAL && !z.booted && blob_calls==0);
    }
    fw.size=8; assert(before_upload(&z)==0); z.booted=false;
    assert(after_upload(&z)==0 && z.booted); /* Preserve header-only baseline. */
    puts("PASS: 65536 receive lengths, 256 finger counts, short messages/firmware, transport errors");
    return 0;
}
'''


def structure(source: str, name: str) -> str:
    start = source.index("struct " + name + " {")
    end = source.index("\n}", start)
    return source[start:source.index(";", end) + 1] + "\n"


def functions(source: str, prefix: str) -> str:
    start = source.index("static void apple_z2_parse_touches(")
    end = source.index("static irqreturn_t apple_z2_irq(", start)
    upload = source[source.index("static int apple_z2_upload_firmware("):source.index("static int apple_z2_boot(")]
    result = source[start:end] + upload
    for name, suffix in (("apple_z2_parse_touches", "parse"), ("apple_z2_read_packet", "read"),
                         ("apple_z2_upload_firmware", "upload")):
        result = result.replace(name, prefix + "_" + suffix)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="exact pinned apple_z2.c")
    parser.add_argument("--cc", default=os.environ.get("CC", "gcc"))
    parser.add_argument("--sanitize", action="store_true")
    args = parser.parse_args()
    if sys.byteorder != "little":
        parser.error("host endian stubs require a little-endian host")
    data = args.source.read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        parser.error("source hash differs from pinned Hoolock apple_z2.c")
    original = data.decode()
    with tempfile.TemporaryDirectory(prefix="apple-z2-") as directory:
        root = Path(directory)
        target = root / SOURCE_PATH
        target.parent.mkdir(parents=True)
        target.write_bytes(data)
        with PATCH.open("rb") as patch:
            subprocess.run(["patch", "--batch", "--fuzz=0", "-p1"], cwd=root, stdin=patch, check=True)
        constants = original[original.index("#define APPLE_Z2_NUM_FINGERS_OFFSET"):original.index("struct apple_z2 {")]
        structures = "".join(structure(original, name) for name in
                             ("apple_z2_finger", "apple_z2_hbpp_blob_hdr",
                              "apple_z2_fw_hdr", "apple_z2_read_interrupt_cmd"))
        code = PRELUDE + constants + "#define APPLE_Z2_RX_BUF_SIZE 4000\n" + structures
        harness = root / "test.c"
        harness.write_text(code + functions(original, "before") + functions(target.read_text(), "after") + TESTS)
        command = [args.cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-Wno-sign-compare", "-O1", "-g"]
        if args.sanitize:
            command += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
        executable = root / "test"
        subprocess.run(command + [str(harness), "-o", str(executable)], check=True)
        subprocess.run([str(executable)], check=True)
        if args.sanitize:
            result = subprocess.run([str(executable), "original-short-firmware"], capture_output=True, text=True)
            if not result.returncode or "heap-buffer-overflow" not in result.stderr:
                raise RuntimeError("expected original short-firmware ASan reproducer not observed")
            print("CONFIRMED: original one-byte firmware header read exceeds allocation")
    print("No SPI hardware, J81 transport adaptation or full kernel build tested")


if __name__ == "__main__":
    main()
