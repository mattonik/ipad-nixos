#!/usr/bin/env python3
"""Audit pinned public PMGR sources offline; never access device registers."""
import argparse
from fractions import Fraction
import hashlib
from pathlib import Path
import re

SOURCE_COMMIT = "6831bc701a6ce059e71e5aaa9488c9195bea6927"
DRIVER_BLOB = "82c33cf727a825d2536644d2fe09c0282acd1ef8"
DTS_BLOB = "7321cfdcd18965e40edbbdfc5edc91e4b1e8eb16"


def pinned(path, expected):
    data = path.read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    if blob != expected:
        raise ValueError(f"{path.name}: expected Git blob {expected}, got {blob}")
    return data.decode("utf-8")


def macro(source, name):
    value = re.search(r"^#define\s+" + re.escape(name) + r"\s+(.+)$", source, re.M)[1]
    if match := re.fullmatch(r"BIT\((\d+)\)", value):
        return 1 << int(match[1])
    if match := re.fullmatch(r"GENMASK\((\d+), (\d+)\)", value):
        high, low = map(int, match.groups())
        return ((1 << (high - low + 1)) - 1) << low
    raise ValueError(f"unsupported macro: {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--driver", type=Path, required=True, help="pinned pmgr-pwrstate.c")
    parser.add_argument("--dts", type=Path, required=True, help="pinned t7001-pmgr.dtsi")
    args = parser.parse_args()
    try:
        source = pinned(args.driver, DRIVER_BLOB)
        dts = pinned(args.dts, DTS_BLOB)
        nodes = {}
        for label, unit, body in re.findall(
                r"(ps_\w+): power-controller@([0-9a-f]+) \{(.*?)\n\t\};", dts, re.S):
            reg = re.search(r"reg = <(0x[0-9a-f]+) 4>;", body)
            if not reg or int(reg[1], 16) != int(unit, 16):
                raise ValueError(f"unit-address/reg mismatch: {label}")
            if label in nodes:
                raise ValueError(f"duplicate node: {label}")
            nodes[label] = (int(reg[1], 16), body)

        # The ADT ID is documented in the existing J81 SPI3 patch. This is
        # a counterexample to using it as a register-array index, not an
        # independent re-decode of the private ADT.
        spi_offset, spi_body = nodes["ps_spi3"]
        bad_offset = 0x20000 + 0x4d * 8
        if spi_offset != 0x20198 or "power-domains = <&ps_sio_p>" not in spi_body:
            raise ValueError("unexpected SPI3 resource")
        collision = [name for name, (offset, _) in nodes.items() if offset == bad_offset]
        if collision != ["ps_usb2host1"]:
            raise ValueError("unexpected counterexample mapping")
        masks = {name: macro(source, "APPLE_PMGR_" + name) for name in
                 ("RESET", "AUTO_ENABLE", "PS_MIN", "PS_ACTUAL", "PS_TARGET")}
        if masks != {"RESET": 1 << 31, "AUTO_ENABLE": 1 << 28,
                     "PS_MIN": 0xf0000, "PS_ACTUAL": 0xf0, "PS_TARGET": 0xf}:
            raise ValueError("unexpected PMGR power-state layout")
        if (masks["PS_MIN"] & ((1 << 19) | (1 << 18))) != ((1 << 19) | (1 << 18)):
            raise ValueError("dedicated touch bits no longer overlap PS_MIN")
        print(f"PASS: {len(nodes)} pinned DTS unit-address/reg pairs")
        print(f"SPI3 PS offset={spi_offset:#x}, array position={(spi_offset-0x20000)//8:#x}, parent=ps_sio_p")
        print(f"COUNTEREXAMPLE: ADT ID 0x4d used as index gives {bad_offset:#x} ({collision[0]})")
        print("PS layout: bit31 RESET, bit28 AUTO_ENABLE, bits19:16 MIN, bits7:4 ACTUAL, bits3:0 TARGET")
        # Conditional arithmetic only: no hardware frequency measurement.
        reference, requested = 24_000_000, 32_768
        divisor = reference // requested
        modeled = Fraction(reference, divisor)
        ppm = (modeled / requested - 1) * 1_000_000
        print(f"Conditional integer-divider model: divisor={divisor:#x}, output={float(modeled):.6f} Hz, error=+{float(ppm):.6f} ppm")
        print("KLCT register location, clock waveform and enable sequence remain unvalidated")
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
