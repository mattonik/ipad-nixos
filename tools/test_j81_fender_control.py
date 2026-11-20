#!/usr/bin/env python3
"""Run J81 19H394 Fender predicates against host RAM on an Apple Silicon Mac."""
import argparse
from pathlib import Path
import platform
import struct
import subprocess
import tempfile

from audit_j81_pmgr_start import checked_file

# Text file offsets and lengths in the digest-checked kernel. The test excludes
# the guard's timeout/logging tail and supplies only idle (busy-bit-clear) inputs.
METHODS = (
    ("state", 0x18, 0x1b44f24, 0x20),
    ("literal", 0x58, 0x1b48224, 0x14),
    ("store", 0x68, 0x1b483c8, 0x10),
    ("control", 0x70, 0x1b483d8, 0x0c),
    ("bit29", 0x78, 0x1b483e4, 0x20),
    ("fallback", 0x98, 0x1b48444, 0x64),
    ("guard", 0xa0, 0x1b484a8, 0xa4),
)

HARNESS = """
#include <assert.h>
#include <stdint.h>
#include <stdio.h>

struct object {
    void (**slots)(void);
    uint32_t unused;
    uint8_t enabled;
    uint8_t padding[3];
    uint32_t *regs;
};
extern unsigned state(struct object *), control(struct object *), bit29(struct object *);
extern unsigned guard(struct object *), fallback(struct object *);
extern void literal(struct object *), store(struct object *, uint32_t);
int main(void) {
    void (*slots[21])(void) = { [3]=(void (*)(void))state,
        [14]=(void (*)(void))control, [20]=(void (*)(void))guard };
    uint32_t regs[1025] = {0};
    struct object obj = { .slots=slots, .regs=regs };
    for (unsigned high=0; high<8; high++)
        for (unsigned enabled=0; enabled<2; enabled++)
            for (unsigned perf=0; perf<2; perf++)
                for (unsigned kick=0; kick<2; kick++) {
                    uint32_t word = ((uint32_t)high << 29) | 0x1234;
                    obj.enabled=enabled; regs[2]=kick; regs[1024]=perf;
                    literal(&obj);
                    assert(regs[0] == 0x40000000u);
                    store(&obj, word);
                    assert(regs[0] == word && control(&obj) == word);
                    assert(bit29(&obj) == (high & 1));
                    unsigned zero_state = !enabled || !perf;
                    unsigned full = (high & 3) == 3 && zero_state && !kick;
                    assert(guard(&obj) == full);
                    assert(fallback(&obj) == (full || (zero_state && high/2 == 1)));
                }
    puts("PASS: 64 combinations of control[31:29], state enable, idle state and kick status");
}
"""


def run(kernel_path):
    kernel = checked_file(kernel_path, "c3507666766775dc854d5bcf6c375e6651ac8b2d1adb13d06331c60deb6a0008")
    # Signed word offsets relative to the switch's ADR, not the table base.
    cases = struct.unpack_from("<9i", kernel, 0x1b38ffc)
    if (0x668cadc + cases[0], 0x668cadc + cases[6]) != (0x668caec, 0x668caa0):
        raise ValueError("unexpected firmware event dispatch")
    print("Verified event switch: type 0 calls controller slot +0x388, type 6 advances", flush=True)
    assembly = [".text", ".p2align 2"]
    for name, slot, offset, size in METHODS:
        target, = struct.unpack_from("<Q", kernel, 0x23dbee8 + slot)
        if target != 0xfffffff00669c000 + offset - 0x1b48000:
            raise ValueError(f"unexpected Fender slot {slot:#x}")
        assembly.extend([f".globl _{name}", f"_{name}:"])
        assembly.extend(f".long 0x{word:08x}" for word, in
                        struct.iter_unpack("<I", kernel[offset:offset+size]))
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise SystemExit("vtable verified; native arithmetic test requires Apple Silicon macOS")
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp)
        (path / "fender.s").write_text("\n".join(assembly) + "\n")
        (path / "test.c").write_text(HARNESS)
        subprocess.run(["clang", "-Wall", "-Werror", "test.c", "fender.s", "-o", "test"],
                       cwd=path, check=True)
        subprocess.run([path / "test"], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel", type=Path)
    run(parser.parse_args().kernel)
