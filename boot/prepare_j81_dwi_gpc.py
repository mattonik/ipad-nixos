#!/usr/bin/env python3
"""Prepare the J81 DWI-hold GPC bundle from verified existing components."""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'boot'))
from kernel_notes_sha256 import notes

OLD_NOTES = '82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014'
OLD_MODULE_NOTE = '8e4e9917c1607b351aa9d9a087c571b9aff353baf6fec3f7e3cbae7fb12e4ac6'
NEW_NOTES = '5db452029d50cfaabd6cfb17f716509c895764543f87b7fee72709bca52aa9d0'
KERNEL = Path('/nix/store/w3w2652ya32c3471ayrayspyws03i7xa-linux-aarch64-unknown-linux-gnu-7.3.0-rc1-dev/vmlinux')
BASE = ROOT / 'artifacts/live/gpu-test-bundle-timed-revision-v3'
KP = ROOT / 'artifacts/live/private/j81-gpc-page5-kpoll-bundle-v1'
SAMPLE = ROOT / 'artifacts/live/private/j81-pmgr-words-bundle-v1/pmgr-words-peek'
FILES = {
    'gpu-pmgr-peek': (BASE / 'bin/gpu-pmgr-peek', '78349e4aa934a5ea1f22a2c9ea1859a39597476810764cdd92b3d8b35d3959dd'),
    'gpu-bridge-once': (BASE / 'bin/gpu-bridge-once', '3b2f655d18d94a4349bd19dbc63025fa9343e8ac43efbebc5b1f7fe97332a02c'),
    'gfx-bridge-plan.bin': (BASE / 'data/gfx-bridge-plan.bin', '1c7b3839da2e7aa914a393e914a7a427c12190293ba5d2b50fe06cf4d8df6435'),
    'gpu-watchdog-supervisor': (KP / 'gpu-watchdog-supervisor', '9740666bb9c4aab798ca762416e0044b737b1f134970fa4b567db80fa3f60280'),
    'pmgr-words-peek': (SAMPLE, 'b58d2ada974d3f0c280ee24f494ad17c7b2b252cf06fa00575b04a1c54618502'),
}
WRAPPERS = {
    'gpu-pmgr-cycle-run': (BASE / 'wrappers/gpu-pmgr-cycle-run.sh', 'e21f678dd41064d865b9946a0a6c9002166ea573ed48500e9748fe0e0e848d62'),
    'gpu-bridge-once-cycle-run': (BASE / 'wrappers/gpu-bridge-once-cycle-run.sh', '7d483501cd269e4fe0f24098bc5e4f08fd7206505091e367baaea6162e59f281'),
    'gpu-gpc-page5-kpoll-run': (KP / 'gpu-gpc-page5-kpoll-run', '9a482e2238b5981189ee46a37416ce3f4bcfd62d5060b7d0a1471d19a8bbca94'),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def module_note(data):
    if data[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', data, 18)[0] != 183:
        raise ValueError('not an AArch64 ELF module')
    shoff = struct.unpack_from('<Q', data, 40)[0]
    entsize, count, namesidx = struct.unpack_from('<HHH', data, 58)
    if entsize < 64 or not count or namesidx >= count or shoff + count * entsize > len(data):
        raise ValueError('invalid module section table')
    def section(i):
        off = shoff + i * entsize
        n, kind = struct.unpack_from('<II', data, off)
        start, size = struct.unpack_from('<QQ', data, off + 24)
        if start + size > len(data): raise ValueError('invalid module section')
        return n, kind, data[start:start + size]
    _, kind, names = section(namesidx)
    if kind != 3: raise ValueError('invalid section names')
    found = []
    for i in range(count):
        name, kind, value = section(i)
        if name >= len(names): raise ValueError('bad section name')
        end = names.find(b'\0', name)
        if end < 0: raise ValueError('bad section name')
        if names[name:end] == b'.note.gnu.build-id':
            if kind != 7 or not value: raise ValueError('invalid build ID')
            found.append(value)
    if len(found) != 1: raise ValueError('module build ID missing or ambiguous')
    return digest(found[0])


def prepare(cycle, kpoll, target):
    if digest(notes(KERNEL.read_bytes())) != NEW_NOTES: raise ValueError('kernel notes differ')
    cycle, kpoll, target = Path(cycle), Path(kpoll), Path(target)
    blobs = {name: path.read_bytes() for name, (path, _) in FILES.items()}
    wrappers = {name: path.read_bytes() for name, (path, _) in WRAPPERS.items()}
    for name, (_, expected) in {**FILES, **WRAPPERS}.items():
        if digest((blobs | wrappers)[name]) != expected: raise ValueError('source checksum mismatch: ' + name)
    blobs['gpu-pmgr-cycle.ko'] = cycle.read_bytes()
    blobs['j81-gpc-page5-kpoll.ko'] = kpoll.read_bytes()
    modnote = module_note(blobs['gpu-pmgr-cycle.ko'])
    module_note(blobs['j81-gpc-page5-kpoll.ko'])
    for name, value in wrappers.items():
        text = value.decode()
        if name != 'gpu-pmgr-cycle-run':
            if text.count(OLD_NOTES) != 1 or text.count(OLD_MODULE_NOTE) != 1: raise ValueError('wrapper identity mismatch')
            text = text.replace(OLD_NOTES, NEW_NOTES).replace(OLD_MODULE_NOTE, modnote)
        guard = "tr ' ' '\\n' </proc/cmdline | grep -qx j81_dwi_hold=1 || exit 1\n"
        marker = 'grep -q \'^rootfs / rootfs \' /proc/mounts || exit 1\n'
        if text.count(marker) != 1: raise ValueError('wrapper guard insertion failed')
        blobs[name] = text.replace(marker, guard + marker).encode()
    target.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, data in blobs.items():
        (target / name).write_bytes(data)
        (target / name).chmod(0o600 if name.endswith(('.bin', '.ko')) else 0o700)
    record = {'kernel_notes': NEW_NOTES, 'cycle_module_note': modnote,
              'files': {name: digest(data) for name, data in sorted(blobs.items())}}
    (target / 'manifest.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    return record

if __name__ == '__main__':
    if len(sys.argv) != 4: raise SystemExit('usage: prepare_j81_dwi_gpc.py cycle.ko kpoll.ko new-bundle-dir')
    print(json.dumps(prepare(*sys.argv[1:]), indent=2))
