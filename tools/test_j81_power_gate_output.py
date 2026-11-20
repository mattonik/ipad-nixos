#!/usr/bin/env python3
"""Run the ordinary 19H394 PMGR power callback action against host RAM."""
import argparse
import ctypes as c
import platform
from pathlib import Path
import struct
import subprocess
import tempfile

from audit_j81_pmgr_start import checked_file, property_at
from test_j81_bank_enable import assembly_words


def run(kernel_path, tree_path):
    kernel = checked_file(kernel_path, "c3507666766775dc854d5bcf6c375e6651ac8b2d1adb13d06331c60deb6a0008")
    tree = checked_file(tree_path, "be3158284d25e5d1217b970327ce2414d3046a2feb6a7b4410697b66df438003")
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise SystemExit("requires arm64 macOS and clang")
    records = property_at(tree, 0x74f8, b"devices")
    gfx, = (row for row, in struct.iter_unpack("48s", records) if row[32:].rstrip(b"\0") == b"GFX")
    ps = c.create_string_buffer(property_at(tree, 0x6a1c, b"ps-regs"))
    record = c.create_string_buffer(gfx)
    # Relocate the original two BL targets. Device lookup checks the ID and
    # returns the board's record. Virtual read +980 below serves the PS samples.
    action = assembly_words(kernel, 0x2084984, 0x2084ae4)
    for pc, target, label in [(0x6bd89ac, 0x6bc7624, "Llookup"),
                              (0x6bd89cc, 0x6bd1dec, "Lstatus"),
                              (0x6bd89e4, 0x6bd1dec, "Lstatus")]:
        index = (pc - 0x6bd8984) // 4
        expected = 0x94000000 | (((target - pc) // 4) & 0x3ffffff)
        if action[index] != f".long 0x{expected:08x}":
            raise ValueError(f"unexpected call at {pc:#x}")
        action[index] = "bl " + label
    lines = [".text", ".globl _action", "_action:", *action,
             "Llookup:", "cmp w1, #0x7c", "b.ne Lbad", "ldr x0, [x0, #8]", "ret",
             "Lbad:", "brk #1", "Lstatus:", *assembly_words(kernel, 0x207ddec, 0x207e12c)]
    obj = c.create_string_buffer(0x2600)
    vtable = c.create_string_buffer(0x988)
    for offset, value in [(0, vtable), (8, record), (0x25f0, ps)]:
        c.c_void_p.from_buffer(obj, offset).value = c.addressof(value)

    reads = []
    samples = (0, 0)

    @c.CFUNCTYPE(c.c_uint32, c.c_void_p, c.c_uint32, c.c_uint32, c.c_uint32)
    def read_word(owner, region, offset, instance):
        reads.append((owner, region, offset, instance))
        return samples[min(len(reads) - 1, 1)]

    c.c_void_p.from_buffer(vtable, 0x980).value = c.cast(read_word, c.c_void_p).value
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)
        (path / "power.s").write_text("\n".join(lines) + "\n")
        subprocess.run(["clang", "-dynamiclib", "power.s", "-o", "power.dylib"], cwd=path, check=True)
        action_fn = c.CDLL(str(path / "power.dylib")).action
        action_fn.argtypes = [c.c_void_p, c.c_uint32, c.c_void_p]
        action_fn.restype = None
        for samples, flag, has_output, expected, count in [
                ((0, 0), 0, True, 0, 2), ((0xf, 0xf), 0, True, 0, 2),
                ((0x100, 0), 0, True, 1, 1), ((0, 0x200), 0, True, 1, 2),
                ((0x200, 0), 0, True, 0, 2), ((0x3ff, 0), 0, True, 1, 1),
                ((0x3ff, 0), 0x10, True, 0, 0), ((0x3ff, 0), 0, False, 99, 0)]:
            record[0] = flag
            reads.clear()
            out = c.c_uint32(99)
            before = (obj.raw, record.raw, ps.raw)
            action_fn(obj, gfx[3], c.byref(out) if has_output else None)
            if (out.value != expected or reads != [(c.addressof(obj), 0, 0x20320, 0)] * count
                    or before != (obj.raw, record.raw, ps.raw)):
                raise ValueError(f"power callback mismatch for {samples}, {flag}, {has_output}")
    print("PASS: eight cases, PS region/offset/instance, read order/count, output and unchanged fixtures")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel", type=Path)
    parser.add_argument("j81dt", type=Path)
    args = parser.parse_args()
    run(args.kernel, args.j81dt)
