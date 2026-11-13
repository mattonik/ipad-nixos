#!/usr/bin/env python3
"""Verify the two RAM payloads differ only in their DWI hold argument."""
import hashlib
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'boot'))
from verify_pcie_j81_reg_on_payload import fdt_nodes

control, hold = map(Path, sys.argv[1:])
parts = ('m1n1.bin', 'bootargs', 't7001-j81.dtb', 'Image.gz', 'initramfs.gz')
for directory, arg in ((control, b'j81_dwi_hold=0'), (hold, b'j81_dwi_hold=1')):
    found = set()
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        name = Path(name).name
        assert name not in found
        found.add(name)
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest
    assert found == set(parts) | {'Pongo.bin', 'm1n1-linux.bin'}
    assert (directory / 'm1n1-linux.bin').read_bytes() == b''.join((directory / p).read_bytes() for p in parts)
    assert (directory / 'bootargs').read_bytes().split().count(arg) == 1
    nodes = fdt_nodes((directory / 't7001-j81.dtb').read_bytes())
    assert b'apple,j81\0' in nodes['/']['compatible']
    parent = nodes['/soc/power-management@20e000000']
    dwi = nodes['/soc/power-management@20e000000/power-controller@20120']
    assert parent['reg'] == struct.pack('>IIII', 2, 0x0e000000, 0, 0x24000)
    assert dwi['reg'] == struct.pack('>II', 0x20120, 4)
    assert dwi['label'] == b'dwi\0'
    assert b'apple,t7000-pmgr-pwrstate\0' in dwi['compatible']
    assert dwi.get('status', b'okay\0') in (b'okay\0', b'ok\0')
for name in ('Pongo.bin', 'm1n1.bin', 't7001-j81.dtb', 'Image.gz', 'initramfs.gz'):
    assert (control / name).read_bytes() == (hold / name).read_bytes(), name
assert (control / 'bootargs').read_bytes().replace(b'j81_dwi_hold=0', b'j81_dwi_hold=1') == (hold / 'bootargs').read_bytes()
print('PASS: paired payload composition, checksums, DWI mapping and only intended difference')
