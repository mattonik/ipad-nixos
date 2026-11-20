#!/usr/bin/env python3
"""Run the archived A8/A8X PMGR bank arithmetic on private host RAM."""
import argparse
import ctypes
from pathlib import Path
import platform
import re
import struct
import subprocess
import tempfile

from audit_j81_pmgr_start import checked_file


def assembly_words(data, start, end):
    return [f".long 0x{word:08x}" for word, in struct.iter_unpack("<I", data[start:end])]


def run(legacy_path, kernel_path, dump_path):
    legacy = checked_file(legacy_path, "b00e8cd0e05f4a7270cf2d38de9d0ab9e092ade4c1394a14224c0f7484b7233c")
    kernel = checked_file(kernel_path, "c3507666766775dc854d5bcf6c375e6651ac8b2d1adb13d06331c60deb6a0008")
    first = 0x22000
    dump = {int(k, 16): int(v, 16) for k, v in
            re.findall(r"^(0x[0-9a-f]+) (0x[0-9a-f]+)$", dump_path.read_text(), re.M | re.I)}
    if set(dump) != set(range(first, first + 0x400, 4)):
        raise ValueError("expected the complete 256-word Linux bank dump")
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise SystemExit("native test requires arm64 macOS with clang")
    # Stop the old routine immediately before its first voltage-manager access.
    asm = [".text", ".p2align 2", ".globl _legacy", "_legacy:",
           "str x19, [sp, #-16]!", "mov x19, x0"]
    asm += assembly_words(legacy, 0x538c, 0x5410)
    asm += ["ldr x19, [sp], #16", "ret", ".globl _modern", "_modern:"]
    # The original loop and its internal branches stay intact. Replace its two
    # external MMIO calls with plain loads/stores to the caller's RAM fixture.
    base = 0x21360c4  # file offset of kernel VA 0xfffffff006c8a0c4
    modern = assembly_words(kernel, base, base + 0xa0)
    for site, opcode, target in [(0x60, 0x9400034e, "Lread"), (0x78, 0x94000351, "Lwrite")]:
        if struct.unpack_from("<I", kernel, base + site)[0] != opcode:
            raise ValueError("unexpected stock MMIO call")
        modern[site // 4] = "bl " + target
    asm += modern + ["Lread:", "ldr x9, [x0, #0x6d0]", "ldr w0, [x9, w1, uxtw]", "ret",
                     "Lwrite:", "ldr x9, [x0, #0x6d0]", "str w2, [x9, w1, uxtw]", "ret"]

    bank = (ctypes.c_uint32 * ((first + 0x400) // 4))()
    obj = ctypes.create_string_buffer(0x1000)
    ctypes.c_void_p.from_buffer(obj, 0x6d0).value = ctypes.addressof(bank)
    legacy_j81 = {first + n for n in (0, 0x90, 0xa0, 0xb0, 0x130)}
    modern_set = {first + n for n in range(0, 0x181, 0x10)
                  if not (0x30 <= n <= 0x70 or n == 0x120)}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)
        (path / "bank.s").write_text("\n".join(asm) + "\n")
        subprocess.run(["clang", "-dynamiclib", "bank.s", "-o", "bank.dylib"], cwd=path, check=True)
        lib = ctypes.CDLL(str(path / "bank.dylib"))
        lib.legacy.argtypes = [ctypes.c_void_p]
        lib.modern.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        lib.legacy.restype = lib.modern.restype = None
        for mode, selected, enable in [
                ("J81", legacy_j81, True),
                ("T7000", (legacy_j81 - {first + 0x130}) | {first + 0x140}, True),
                ("19H394 on", modern_set, True), ("19H394 off", modern_set, False)]:
            for seed in ("snapshot", "all clear", "all set"):
                before = [dump[k] if seed == "snapshot" else
                          (k | (0x80000000 if seed == "all set" else 0)) for k in sorted(dump)]
                bank[first // 4:] = before
                if mode in ("J81", "T7000"):
                    obj[0x94e] = int(mode == "T7000")
                    lib.legacy(obj)
                else:
                    lib.modern(obj, int(enable))
                after = bank[first // 4:]
                want = [((v & 0x7fffffff) | (int(enable) << 31)) if k in selected else v
                        for k, v in zip(sorted(dump), before)]
                if after != want:
                    raise ValueError(f"bank mismatch: {mode}, {seed}")
                if seed == "snapshot" and mode in ("J81", "19H394 on"):
                    changed = {k for k, a, b in zip(sorted(dump), before, after) if a != b}
                    if changed != legacy_j81:
                        raise ValueError("Linux capture no longer gives the same five changes")
            print(f"PASS {mode}: all 256 words, captured and two synthetic input patterns")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("legacy_kext", "kernel", "linux_dump"):
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()
    run(args.legacy_kext, args.kernel, args.linux_dump)
