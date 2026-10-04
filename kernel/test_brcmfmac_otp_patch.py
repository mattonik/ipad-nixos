#!/usr/bin/env python3
"""Compile actual pinned firmware-selection functions with host API stubs.

Requires a local copy of the pinned Hoolock brcmfmac/pcie.c, not hardware or
firmware. The patch remains unapplied to every payload. This harness validates
filename selection only, not OTP MMIO, firmware loading or kernel integration.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile


SOURCE_SHA256 = "2bc4ff2f06eb515b404e08973a39c029ec975155a17a7baaf6f62e76ca181b4c"
SOURCE_PATH = "drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c"
PATCH = Path(__file__).with_name("patches") / "0048-brcmfmac-pcie-otp-without-antenna-sku.patch"

PRELUDE = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define GFP_KERNEL 0
#define PCIE 0
#define brcmf_dbg(...) ((void)0)
#define BRCMF_PCIE_FW_CODE 0
#define BRCMF_PCIE_FW_NVRAM 1
#define BRCMF_PCIE_FW_CLM 2
#define BRCMF_PCIE_FW_TXCAP 3
#define BRCMF_FW_TYPE_BINARY 1
#define BRCMF_FW_TYPE_NVRAM 2
#define BRCMF_FW_REQF_OPTIONAL 1
struct device { int unused; };
struct pci_bus { unsigned int number; };
struct pci_dev { struct device dev; struct pci_bus *bus; };
struct chip { unsigned int chip, chiprev; };
struct settings { const char *board_type, *antenna_sku; };
struct brcmf_otp_params { char module[16], vendor[16], version[16]; bool valid; };
struct brcmf_pciedev_info {
    struct chip *ci;
    struct settings *settings;
    struct pci_dev *pdev;
    struct brcmf_otp_params otp;
    char fw_name[256], nvram_name[256], clm_name[256], txcap_name[256];
};
struct item { int type, flags; };
struct brcmf_fw_request {
    unsigned int domain_nr, bus_nr;
    const char *board_types[8];
    struct item items[4];
};
struct brcmf_fw_name { const char *extension; char *path; };
static const int brcmf_pcie_fwnames[] = { 0 };
static bool fail_request;
static int allocation_calls, fail_at = -1, request_live;
static void *managed[16];
static size_t managed_count;
static unsigned int pci_domain_nr(struct pci_bus *bus) { (void)bus; return 2; }
static struct brcmf_fw_request *brcmf_fw_alloc_request(
    unsigned int chip, unsigned int chiprev, const void *map, size_t maps,
    struct brcmf_fw_name *names, size_t count)
{
    (void)chip; (void)chiprev; (void)map; (void)maps;
    assert(count == 4);
    assert(strcmp(names[0].extension, ".bin") == 0);
    assert(strcmp(names[1].extension, ".txt") == 0);
    assert(strcmp(names[2].extension, ".clm_blob") == 0);
    assert(strcmp(names[3].extension, ".txcap_blob") == 0);
    if (fail_request) return NULL;
    struct brcmf_fw_request *request = calloc(1, sizeof(*request));
    assert(request);
    request_live++;
    return request;
}
static char *devm_kasprintf(struct device *dev, int flags, const char *format, ...)
{
    (void)dev; (void)flags;
    if (allocation_calls++ == fail_at) return NULL;
    va_list args, copy;
    va_start(args, format);
    va_copy(copy, args);
    int size = vsnprintf(NULL, 0, format, copy);
    va_end(copy);
    assert(size >= 0);
    char *value = malloc((size_t)size + 1);
    assert(value);
    assert(vsnprintf(value, (size_t)size + 1, format, args) == size);
    va_end(args);
    assert(managed_count < ARRAY_SIZE(managed));
    managed[managed_count++] = value;
    return value;
}
static void kfree(void *value) { assert(request_live == 1); request_live--; free(value); }
static void cleanup(void)
{
    assert(request_live == 0);
    for (size_t i = 0; i < managed_count; i++) free(managed[i]);
    managed_count = 0;
    allocation_calls = 0;
    fail_at = -1;
    fail_request = false;
}
'''

TESTS = r'''
typedef struct brcmf_fw_request *(*prepare_fn)(struct brcmf_pciedev_info *);
static void check(prepare_fn fn, struct brcmf_pciedev_info *info,
                  const char **expected, size_t count, int allocations)
{
    struct brcmf_fw_request *request = fn(info);
    assert(request);
    for (size_t i = 0; i < count; i++)
        assert(request->board_types[i] && strcmp(request->board_types[i], expected[i]) == 0);
    for (size_t i = count; i < ARRAY_SIZE(request->board_types); i++)
        assert(request->board_types[i] == NULL);
    assert(allocation_calls == allocations);
    assert(request->domain_nr == 3 && request->bus_nr == 7);
    assert(request->items[0].type == BRCMF_FW_TYPE_BINARY && request->items[0].flags == 0);
    assert(request->items[1].type == BRCMF_FW_TYPE_NVRAM);
    for (size_t i = 1; i < 4; i++) assert(request->items[i].flags == BRCMF_FW_REQF_OPTIONAL);
    assert(request->items[2].type == BRCMF_FW_TYPE_BINARY);
    assert(request->items[3].type == BRCMF_FW_TYPE_BINARY);
    kfree(request);
    cleanup();
}
int main(void)
{
    struct chip chip = { 4350, 7 };
    struct pci_bus bus = { 7 };
    struct pci_dev pdev = { .bus = &bus };
    struct settings settings = { "apple,synthetic", "X3" };
    struct brcmf_pciedev_info info = { .ci = &chip, .pdev = &pdev, .settings = &settings,
        .otp = { .module = "MOD", .vendor = "v", .version = "1.0", .valid = true } };
    const char *sku[] = { "apple,synthetic-MOD-v-1.0-X3", "apple,synthetic-MOD-v-1.0",
        "apple,synthetic-MOD-v", "apple,synthetic-MOD", "apple,synthetic-X3", "apple,synthetic" };
    const char *no_sku[] = { "apple,synthetic-MOD-v-1.0", "apple,synthetic-MOD-v",
        "apple,synthetic-MOD", "apple,synthetic" };
    const char *platform[] = { "apple,synthetic" };
    check(prepare_before, &info, sku, 6, 5);
    check(prepare_after, &info, sku, 6, 5);
    settings.antenna_sku = NULL;
    check(prepare_before, &info, platform, 1, 0);
    check(prepare_after, &info, no_sku, 4, 3);
    for (int sku_present = 0; sku_present < 2; sku_present++) {
        settings.antenna_sku = sku_present ? "X3" : NULL;
        info.otp.valid = false;
        check(prepare_before, &info, platform, 1, 0);
        check(prepare_after, &info, platform, 1, 0);
        settings.board_type = NULL;
        info.otp.valid = true;
        check(prepare_before, &info, NULL, 0, 0);
        check(prepare_after, &info, NULL, 0, 0);
        settings.board_type = "apple,synthetic";
        /* Exercise every string-allocation failure without returning a partial list. */
        for (int i = 0; i < (sku_present ? 5 : 3); i++) {
            fail_at = i;
            assert(prepare_after(&info) == NULL);
            cleanup();
        }
        fail_request = true;
        assert(prepare_after(&info) == NULL);
        assert(allocation_calls == 0);
        cleanup();
    }
    /* Maximum OTP field width: no truncation, invented SKU or hole in the list. */
    settings.antenna_sku = NULL;
    strcpy(info.otp.module, "123456789abcdef");
    strcpy(info.otp.vendor, "123456789abcdef");
    strcpy(info.otp.version, "123456789abcdef");
    const char *maximum[] = {
        "apple,synthetic-123456789abcdef-123456789abcdef-123456789abcdef",
        "apple,synthetic-123456789abcdef-123456789abcdef",
        "apple,synthetic-123456789abcdef", "apple,synthetic" };
    check(prepare_after, &info, maximum, 4, 3);
    puts("PASS: legacy SKU order, absent-SKU order, null termination, fallbacks, request metadata, allocation failures, maximum OTP widths");
    return 0;
}
'''


def function(source: str, name: str) -> str:
    # The file also has a forward declaration; select the actual definition.
    start = source.rindex("static struct brcmf_fw_request *\nbrcmf_pcie_prepare_fw_request(")
    end = source.index("\n#ifdef DEBUG", start)
    return source[start:end].replace("brcmf_pcie_prepare_fw_request", name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="exact pinned Hoolock pcie.c")
    parser.add_argument("--cc", default=os.environ.get("CC", "gcc"))
    parser.add_argument("--sanitize", action="store_true")
    args = parser.parse_args()
    data = args.source.read_bytes()
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        parser.error("source SHA-256 differs from the reviewed Hoolock pin")
    original = data.decode()
    otp_reader = original[original.index("static int brcmf_pcie_read_otp("):original.index("#define BRCMF_PCIE_FW_CODE")]
    assert "case BRCM_CC_4350_CHIP_ID:" not in otp_reader
    assert "/* OTP not supported on this chip */\n\t\treturn 0;" in otp_reader

    with tempfile.TemporaryDirectory(prefix="brcmfmac-otp-") as directory:
        root = Path(directory)
        target = root / SOURCE_PATH
        target.parent.mkdir(parents=True)
        target.write_bytes(data)
        with PATCH.open("rb") as patch:
            subprocess.run(["patch", "--batch", "--fuzz=0", "-p1"], cwd=root, stdin=patch, check=True)
        patched = target.read_text()
        harness = root / "test.c"
        harness.write_text(PRELUDE + function(original, "prepare_before") +
                           function(patched, "prepare_after") + TESTS)
        command = [args.cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-O1", "-g"]
        if args.sanitize:
            command += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
        subprocess.run(command + [str(harness), "-o", str(root / "test")], check=True)
        subprocess.run([str(root / "test")], check=True)
    print("BCM4350 OTP reader remains absent; patch is not wired into any kernel/payload")


if __name__ == "__main__":
    main()
