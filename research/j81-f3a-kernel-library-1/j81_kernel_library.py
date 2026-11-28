#!/usr/bin/env python3
"""J81 (A8X) compute kernel library, request 36: USC kernels, PDS programs and CDM streams.

usage:
  j81_kernel_library.py list                       print the tests in their safe order
  j81_kernel_library.py dump TEST                  print every word with its byte offset and meaning
  j81_kernel_library.py payload TEST OUT_FILE      write a payload file in j81_j2c_payload.py's format
  j81_kernel_library.py grid                       print the encoder grid (to diff against Orchard's C encoders)

Encodings are transcribed (not copied as binaries) from public MIT sources:
  OrchardLinux/mesa 7df85604e5 src/imagination/g9p/g9p_isa.h (the A8 forms behind g5p_usc_g4p),
  src/imagination/g5p/g5p_cdm.h, src/imagination/vulkan/pvr_arch_g5p_compute.c;
  OrchardLinux/gpu e03c572de2 tools/a10/tools/isa/g9p.py and gen-tests.py (the A10 forms and test shapes).
Constants that Orchard quotes from Apple's A8 output are small field values (e.g. the store 2510 0504 8100 4020).

Heap layout (VA 0x3_00000000, the A8's single PDS/USC execution base, offsets below are from it):
  +0x040 empty USC kernel (66 bytes)          +0x100 end-of-pass PDS data   +0x120 end-of-pass PDS code
  +0x140 fence PDS data (zero)                +0x160 fence PDS code
  +0x180 binding PDS data (<= 16 dwords)      +0x1c0 binding PDS code (<= 8 words)
  +0x1e0 kernel PDS data (4 dwords)           +0x200 kernel PDS code (<= 8 words)
  +0x240 argument table (u64 buffer VAs)      +0x280 thread-count block {N | N << 16, 0, 0, 0} (own 64-byte line)
  +0x300 the test kernel (USC code, 64-byte aligned, up to +0x800)
  +0x800 input A (0x400 bytes)                +0xc00 input B (0x400 bytes)     image size 0x1000
Output: the page at OUT_VA (0x203000), every word pre-filled with SENTINEL.
"""
import struct
import sys

HEAP_VA = 0x300000000
OUT_VA = 0x203000
SENTINEL = 0xDEAD0001

OFF = dict(empty=0x040, eop_data=0x100, eop_code=0x120, fence_data=0x140, fence_code=0x160,
           bind_data=0x180, bind_code=0x1C0, kdata=0x1E0, kcode=0x200, args=0x240, count=0x280,
           kernel=0x300, in_a=0x800, in_b=0xC00, size=0x1000)

# ---------------------------------------------------------------- USC encoders (A8 compute forms)
# Each returns one instruction as a list of 16-bit words. Register numbers are 32-bit registers.


def prologue(nbuf, common):
    """Program entry: compare r0 (local index) with the thread count at common dword 2*nbuf, disable lanes past it.
    The A8 clears W1 bit 15 when the kernel record has a common store (it reads the workgroup ID)."""
    return [0x1181, (0x0181 if common else 0x8181) | 2 * (4 * nbuf), 0x4100, 0xACB7]


def push_init(st):
    return [0x01C8, 0x0300 | 2 * st, 0x0101, 0x0120, 0x46D1]


def pop_final(st):
    """The program's last stack operation (g9p_pop: last-read bit 7 set)."""
    return [0x21C8, 0x0300 | 2 * st, 0x0180 | st << 2, 0x46D2]


def pop_levels(st, levels):
    """An intermediate pop, A9/A8 compute rule (a9_stack): no last-read bit."""
    return [0x21C8, 0x0300 | 2 * st, 0x0100 | st << 2, 0x0600 | 0xD2 | levels << 14]


def push_if(st, invert=False):
    return [0x21C8, 0x0300 | 2 * st, 0x0100 | st << 2, 0x46D1 | invert << 13]


def else_(st):
    return [0x21C8, 0x0300 | 2 * st, 0x0100 | st << 2, 0x46D4]


def loop_begin(st):
    return [0x21C8, 0x0300 | 2 * st, 0x0100 | st << 2, 0x86D0]


def loop_break(st, when_true):
    return [0x21C8, 0x0300 | 2 * st, 0x0100 | st << 2, 0x86D7 | when_true << 13]


def mov_imm(dst, imm):
    imm &= 0xFFFFFFFF
    w0 = 0x0198 | ((imm >> 9) & 1) << 13
    w2 = 0x0101 | (imm & 0x3F) << 1
    w3 = (0x0120 | ((imm >> 6) & 7) << 1 | ((imm >> 10) & 1) << 4 | ((imm >> 14) & 1) << 6 |
          ((imm >> 15) & 1) << 7 | ((imm >> 11) & 7) << 12)
    words = [w0, 0x0300 | 2 * dst, w2, w3]
    if imm >> 16:
        words[3] |= 1 | ((imm >> 24) & 1) << 15
        words.append(0x0100 | ((imm >> 16) & 0xFF) | ((imm >> 25) & 0x7F) << 9)
    return words + [0x0154, 0x0038]


