"""Host test of the iPadOS state-probe patcher: only the intended words change, a wrong base or word is refused."""
import hashlib
import struct

import make_j81_ios_state_probes as m

base = bytearray(0x5000)
for offset, old in {o: w for n in m.names() for o, w, _ in m.patches(n)}.items():
    struct.pack_into("<I", base, offset, old)
fake_sha = hashlib.sha256(bytes(base)).hexdigest()
m.BASE_SHA = fake_sha
base = bytes(base)
for name in m.names():
    out = m.build(base, name)
    changed = [i for i in range(0, len(base), 4) if base[i:i+4] != out[i:i+4]]
    assert changed == [o for o, old, new in m.patches(name) if old != new], name
    assert len(out) == len(base)
# encodings
assert m.add_x0_x24(0x20) == m.OLD_CORE_ADD and m.add_x0_x24(0x48) == 0x91012300 and m.add_x0_x24(0x194) == 0x91065300
assert m.OLD_PAGE5_A == 0x91400000 | (5 << 10) | (20 << 5) and m.NEW_MOVZ == 0xd2a00000 | (0x222 << 5) and m.OLD_MOVZ == 0xd2a00000 | (0x100 << 5)
assert m.ADD_X0_X20_1 == 0x91400000 | (1 << 10) | (20 << 5) and m.ADD_X0_X20_4 == 0x91400000 | (4 << 10) | (20 << 5)
for bad in (b"x" + base[1:], base[:0x413c] + b"\0\0\0\0" + base[0x4140:]):
    try:
        m.build(bad, "page14")
    except ValueError:
        pass
    else:
        raise AssertionError("bad base accepted")
print("PASS: state-probe patcher: exact word changes only, encodings checked, wrong base or word refused")
