#!/usr/bin/env python3
"""Check the Image layout bound used by the guarded T7001 diagnostic."""
import struct
from pathlib import Path


root = Path(__file__).resolve().parent.parent
image = (root / "result-kernel" / "Image").read_bytes()
layout_size = struct.unpack_from("<Q", image, 16)[0]
capacity = 64 * 1024 * 1024

assert len(image) <= layout_size <= capacity
assert "*image_size < output_size || *image_size > LINUX_IMAGE_CAPACITY" in (
    root / "boot" / "pongo-t7001.patch"
).read_text()
print(f"Image={len(image)} layout={layout_size} capacity={capacity}")
