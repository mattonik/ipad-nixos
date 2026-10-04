#!/usr/bin/env python3
"""Exercise exact pinned OTP parsers before/after an inactive bounds patch.

Synthetic records only. No MMIO, firmware, kernel build or hardware access.
The host stubs cover bounded string helpers, not Linux ABI compatibility.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

from test_brcmfmac_otp_patch import SOURCE_PATH, SOURCE_SHA256

PATCH = Path(__file__).with_name("patches") / "0049-brcmfmac-pcie-otp-parser-bounds.patch"

PRELUDE = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <ctype.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
#define BRCMF_OTP_MAX_PARAM_LEN 16
#define PCIE 0
/* Check real debug format arguments, but don't log synthetic/private bytes. */
#define brcmf_dbg(level, ...) do { if (0) printf(__VA_ARGS__); } while (0)
struct brcmf_otp_params { char module[16], vendor[16], version[16]; bool valid; };
struct brcmf_pciedev_info { struct brcmf_otp_params otp; };
static uint32_t get_unaligned_le32(const void *pointer)
{
    const u8 *p = pointer;
    return p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static const char *skip_spaces(const char *p)
{
    while (isspace((unsigned char)*p)) p++;
    return p;
}
static long strscpy(char *destination, const char *source, size_t size)
{
    if (!size) return -E2BIG;
    size_t n = strnlen(source, size);
    size_t copied = n < size ? n : size - 1;
    memcpy(destination, source, copied);
    destination[copied] = 0;
    return n < size ? (long)n : -E2BIG;
}
'''

TESTS = r'''
static size_t record(u8 *out, const char *board)
{
    size_t n = strlen(board);
    assert(n + 6 <= 255);
    out[0] = 0x15; out[1] = (u8)(n + 6);
    out[2] = 8; out[3] = out[4] = out[5] = 0;
    out[6] = 0; /* Empty chip string is accepted by the pinned parser. */
    memcpy(out + 7, board, n + 1);
    return n + 8;
}
static bool cleared(const struct brcmf_pciedev_info *d)
{
    return !d->otp.valid && !d->otp.module[0] && !d->otp.vendor[0] && !d->otp.version[0];
}
static void check(u8 *data, size_t size, bool valid)
{
    struct brcmf_pciedev_info d;
    memset(&d, 0xa5, sizeof(d)); /* Also verify stale-state removal. */
    int ret = after_parse(&d, data, size);
    assert((ret == 0) == valid);
    assert(d.otp.valid == valid);
    if (!valid) assert(cleared(&d));
}
static uint32_t random_state = 0x4350;
static uint32_t next_random(void)
{
    random_state ^= random_state << 13;
    random_state ^= random_state >> 17;
    random_state ^= random_state << 5;
    return random_state;
}
int main(int argc, char **argv)
{
    struct brcmf_pciedev_info d = {0};
    u8 data[1024];
    size_t n;
    if (argc == 2 && !strcmp(argv[1], "original-zero")) {
        /* One allocated byte makes the second header read ASan-detectable. */
        u8 *zero = malloc(1); assert(zero); zero[0] = 0;
        int ret = before_parse(&d, zero, 0);
        free(zero);
        return ret == -EINVAL ? 0 : 1;
    }
    assert(argc == 1);
    n = record(data, "M=TEST V=x m=1.0");
    assert(before_parse(&d, data, n) == 0);
    assert(!strcmp(d.otp.module, "TEST") && !strcmp(d.otp.vendor, "x"));
    check(data, n, true);
    /* Actual original parser combines two individually incomplete records. */
    memset(&d, 0, sizeof(d));
    n = record(data, "M=FIRST");
    n += record(data + n, "V=y m=2.0");
    assert(before_parse(&d, data, n) == 0 && d.otp.valid);
    assert(!strcmp(d.otp.module, "FIRST") && !strcmp(d.otp.vendor, "y"));
    check(data, n, false);
    /* Original retains a successful result despite a truncated later record. */
    memset(&d, 0, sizeof(d));
    n = record(data, "M=TEST V=x m=1.0");
    data[n++] = 0x80; data[n++] = 255;
    assert(before_parse(&d, data, n) == 0 && d.otp.valid);
    check(data, n, false);
    check(NULL, 0, false);
    data[0] = 0; check(data, 1, false);
    data[0] = 0x15; check(data, 1, false);
    data[1] = 0; check(data, 2, false);
    n = record(data, "M=123456789abcdef V=x m=1"); check(data, n, true);
    n = record(data, "M=123456789abcdef V=123456789abcdef m=123456789abcdef");
    check(data, n, true);
    n = record(data, "M=123456789abcdef0 V=x m=1"); check(data, n, false);
    n = record(data, "M= V=x m=1"); check(data, n, false);
    n = record(data, "M=TEST V=x"); check(data, n, false);
    n = record(data, "M:TEST V=x m=1"); check(data, n, false);
    n = record(data, " M=TEST  V=x m=1 "); check(data, n, true);
    n = record(data, "Q=ok M=TEST V=x m=1"); check(data, n, true);
    n = record(data, "M=TEST V=x m=1"); data[2] = 9; check(data, n, false);
    n = record(data, "M=TEST V=x m=1"); data[n - 1] = 'X'; check(data, n, false);
    n = record(data, "M=TEST V=x m=1");
    memset(data + 6, 'X', n - 6); check(data, n, false);
    data[0] = 0x80; data[1] = 0; check(data, 2, false);
    n = record(data, "M=TEST V=x m=1");
    for (size_t length = 0; length < n; length++) check(data, length, false);
    data[n] = 0x80; check(data, n + 1, false);
    data[n] = 0; data[n + 1] = 255; check(data, n + 2, true);
    /* Unknown CIS before identity remains supported; no byte scanning. */
    data[0] = 0x80; data[1] = 1; data[2] = 7;
    n = 3 + record(data + 3, "M=TEST V=x m=1"); check(data, n, true);
    data[0] = 0x99; check(data, n, true);
    n = record(data, "M=ONE V=x m=1");
    n += record(data + n, "M=TWO V=y m=2");
    assert(after_parse(&d, data, n) == 0 && !strcmp(d.otp.module, "TWO"));
    n = record(data, "M=ONE V=x m=1");
    n += record(data + n, "V=y m=2"); check(data, n, false);
    /* Exact-sized allocations expose end-of-buffer reads to ASan. */
    for (unsigned int iteration = 0; iteration < 30000; iteration++) {
        size_t size = next_random() % 1025;
        u8 *input = size ? malloc(size) : NULL;
        assert(!size || input);
        for (size_t i = 0; i < size; i++) input[i] = (u8)next_random();
        if (size > 64 && iteration % 2) {
            size_t valid_size = record(data, "M=TEST V=x m=1");
            memcpy(input, data, valid_size);
        }
        memset(&d, 0xa5, sizeof(d));
        int ret = after_parse(&d, input, size);
        if (ret) assert(cleared(&d));
        else {
            assert(d.otp.valid && d.otp.module[0] && d.otp.vendor[0] && d.otp.version[0]);
            assert(memchr(d.otp.module, 0, 16) && memchr(d.otp.vendor, 0, 16) && memchr(d.otp.version, 0, 16));
        }
        free(input);
    }
    puts("PASS: original mixed-record/truncation reproducers, patched boundaries/state, 30000 deterministic synthetic inputs");
    return 0;
}
'''


def functions(source: str, prefix: str) -> str:
    start = source.index("static int\nbrcmf_pcie_parse_otp_sys_vendor(")
    end = source.index("static int brcmf_pcie_read_otp(", start)
    # Rename longer name first so only actual function definitions/calls change.
    return source[start:end].replace("brcmf_pcie_parse_otp_sys_vendor", prefix + "_vendor").replace(
        "brcmf_pcie_parse_otp", prefix + "_parse")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--cc", default=os.environ.get("CC", "gcc"))
    parser.add_argument("--sanitize", action="store_true")
    args = parser.parse_args()
    data = args.source.read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        parser.error("source SHA-256 differs from the reviewed Hoolock pin")
    with tempfile.TemporaryDirectory(prefix="brcmfmac-parser-") as directory:
        root = Path(directory)
        target = root / SOURCE_PATH
        target.parent.mkdir(parents=True)
        target.write_bytes(data)
        with PATCH.open("rb") as patch:
            subprocess.run(["patch", "--batch", "--fuzz=0", "-p1"], cwd=root, stdin=patch, check=True)
        harness = root / "test.c"
        constants = "#define BRCMF_OTP_SYS_VENDOR 0x15\n#define BRCMF_OTP_BRCM_CIS 0x80\n#define BRCMF_OTP_VENDOR_HDR 8\n"
        harness.write_text(PRELUDE + constants + functions(data.decode(), "before") +
                           functions(target.read_text(), "after") + TESTS)
        # Match kernel allowances in the unmodified baseline (u8/char pointers
        # and signed cursor comparisons); format checking stays enabled.
        command = [args.cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                   "-Wno-sign-compare", "-Wno-pointer-sign", "-O1", "-g"]
        if args.sanitize:
            command += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
        executable = root / "test"
        subprocess.run(command + [str(harness), "-o", str(executable)], check=True)
        subprocess.run([str(executable)], check=True)
        if args.sanitize:
            result = subprocess.run([str(executable), "original-zero"], capture_output=True, text=True)
            if result.returncode == 0 or "heap-buffer-overflow" not in result.stderr:
                raise RuntimeError("expected original zero-length ASan reproducer was not observed")
            print("CONFIRMED: original zero-length input triggers ASan heap-buffer-overflow")
    print("Patch 0049 remains inactive; no claim of a reachable hardware/kernel fault")


if __name__ == "__main__":
    main()
