#!/usr/bin/env python3
"""Verify the two November 19 Linux GPU readers and working iPadOS access listing."""
import argparse
import hashlib
from pathlib import Path
import struct
import tarfile


def linux_reader(inbox, campaign, name, digest):
    stem = f"2026-11-19-j81-linux-{campaign}"
    path = inbox / (stem + "-prepared") / f"runner-src-{campaign}.tar.gz"
    with tarfile.open(path, "r:gz") as archive:
        data = archive.extractfile("boot/" + name).read()
    log_name = "timed-core.log" if campaign == "timed-core" else "core-id.log"
    log = (inbox / (stem + "-result") / "results" / log_name).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest or digest.encode() not in log:
        raise ValueError(f"{name} binary or logged run digest mismatch")
    return data


def words(binary, offset, expected):
    if struct.unpack_from(f"<{len(expected)}I", binary, offset) != expected:
        raise ValueError(f"instruction mismatch at ELF file offset {offset:#x}")


def check(inbox):
    # The text segment in these digest-pinned ELFs has file offset VA - 0x210000.
    late = linux_reader(inbox, "core-id", "gpu-core-id-gated",
                        "2bf8c5c3912d88c2de3db6307e6e0fce91d10b90a67453001cadff41f3389e78")
    words(late, 0x708, (0xd4000001, 0xb13ffc1f, 0x54000ba2, 0xd3422d48,
                        0x90ffff8c, 0xb868780a, 0xd5033d9f))
    print("Linux late: mmap syscall and result check precede indexed LDR W10 and DSB LD")
    timed = linux_reader(inbox, "timed-core", "gpu-gpc-timed-core",
                         "58e2f0254ef464d9dafec4094432d7a82b1f53b2fd6d85186d11a7492261c56a")
    words(timed, 0x680, (0xb9400542, 0xd5033d9f, 0x37f00222))
    words(timed, 0x6f0, (0x94000151,))
    words(timed, 0x700, (0xb9402262, 0x72ae440a, 0x528eec2b, 0xd5033d9f))
    print("Linux timed: page-5 gate, final checkpoint call, LDR W2 at +0x20, DSB LD")
    listing = (inbox / "2026-11-19-j81-ios-pregpc-miscacg-run-result" /
               "evidence/probe-module-full.dis").read_bytes()
    if hashlib.sha256(listing).hexdigest() != "1e3e7c5b7ba4c76679693843639cc489ef0d7e82704a6843098b55bfdab137f7":
        raise ValueError("iPadOS access listing digest mismatch")
    for site in (b"4478: 37f000c8", b"4490: d2a02000", b"4494: f2c00040",
                 b"449c: d374cc21", b"44a4: d63f0200", b"44ac: b5000098",
                 b"44cc: 91008300", b"44d0: 9400003d", b"45c4: b9400000",
                 b"45c8: d5033f9f"):
        if site not in listing:
            raise ValueError(f"missing iPadOS instruction {site!r}")
    print("iPadOS: page-5 gate, map call, non-null path, +0x20, LDR W0, DSB SY")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inbox", type=Path, help="builder-mailbox/from-builder directory")
    args = parser.parse_args()
    try:
        check(args.inbox)
    except (OSError, ValueError, KeyError, tarfile.TarError, struct.error) as error:
        parser.exit(1, f"{error}\n")
