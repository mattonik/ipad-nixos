#!/usr/bin/env python3
"""Exercise pinned brcmfmac firmware.c selection and optional-NVRAM policy.

Uses synthetic filenames and host stubs, no radio, private assets or Nix.
NVRAM parser and firmware APIs are stubbed: this checks loader control flow.
"""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

SOURCE_SHA256 = "f2b6fe570981bf69a81fd5965712f18840df9b97dabcdbd4aa4cf260b4e9760b"
PRELUDE = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8;
typedef uint32_t u32;
#define BRCMF_FW_NAME_LEN 320
#define GFP_KERNEL 0
#define BRCMF_FW_TYPE_BINARY 1
#define BRCMF_FW_TYPE_NVRAM 2
#define BRCMF_FW_REQF_OPTIONAL 1
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define brcmf_dbg(...) ((void)0)
#define brcmf_err(...) ((void)0)
#define kfree free
struct device { int unused; };
struct firmware { const u8 *data; size_t size; };
struct brcmf_fw_item {
    const char *path; int type, flags;
    const struct firmware *binary;
    struct { void *data; u32 len; } nv_data;
};
struct brcmf_fw_request {
    const char *board_types[8];
    struct brcmf_fw_item items[4];
    unsigned int domain_nr, bus_nr;
};
struct brcmf_fw { struct device *dev; struct brcmf_fw_request *req; unsigned int curpos; };
static char requested[16][512];
static int calls, warnings, release_calls, parse_calls;
static const char *available;
static bool fail_alloc, fail_parse;
static u8 fake_data[4] = {1,2,3,4};
static const struct firmware blob = { fake_data, sizeof(fake_data) };
static size_t strscpy(char *dst, const char *src, size_t size) {
    size_t len = strlen(src); assert(len < size); memcpy(dst, src, len + 1); return len;
}
static char *kasprintf(int flags, const char *format, ...) {
    (void)flags; if (fail_alloc) return NULL;
    va_list ap; va_start(ap, format);
    char *p = malloc(1024); assert(p);
    assert(vsnprintf(p,1024,format,ap) < 1024); va_end(ap); return p;
}
static int firmware_request_nowarn(const struct firmware **fw, const char *path, struct device *dev) {
    (void)dev; assert(calls < 16); assert(strlen(path) < sizeof(requested[0]));
    strcpy(requested[calls++],path);
    *fw = available && !strcmp(path,available) ? &blob : NULL;
    return *fw ? 0 : -ENOENT;
}
static int request_firmware(const struct firmware **fw, const char *path, struct device *dev) {
    warnings++; return firmware_request_nowarn(fw,path,dev);
}
static void release_firmware(const struct firmware *fw) { if(fw) release_calls++; }
static u8 *bcm47xx_nvram_get_contents(size_t *len) { (void)len; return NULL; }
static u8 *brcmf_fw_nvram_from_efi(size_t *len) { (void)len; return NULL; }
static void bcm47xx_nvram_release_contents(u8 *data) { (void)data; assert(0); }
static void *brcmf_fw_nvram_strip(u8 *data, size_t len, u32 *out, unsigned int domain,
                                unsigned int bus, struct device *dev) {
    (void)dev; assert(data == fake_data && len == 4 && domain == 0 && bus == 0);
    parse_calls++; if (fail_parse) return NULL; *out = 4; return fake_data;
}
'''
TESTS = r'''
static void reset(void) {
    calls = warnings = release_calls = parse_calls = 0;
    available = NULL; fail_alloc = fail_parse = false;
}
int main(void) {
    struct device dev = {0};
    struct brcmf_fw_request req = {0};
    struct brcmf_fw ctx = { &dev, &req, 0 };
    const char *boards[] = {"apple,synthetic-M-V-1", "apple,synthetic-M-V",
                           "apple,synthetic-M", "apple,synthetic"};
    const char *exts[] = {".bin", ".txt", ".clm_blob", ".txcap_blob"};
    memcpy(req.board_types,boards,sizeof(boards));
    const struct firmware *fw;
    char path[128], expected[5][256];
    for(size_t e = 0; e < ARRAY_SIZE(exts); e++) {
        snprintf(path,sizeof(path),"brcm/brcmfmac4350c2-pcie%s",exts[e]);
        req.items[0].path = path;
        req.items[0].flags = e ? BRCMF_FW_REQF_OPTIONAL : 0;
        for(size_t b = 0; b < 4; b++)
            snprintf(expected[b],sizeof(expected[b]),"brcm/brcmfmac4350c2-pcie.%s%s",boards[b],exts[e]);
        strcpy(expected[4],path);
        for(int found = 0; found <= 5; found++) {
            reset(); available = found < 5 ? expected[found] : NULL;
            assert(brcmf_fw_request_firmware(&fw,&ctx) == (found < 5 ? 0 : -ENOENT));
            assert(calls == (found < 5 ? found + 1 : 5));
            for(int i = 0; i < calls; i++) assert(!strcmp(requested[i],expected[i]));
            assert(warnings == (found >= 4 && e == 0));
        }
        reset(); req.board_types[1] = NULL;
        assert(brcmf_fw_request_firmware(&fw,&ctx) == -ENOENT);
        assert(calls == 2 && !strcmp(requested[1],path));
        req.board_types[1] = boards[1];
        reset(); fail_alloc = true;
        assert(brcmf_fw_request_firmware(&fw,&ctx) == -ENOENT);
        assert(calls == 1 && !strcmp(requested[0],path));
    }
    assert(!brcm_alt_fw_path("no_extension",boards[0]));
    assert(!brcm_alt_fw_path(".hidden",boards[0]));
    assert(!brcm_alt_fw_path("file.bin",NULL));
    req.items[0].type = BRCMF_FW_TYPE_NVRAM;
    for(int optional = 0; optional < 2; optional++) {
        req.items[0].flags = optional ? BRCMF_FW_REQF_OPTIONAL : 0;
        reset();
        assert(brcmf_fw_complete_request(NULL,&ctx) == (optional ? 0 : -ENOENT));
        if(optional) assert(!req.items[0].nv_data.data && !req.items[0].nv_data.len);
        reset(); fail_parse = true;
        assert(brcmf_fw_complete_request(&blob,&ctx) == (optional ? 0 : -ENOENT));
        assert(parse_calls == 1 && release_calls == 1);
        if(optional) assert(!req.items[0].nv_data.data && !req.items[0].nv_data.len);
        reset();
        assert(!brcmf_fw_complete_request(&blob,&ctx));
        assert(req.items[0].nv_data.data == fake_data && req.items[0].nv_data.len == 4);
    }
    req.items[0].type = BRCMF_FW_TYPE_BINARY;
    req.items[0].flags = 0;
    assert(brcmf_fw_complete_request(NULL,&ctx) == -ENOENT);
    req.items[0].flags = BRCMF_FW_REQF_OPTIONAL;
    assert(!brcmf_fw_complete_request(NULL,&ctx));
    puts("PASS: four file types x six lookup outcomes; gaps/OOM fallback; optional NVRAM absence/parser-failure policy");
}
'''

def extract(source: str, signature: str) -> str:
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    for i in range(opening + 1, len(source)):
        depth += (source[i] == "{") - (source[i] == "}")
        if depth == 0:
            return source[start:i + 1]
    raise ValueError("unterminated function")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--cc", default=os.environ.get("CC", "gcc"))
    parser.add_argument("--sanitize", action="store_true")
    args = parser.parse_args()
    data = args.source.read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        parser.error("source is not the audited Hoolock firmware.c")
    source = data.decode()
    functions = [extract(source, signature) for signature in (
        "static int brcmf_fw_request_nvram_done(",
        "static int brcmf_fw_complete_request(",
        "static char *brcm_alt_fw_path(",
        "static int brcmf_fw_request_firmware(",
    )]
    with tempfile.TemporaryDirectory(prefix="brcmfmac-loader-") as temp:
        cfile, binary = Path(temp)/"test.c", Path(temp)/"test"
        cfile.write_text(PRELUDE + "\n".join(functions) + TESTS)
        flags = ["-std=gnu11", "-Wall", "-Wextra", "-Werror", "-O1", "-g"]
        if args.sanitize:
            flags += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
        subprocess.run([args.cc, *flags, str(cfile), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print("Host policy only: no real NVRAM parse, async callback, kernel build or J81 firmware compatibility validation")

if __name__ == "__main__":
    main()
