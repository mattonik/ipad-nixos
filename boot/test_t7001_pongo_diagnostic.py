#!/usr/bin/env python3
"""Check the Image layout bound used by the guarded T7001 diagnostic."""
import struct
from pathlib import Path


root = Path(__file__).resolve().parent.parent
image = (root / "result-kernel" / "Image").read_bytes()
layout_size = struct.unpack_from("<Q", image, 16)[0]
text_offset = struct.unpack_from("<Q", image, 8)[0]
capacity = 64 * 1024 * 1024
alignment = 2 * 1024 * 1024

assert len(image) <= layout_size <= capacity
assert text_offset == 0
assert (-text_offset) % alignment == 0
patch = (root / "boot" / "pongo-t7001.patch").read_text()
assert "*image_size < output_size || *image_size > LINUX_IMAGE_CAPACITY" in patch
assert "#define LINUX_IMAGE_ALIGNMENT (2 * 1024 * 1024)" in patch
assert "x0=%p x1=x2=x3=0 EL%d" in patch
print(f"Image={len(image)} layout={layout_size} offset={text_offset} capacity={capacity}")