def mov_cs(dst, u):
    """dst = common-store dword u (Apple's A8 common-store move)."""
    return [0x0198, 0x0300 | 2 * dst, 0x0181 | (u & 31) << 2, 0x4100 | ((u >> 5) & 7) << 1, 0x0154, 0x0038]


def shift_imm(dst, a, n, right=False):
    """dst = a << n (or >> n, logical): the A8's literal shift."""
    return [0x519E if right else 0x119A, (0 if right else 0x8000) | 0x0300 | 2 * dst, 0x0101 | a << 10, 0x0120,
            0x0101 | (n & 31) << 1, 0x0120, 0x14F4 if right else 0x14F0]


def srcs(a, b, kill):
    return 0x0100 | a << 2 | b << 10 | (0x8080 if kill else 0)


IADD, IMUL, ISUB, AND, OR, XOR = 0xA1, 0xA2, 0xA5, 0xC8, 0xCE, 0xC6
ULT, UGT, EQ, SLT, SGT = 0xB6, 0xB7, 0xBD, 0xBE, 0xBF


def alu2(op, dst, a, b, kill=False):
    return [0x3199, 0x0300 | 2 * dst, srcs(a, b, kill), op]


def add_imm(dst, src, imm):
    assert 0 <= imm < 0x40 and src < 16
    return [0x1199, 0x0300 | 2 * dst, 0x0101 | imm << 1 | src << 10, 0x0120, 0x09A1, 0x0070]


def cmp_imm(cond, reg, imm):
    assert 0 <= imm < 0x400 and reg < 16
    return [0x1181 | ((imm >> 9) & 1) << 13, 0x0101 | (imm & 0x3F) << 1 | reg << 10,
            0x0120 | ((imm >> 6) & 7) << 1, 0xA100 | cond, 0x0070]


def cmp_reg(cond, a, b):
    return [0x3181, srcs(a, b, False), 0xA000 | cond]


def addr(dst, u, idx, kill=False):
    """r[dst]:r[dst+1] = (common dwords u, u+1) + r[idx] (32-bit byte offset), the A8 carry build, 4 instructions."""
    hi = dst + 1
    assert idx not in (dst, hi) and idx < 16 and hi < 16
    ue, u1e = 0x4100 | ((u >> 5) & 7) << 1, 0x4100 | (((u + 1) >> 5) & 7) << 1
    return [[0x119D, 0x0300 | 2 * hi, 0x0101 | (u & 31) << 2 | idx << 10, ue, 0x00A5],
            [0x0198, 0x0300 | 2 * dst, 0x0181 | ((u + 1) & 31) << 2, u1e, 0x0154, 0x0038],
            [0x3199, 0x0300 | 2 * hi, (0x81 | (2 * hi + 1) << 1) << 8 | 0x80 | (2 * dst) << 1, 0x08A1],
            [0x1199, 0x0300 | 2 * dst, 0x0181 | (u & 31) << 2 | idx << 10 | (0x8000 if kill else 0), ue, IADD]]


U8, U16, U32, U32X2 = 1, 2, 4, 5


def mem(store, size, reg, pair):
    """The A8 compute load/store through the address pair r[pair]:r[pair+1]."""
    return [size << 11 | 0x0510, 0x0500 | reg << 1, (0x8100 if store else 0x0100) | pair << 1, 0x4020 if store else 0x0020]


WAIT = [0x004D]


def tg_load(dst):
    """dst = threadgroup word 0 (workgroup ID x, written by the kernel task's PDS); follow with WAIT."""
    return [0x1516, 2 * dst]


def jump(op, off):
    off &= 0xFFFFFFFF
    return [op, (off & 0xFEFE) | 0x0100 | (off >> 8 & 1), (off >> 16 & 0xFEFE) | (off >> 24 & 1)]


JMP, JMP_NONE, JMP_ANY = 0x0100, 0x0900, 0x0101

# ---------------------------------------------------------------- assembler


def assemble(items):
    """items: (note, words) | 'label' | (note, op, 'label'). The label 'end' is the end word at the next 64-byte
    boundary after the last instruction. Returns [(byte offset, words, note)] including padding and the end word."""
    def size(it):
        return 0 if isinstance(it, str) else 6 if len(it) == 3 else 2 * len(it[1])
    pos, at = 0, {}
    for it in items:
        if isinstance(it, str):
            at[it] = pos
        pos += size(it)
    at['end'] = (pos + 63) // 64 * 64
    out, pos = [], 0
    for it in items:
        if isinstance(it, str):
            continue
        if len(it) == 3:
            note, op, label = it
            words = jump(op, at[label] - pos)
            note = f"{note} (to +{at[label]:#x})"
        else:
            note, words = it
        out.append((pos, words, note))
        pos += 2 * len(words)
    if at['end'] > pos:
        out.append((pos, [0xC000] * ((at['end'] - pos) // 2), 'padding'))
    out.append((at['end'], [0x8000], 'end'))
    return out


def flat(listing):
    return [w for _, ws, _ in listing for w in ws]


def code_bytes(listing):
    return struct.pack(f"<{len(flat(listing))}H", *flat(listing))


def address(dst, u, idx, what):
    return [(f"{what}: r{dst + 1} = carry(s{u} + r{idx}) (result's high half)", a) if i == 0 else
            (f"{what}: r{dst} = s{u + 1}", a) if i == 1 else
            (f"{what}: r{dst + 1} = r{dst} + r{dst + 1}.hi", a) if i == 2 else
            (f"{what}: r{dst} = s{u} + r{idx}", a) for i, a in enumerate(addr(dst, u, idx))]


def store_tail(data, pair, st):
    st_ins = mem(True, U32, data, pair)
    return [(f"skip the store when no lane is active", jump(JMP_NONE, 2 * (3 + len(st_ins)))),
            (f"store r{data} -> [r{pair}:r{pair + 1}]", st_ins),
            (f"epilogue: pop the mask stack r{st} (last-read)", pop_final(st)),
            ("jump to the end word", JMP, 'end')]


def log2(n):
    assert n & (n - 1) == 0 and n > 0, "power of two"
    return n.bit_length() - 1

# ---------------------------------------------------------------- kernels


def k_store1(imm=0xCAFE0001):
    """Request 34/35 store kernel, the run-99 regression: out[0] = imm (one buffer)."""
    return [("prologue (thread count at dword 2)", prologue(1, False)), ("start the mask stack in r3", push_init(3)),
            ("r0 = s0 (out low)", mov_cs(0, 0)), ("r1 = s1 (out high)", mov_cs(1, 1)), (f"r2 = {imm:#x}", mov_imm(2, imm)),
            *store_tail(2, 0, 3)], 4


def k_lid(_n=None):
    """out[i] = i, one workgroup (plain launch: r0 = local index)."""
    st = 4
    return [("prologue (thread count at dword 2)", prologue(1, False)), (f"start the mask stack in r{st}", push_init(st)),
            ("r1 = r0 << 2 (byte offset)", shift_imm(1, 0, 2)), *address(2, 0, 1, "out + r1"),
            *store_tail(0, 2, st)], 5


def k_gid(n):
    """out[wg*N + i] = wg*N + i (workgroup ID from threadgroup word 0)."""
    st = 6
    return [("prologue, common-store form (thread count at dword 2)", prologue(1, True)),
            (f"start the mask stack in r{st}", push_init(st)),
            ("r1 = threadgroup word 0 (workgroup ID x)", tg_load(1)), ("wait for the load", WAIT),
            (f"r1 = r1 << {log2(n)} (wg * N)", shift_imm(1, 1, log2(n))), ("r1 = r1 + r0 (global index)", alu2(IADD, 1, 1, 0)),
            ("r2 = r1 << 2 (byte offset)", shift_imm(2, 1, 2)), *address(4, 0, 2, "out + r2"),
            *store_tail(1, 4, st)], 7


def k_ldcopy(_n=None):
    """out[i] = in[i] (in: dwords 0-1, out: dwords 2-3)."""
    st = 6
    return [("prologue (thread count at dword 4)", prologue(2, False)), (f"start the mask stack in r{st}", push_init(st)),
            ("r1 = r0 << 2", shift_imm(1, 0, 2)), *address(2, 0, 1, "in + r1"),
            ("load r4 <- [r2:r3]", mem(False, U32, 4, 2)), ("wait for the load", WAIT),
            *address(2, 2, 1, "out + r1"), *store_tail(4, 2, st)], 7


def k_ldk(k):
    """out[i] = in[i] + k: k < 64 uses the add-immediate form, else a move-immediate and a register add."""
    st = 6
    body = [("prologue (thread count at dword 4)", prologue(2, False)), (f"start the mask stack in r{st}", push_init(st)),
            ("r1 = r0 << 2", shift_imm(1, 0, 2)), *address(2, 0, 1, "in + r1"),
            ("load r4 <- [r2:r3]", mem(False, U32, 4, 2)), ("wait for the load", WAIT)]
    if k < 0x40:
        body.append((f"r4 = r4 + {k:#x} (add immediate)", add_imm(4, 4, k)))
    else:
        body += [(f"r5 = {k:#x}", mov_imm(5, k)), ("r4 = r4 + r5 (last use of both)", alu2(IADD, 4, 4, 5, True))]
    return body + [*address(2, 2, 1, "out + r1"), *store_tail(4, 2, st)], 7


def k_vadd(n, wgid=True):
    """c[g] = a[g] + b[g], g = wg*N + i (a: dwords 0-1, b: 2-3, c: 4-5, thread count at dword 6)."""
    st = 7
    body = [(f"prologue{', common-store form' if wgid else ''} (thread count at dword 6)", prologue(3, wgid)),
            (f"start the mask stack in r{st}", push_init(st))]
    if wgid:
        body += [("r1 = threadgroup word 0 (workgroup ID x)", tg_load(1)), ("wait for the load", WAIT),
                 (f"r1 = r1 << {log2(n)} (wg * N)", shift_imm(1, 1, log2(n))), ("r1 = r1 + r0 (global index)", alu2(IADD, 1, 1, 0)),
                 ("r2 = r1 << 2 (byte offset)", shift_imm(2, 1, 2))]
    else:
        body += [("r2 = r0 << 2 (byte offset)", shift_imm(2, 0, 2))]
    body += [*address(4, 0, 2, "a + r2"), ("load r3 <- [r4:r5]", mem(False, U32, 3, 4)), ("wait for the load", WAIT),
             *address(4, 2, 2, "b + r2"), ("load r6 <- [r4:r5]", mem(False, U32, 6, 4)), ("wait for the load", WAIT),
             ("r3 = r3 + r6 (last use of both)", alu2(IADD, 3, 3, 6, True)), *address(4, 4, 2, "c + r2"),
             *store_tail(3, 4, st)]
    return body, 8


def k_loop(count, divergent=False):
    """out[i] = number of loop iterations: count (uniform) or (i & 3) + 1 (divergent: lanes leave at different
    iterations). The A10 countdown shape (gen-tests.py), with the compiler's exit jump after the break."""
    st = 7
    body = [("prologue (thread count at dword 2)", prologue(1, False)), (f"start the mask stack in r{st}", push_init(st)),
            ("r1 = r0 << 2", shift_imm(1, 0, 2)), *address(2, 0, 1, "out + r1")]
    if divergent:
        body += [("r4 = 3", mov_imm(4, 3)), ("r4 = r0 & r4", alu2(AND, 4, 0, 4)), ("r4 = r4 + 1 (count)", add_imm(4, 4, 1))]
    else:
        body += [(f"r4 = {count} (count)", mov_imm(4, count))]
    body += [("r5 = 0 (iterations)", mov_imm(5, 0)), ("r6 = 0xffffffff (-1: no register subtract on the A8)", mov_imm(6, 0xFFFFFFFF)),
             ("loop start: two mask levels", loop_begin(st)), 'body',
             ("r5 = r5 + 1", add_imm(5, 5, 1)), ("r4 = r4 + r6 (count - 1)", alu2(IADD, 4, 4, 6)),
             ("compare r4 >u 0", cmp_imm(UGT, 4, 0)), ("break the lanes whose compare failed (r4 == 0)", loop_break(st, False)),
             ("leave when no lane is left", JMP_NONE, 'after'), ("back to the body while any lane is active", JMP_ANY, 'body'),
             'after', ("after the loop: pop both levels (no last-read)", pop_levels(st, 2)),
             *store_tail(5, 2, st)]
    return body, 8


def k_condodd(_n=None):
    """if (i & 1) out[i] = i (the compiler's if/else shape with an empty else)."""
    st = 6
    st_ins = mem(True, U32, 0, 2)
    return [("prologue (thread count at dword 2)", prologue(1, False)), (f"start the mask stack in r{st}", push_init(st)),
            ("r1 = r0 << 2", shift_imm(1, 0, 2)), *address(2, 0, 1, "out + r1"),
            ("r4 = 1", mov_imm(4, 1)), ("r4 = r0 & r4", alu2(AND, 4, 0, 4)), ("compare r4 == 1", cmp_imm(EQ, 4, 1)),
            ("push: disable the lanes whose compare failed", push_if(st)), ("to the else when no lane is active", JMP_NONE, 'else'),
            ("store r0 -> [r2:r3]", st_ins), 'else', ("else: flip the lanes", else_(st)),
            ("to the pop when no lane is active", JMP_NONE, 'pop'), 'pop', ("pop the if level (no last-read)", pop_levels(st, 1)),
            (f"epilogue: pop the mask stack r{st} (last-read)", pop_final(st)), ("jump to the end word", JMP, 'end')], 7


def k_carry(_n=None):
    """out[0] = 0xc0ffee01 through base 0xffffffff_ffffff00 + offset 0x203100: lands on 0x203000 only if the carry
    reaches the high word (wraps to 0). Argument table entry 0 = 0xffffffffffffff00 instead of the output VA."""
    st = 4
    return [("prologue (thread count at dword 2)", prologue(1, False)), (f"start the mask stack in r{st}", push_init(st)),
            ("r1 = 0x203100 (offset)", mov_imm(1, 0x203100)), *address(2, 0, 1, "base + r1"),
            ("r0 = 0xc0ffee01", mov_imm(0, 0xC0FFEE01)), *store_tail(0, 2, st)], 5


def k_wgidraw(_n=None):
    """out[i] = workgroup ID (every group writes the same N slots: any non-zero value proves the ID arrives)."""
    st = 4
    return [("prologue, common-store form (thread count at dword 2)", prologue(1, True)),
            (f"start the mask stack in r{st}", push_init(st)),
            ("r5 = threadgroup word 0 (workgroup ID x)", tg_load(5)), ("wait for the load", WAIT),
            ("r1 = r0 << 2", shift_imm(1, 0, 2)), *address(2, 0, 1, "out + r1"), *store_tail(5, 2, st)], 6


def k_reg(r, alloc):
    """out[i] = 0x5a5a0000 | r through register r (r >= 5); the record allocates `alloc` registers."""
    st = 4
    return [("prologue (thread count at dword 2)", prologue(1, False)), (f"start the mask stack in r{st}", push_init(st)),
            ("r1 = r0 << 2", shift_imm(1, 0, 2)), *address(2, 0, 1, "out + r1"),
            (f"r{r} = {0x5A5A0000 | r:#x}", mov_imm(r, 0x5A5A0000 | r)), *store_tail(r, 2, st)], alloc


def k_loop_self(_n=None):
    """Request 35 t3a: jump to self (never ends; the watchdog test)."""
    return None, 0

# ---------------------------------------------------------------- PDS, records, stream


def pds_dout_a8(typ, src64, space, ctrl, end=False, cc=False):
    """A8 DOUT, Rogue layout: src1 (control-word data dword) in bits 16-23, src0 (space << 5 | 64-bit reg) in 8-14."""
    return 0xF0000000 | (1 << 26 if end else 0) | (1 << 27 if cc else 0) | ctrl << 16 | (space << 5 | src64) << 8 | typ


DOUTD, DOUTW, DOUTU, DOUTC = 0, 1, 2, 5
DATA, TEMPS = 0, 2
HALT = 0xD3000000


def bra_not_if1(t):
    return 0xC2C00000 | t


def binding(nbuf):
    """Binding DMA task: one DOUTD per buffer (2 dwords to common dword 2k), then the count (1 dword to dword
    2*nbuf). Apple's slot layout: 64-bit sources in data dwords 0..2T-1, control word of transfer k at 2T + 2k."""
    t = nbuf + 1
    data = [0] * (4 * t)
    code = []
    for k in range(t):
        src = HEAP_VA + OFF['args'] + 8 * k if k < nbuf else HEAP_VA + OFF['count']
        data[2 * k], data[2 * k + 1] = src & 0xFFFFFFFF, src >> 32
        last = k == t - 1
        data[2 * t + 2 * k] = (0x80000000 if last else 0) | 0x10000000 | (2 * k) << 13 | (1 if last else 2)
        code.append(pds_dout_a8(DOUTD, k, DATA, 2 * t + 2 * k, end=last))
    code.append(HALT)
    units = (len(data) + 3) // 4
    common = (2 * nbuf + 1 + 15) // 16
    return data, code, units, common


def kernel_pds(wgid, nregs):
    temps = 0x10 * ((max(nregs, 1) + 7) // 8)
    if wgid:
        data = [OFF['kernel'], temps, 0x90000002, 0x80000000]
        code = [bra_not_if1(3), pds_dout_a8(DOUTW, 0, TEMPS, 2), HALT, pds_dout_a8(DOUTW, 0, TEMPS, 3),
                pds_dout_a8(DOUTU, 0, DATA, 0, end=True, cc=True), HALT]
    else:
        data = [OFF['kernel'], temps, 0x80000000, 0]
        code = [bra_not_if1(2), HALT, pds_dout_a8(DOUTW, 0, TEMPS, 2), pds_dout_a8(DOUTU, 0, DATA, 0, end=True, cc=True), HALT]
    return data, code


def max_instances_a8(threads, one_wg_per_task=False, shared_bytes=0):
    if threads >= 32:
        return 0
    wgs = 1 if one_wg_per_task else (8 if threads < 5 else 32 // threads)
    m = (shared_bytes + 63) // 64
    if m and not one_wg_per_task:
        wgs = min(wgs, (m + 0x13F) // (2 * m - 1))
    return (wgs * threads) & 31


def hw_threads(n):
    return (n + 31) & ~31 if n > 32 else n


def kernel_k0(nregs, wgid):
    return (1 if wgid else 0) << 18 | (2 * ((nregs + 7) // 8)) << 12 | 0x100 | 1 << 2 | 0x2


def kernel8(n, wgid):
    return max_instances_a8(n, False, 16 if wgid else 0) << 27 | (hw_threads(n) - 1) << 18


def stream(nbuf, nregs, wgid, groups, n):
    _, _, units, common = binding(nbuf)
    rec = lambda k0, k1, k2, x=0, k8=0x40000000: [k0, k1, k2, x, 0, 0, k8]
    words = (rec(common << 18 | units << 2, OFF['bind_data'] | 0x2, OFF['bind_code']) +
             rec(kernel_k0(nregs, wgid), OFF['kdata'], OFF['kcode'], groups - 1, kernel8(n, wgid)) +
             rec(0x4, OFF['eop_data'] | 0xA, OFF['eop_code']) + rec(0x7, OFF['fence_data'] | 0x4, OFF['fence_code']) +
             [0x80000000])
    return words

# ---------------------------------------------------------------- tests


def a_val(k):
    return (0x10008000 + k) & 0xFFFFFFFF


def b_val(k):
    return (0x01008000 + 0x100 * k) & 0xFFFFFFFF


def empty_kernel():
    return [0x0100, 0x0140, 0x0000] + [0xC000] * 29 + [0x8000]


TESTS = []  # (name, risk, kernel fn, arg, nbuf, wgid, groups, N, inputs, expected fn, note)


def T(name, risk, fn, arg, nbuf, wgid, groups, n, inputs, expect, note):
    TESTS.append(dict(name=name, risk=risk, fn=fn, arg=arg, nbuf=nbuf, wgid=wgid, groups=groups, n=n,
                      inputs=inputs, expect=expect, note=note))


T("store1", 0, k_store1, 0xCAFE0001, 1, False, 1, 1, (), lambda i: 0xCAFE0001 if i == 0 else None,
  "run 99 regression in the new layout")
T("lid1", 1, k_lid, None, 1, False, 1, 1, (), lambda i: 0 if i == 0 else None, "shift + carry address build, one lane")
for n in (4, 16, 32, 64, 128):
    T(f"lid{n}", 2 if n <= 32 else 3, k_lid, None, 1, False, 1, n, (), (lambda n: lambda i: i if i < n else None)(n),
      f"one workgroup of {n}")
T("ldcopy4", 2, k_ldcopy, None, 2, False, 1, 4, ('a',), lambda i: a_val(i) if i < 4 else None, "the A8 load + wait")
T("ldk6_4", 2, k_ldk, 0x2A, 2, False, 1, 4, ('a',), lambda i: (a_val(i) + 0x2A) & 0xFFFFFFFF if i < 4 else None,
  "add immediate")
T("ldk32_4", 2, k_ldk, 0x01008000, 2, False, 1, 4, ('a',), lambda i: (a_val(i) + 0x01008000) & 0xFFFFFFFF if i < 4 else None,
  "move immediate + register add, carry across bit 16")
for g in (1, 2, 4, 16):
    T(f"gid{g}x32", 3, k_gid, 32, 1, True, g, 32, (), (lambda g: lambda i: i if i < 32 * g else None)(g),
      f"{g} workgroup(s) of 32: workgroup-ID launch (Orchard's compute64k shape)")
for g in (2, 4, 16, 64):
    T(f"gid{g}x4", 3.5, k_gid, 4, 1, True, g, 4, (), (lambda g: lambda i: i if i < 4 * g else None)(g),
      f"{g} workgroups of 4: several workgroups per task (max_instances 0 = 32 lanes)")
T("vadd1x32", 3, k_vadd, (32, False), 3, False, 1, 32, ('a', 'b'),
  lambda i: (a_val(i) + b_val(i)) & 0xFFFFFFFF if i < 32 else None, "two loads, register add, three buffers")
for g, n in ((4, 32), (8, 32), (4, 64)):
    T(f"vadd{g}x{n}", 4, k_vadd, (n, True), 3, True, g, n, ('a', 'b'),
      (lambda m: lambda i: (a_val(i) + b_val(i)) & 0xFFFFFFFF if i < m else None)(g * n), f"vector add, {g * n} elements")
T("loop5x4", 4, k_loop, (5, False), 1, False, 1, 4, (), lambda i: 5 if i < 4 else None, "uniform bounded loop")
T("loopdiv32", 5, k_loop, (0, True), 1, False, 1, 32, (), lambda i: (i & 3) + 1 if i < 32 else None,
  "divergent loop: lanes leave at iterations 1-4")
T("condodd32", 4, k_condodd, None, 1, False, 1, 32, (), lambda i: i if i < 32 and i & 1 else None, "if (i & 1) store")
T("wgidraw4x32", 3, k_wgidraw, None, 1, True, 4, 32, (), lambda i: 'any of 0..3' if i < 32 else None,
  "diagnostic: all zeros means the workgroup ID never arrives")
T("lid48", 3, k_lid, None, 1, False, 1, 48, (), lambda i: i if i < 48 else None, "48 lanes: the prologue masks lanes 48-63")
T("lid256", 6, k_lid, None, 1, False, 1, 256, (), lambda i: i if i < 256 else None, "limit: 256 lanes")
T("lid512", 6, k_lid, None, 1, False, 1, 512, (), lambda i: i if i < 512 else None, "limit: 512 lanes (Apple's A8 maximum)")
T("reg7a8", 6, k_reg, (7, 8), 1, False, 1, 4, (), lambda i: 0x5A5A0007 if i < 4 else None, "limit: r7 with 8 registers (field 2)")
T("reg11a16", 6, k_reg, (11, 16), 1, False, 1, 4, (), lambda i: 0x5A5A000B if i < 4 else None,
  "limit: r11 with 16 registers (field 4, temps 0x20)")
T("reg11a8", 7, k_reg, (11, 8), 1, False, 1, 4, (), lambda i: 0x5A5A000B if i < 4 else None,
  "limit, expected to fail: r11 beyond an 8-register allocation (wrong value, no fault)")
T("carry1", 5, k_carry, None, 1, False, 1, 1, (), lambda i: 0xC0FFEE01 if i == 0 else None,
  "argument entry 0 = 0xffffffffffffff00: the store lands on the page only if the carry is right")


def build(t):
    fn = t['fn']
    arg = t['arg']
    items, nregs = fn(*arg) if isinstance(arg, tuple) else fn(arg)
    listing = assemble(items)
    code = code_bytes(listing)
    assert OFF['kernel'] + len(code) <= OFF['in_a'], "kernel too long for its slot"
    img = bytearray(OFF['size'])
    img[OFF['empty']:OFF['empty'] + 66] = struct.pack("<33H", *empty_kernel())
    struct.pack_into("<IIII", img, OFF['eop_data'], OFF['empty'], 0x10, 0, 0)
    struct.pack_into("<IIII", img, OFF['eop_code'], bra_not_if1(2), HALT, pds_dout_a8(DOUTU, 0, DATA, 0, end=True, cc=True), HALT)
    struct.pack_into("<IIII", img, OFF['fence_code'], bra_not_if1(2), HALT, pds_dout_a8(DOUTC, 0, DATA, 0), HALT)
    bdata, bcode, _, _ = binding(t['nbuf'])
    assert len(bdata) <= 16 and len(bcode) <= 8
    struct.pack_into(f"<{len(bdata)}I", img, OFF['bind_data'], *bdata)
    struct.pack_into(f"<{len(bcode)}I", img, OFF['bind_code'], *bcode)
    kdata, kcode = kernel_pds(t['wgid'], nregs)
    struct.pack_into("<4I", img, OFF['kdata'], *kdata)
    struct.pack_into(f"<{len(kcode)}I", img, OFF['kcode'], *kcode)
    m = t['groups'] * t['n']
    vas = {'a': HEAP_VA + OFF['in_a'], 'b': HEAP_VA + OFF['in_b']}
    bufs = [vas[x] for x in t['inputs']] + [OUT_VA]
    if t['name'].startswith('carry'):
        bufs = [0xFFFFFFFFFFFFFF00]
    assert len(bufs) == t['nbuf']
    struct.pack_into(f"<{len(bufs)}Q", img, OFF['args'], *bufs)
    struct.pack_into("<IIII", img, OFF['count'], t['n'] | t['n'] << 16, 0, 0, 0)
    for x in t['inputs']:
        assert 4 * m <= 0x400, "inputs larger than their slot: place them in their own pages"
        f = a_val if x == 'a' else b_val
        struct.pack_into(f"<{m}I", img, OFF['in_a' if x == 'a' else 'in_b'], *[f(k) for k in range(m)])
    img[OFF['kernel']:OFF['kernel'] + len(code)] = code
    s = stream(t['nbuf'], nregs, t['wgid'], t['groups'], t['n'])
    return dict(listing=listing, nregs=nregs, img=bytes(img), stream=s, bdata=bdata, bcode=bcode, kdata=kdata, kcode=kcode,
                words=m, bufs=bufs)


def expected(t, count):
    return [t['expect'](i) for i in range(count)]


def payload(t, out):
    b = build(t)
    sb = struct.pack(f"<{len(b['stream'])}I", *b['stream'])
    assert len(sb) <= 0x80
    readback = max(8, min(1024, (b['words'] + 7) // 8 * 8 + 8))
    exp = [SENTINEL if v is None else 0xFFFFFFFF if isinstance(v, str) else v for v in expected(t, readback)]
    lines = [f"stream_hex {sb.hex()}", "pds_hex 000000d3", f"usc_hex {b['img'].hex()}", f"usc_va {HEAP_VA:#x}",
             f"out_va {OUT_VA:#x}", f"out_init {SENTINEL:#x}", "pds_code_va 0x201000", "pds_data_va 0x201000",
             "w244 0x00900004", "cmask 0xff"]
    with open(out, "x") as f:
        f.write("\n".join(lines) + "\n")
    # sidecar for the checker (the payload keeps j81_j2c_payload.py's keys): fill the whole output page with the
    # sentinel before the job, read back `read_words` words, compare with `expect_hex`
    with open(out + ".expect", "x") as f:
        f.write(f"fill_words 1024\nfill_value {SENTINEL:#x}\nread_words {readback}\n"
                "expect_hex " + struct.pack(f"<{readback}I", *exp).hex() + "\n")


def dump(t):
    b = build(t)
    print(f"# {t['name']}: {t['note']}; {t['groups']} workgroup(s) of {t['n']}; registers {b['nregs']}")
    for off, ws, note in b['listing']:
        if note == 'padding':
            print(f"+{off:#05x}  c000 x{len(ws)}  padding")
        else:
            print(f"+{off:#05x}  {' '.join(f'{w:04x}' for w in ws):<40} {note}")
    print("stream:", ' '.join(f"{w:08x}" for w in b['stream']))
    print("binding data:", ' '.join(f"{w:08x}" for w in b['bdata']), "| code:", ' '.join(f"{w:08x}" for w in b['bcode']))
    print("kernel data:", ' '.join(f"{w:08x}" for w in b['kdata']), "| code:", ' '.join(f"{w:08x}" for w in b['kcode']))


def grid():
    """Encoder grid for comparison against Orchard's C encoders (g9p_isa.h with g5p_usc_g4p = true)."""
    rows = []
    for st in (3, 4, 6, 7):
        rows += [("push_init", st, push_init(st)), ("pop", st, pop_final(st)), ("pop_levels1", st, pop_levels(st, 1)),
                 ("pop_levels2", st, pop_levels(st, 2)), ("push_if", st, push_if(st)), ("else", st, else_(st)),
                 ("loop_begin", st, loop_begin(st)), ("loop_break0", st, loop_break(st, False))]
    for imm in (0, 1, 3, 5, 0x2A, 0x203100, 0xCAFE0001, 0xFFFFFFFF, 0xC0FFEE01, 0x01008000):
        rows.append(("mov_imm2", imm, mov_imm(2, imm)))
    for dst, a, n in ((1, 0, 2), (2, 1, 2), (1, 1, 5), (1, 1, 2), (1, 1, 6)):
        rows.append(("shl", (dst, a, n), shift_imm(dst, a, n)))
    for dst, u, idx in ((2, 0, 1), (2, 2, 1), (4, 0, 2), (4, 2, 2), (4, 4, 2)):
        rows.append(("addr", (dst, u, idx), [w for i in addr(dst, u, idx) for w in i]))
    for store, reg, pair in ((True, 0, 2), (True, 2, 0), (True, 3, 4), (False, 4, 2), (False, 3, 4), (False, 6, 4), (True, 4, 2), (True, 1, 4), (True, 5, 2)):
        rows.append(("mem", (store, reg, pair), mem(store, U32, reg, pair)))
    rows += [("tg_load", 1, tg_load(1)), ("add_imm", (4, 4, 0x2A), add_imm(4, 4, 0x2A)), ("add_imm", (5, 5, 1), add_imm(5, 5, 1)),
             ("add_imm", (4, 4, 1), add_imm(4, 4, 1)), ("alu2", "iadd 1 1 0", alu2(IADD, 1, 1, 0)),
             ("alu2", "iadd 4 4 5 k", alu2(IADD, 4, 4, 5, True)), ("alu2", "iadd 3 3 6 k", alu2(IADD, 3, 3, 6, True)),
             ("alu2", "iadd 4 4 6", alu2(IADD, 4, 4, 6)), ("alu2", "and 4 0 4", alu2(AND, 4, 0, 4)),
             ("cmp_imm", "ugt 4 0", cmp_imm(UGT, 4, 0)), ("cmp_imm", "eq 4 1", cmp_imm(EQ, 4, 1)),
             ("prologue", "1 0", prologue(1, False)), ("prologue", "1 1", prologue(1, True)), ("prologue", "2 0", prologue(2, False)),
             ("prologue", "3 0", prologue(3, False)), ("prologue", "3 1", prologue(3, True))]
    for name, arg, ws in rows:
        print(name, arg if not isinstance(arg, tuple) else ','.join(map(str, arg)), ' '.join(f"{w:04x}" for w in ws))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'list'
    if cmd == 'list':
        for t in sorted(TESTS, key=lambda t: t['risk']):
            print(f"{t['name']:<12} risk {t['risk']:<4} {t['groups']}x{t['n']:<5} {t['note']}")
    elif cmd == 'dump':
        dump(next(t for t in TESTS if t['name'] == sys.argv[2]))
    elif cmd == 'payload':
        payload(next(t for t in TESTS if t['name'] == sys.argv[2]), sys.argv[3])
    elif cmd == 'grid':
        grid()


if __name__ == '__main__':
    main()
