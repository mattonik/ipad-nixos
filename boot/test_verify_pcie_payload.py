#!/usr/bin/env python3
"""Unit-test the FDT walker and cpio reader used by verify_pcie_j81_reg_on_payload.py."""
import struct
import unittest

import verify_pcie_j81_reg_on_payload as v


def dtb(tree):
    """Build a minimal DTB from nested (name, {prop: bytes}, [children])."""
    strings, struct_blob = b"", b""

    def pad(b):
        return b + b"\0" * (-len(b) % 4)

    def walk(node):
        nonlocal strings, struct_blob
        name, props, children = node
        struct_blob += struct.pack(">I", 1) + pad(name.encode() + b"\0")
        for key, value in props.items():
            off = len(strings)
            strings += key.encode() + b"\0"
            struct_blob += struct.pack(">III", 3, len(value), off) + pad(value)
        for child in children:
            walk(child)
        struct_blob += struct.pack(">I", 2)

    walk(tree)
    struct_blob += struct.pack(">I", 9)
    off_struct = 40
    off_strings = off_struct + len(struct_blob)
    total = off_strings + len(strings)
    header = struct.pack(">10I", 0xD00DFEED, total, off_struct, off_strings, 0, 17, 16, 0,
                         len(strings), len(struct_blob))
    return header + struct_blob + strings


def newc(name, data, mode=0o100755):
    nm = name.encode() + b"\0"
    head = b"070701" + b"".join(b"%08X" % x for x in (0, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(nm), 0))
    body = head + nm
    body += b"\0" * (-len(body) % 4) + data
    return body + b"\0" * (-len(body) % 4)


class WalkerTests(unittest.TestCase):
    def test_fdt_nodes_and_properties(self):
        blob = dtb(("", {}, [("soc", {}, [("pcie@610000000", {"apple,reg-on-pmic": struct.pack(">I", 7),
                                                              "status": b"okay\0"}, []),
                                          ("pmic@3c", {"phandle": struct.pack(">I", 7),
                                                       "compatible": b"apple,i2c-pmic\0"}, [])])]))
        nodes = v.fdt_nodes(blob)
        self.assertEqual(struct.unpack(">I", nodes["/soc/pcie@610000000"]["apple,reg-on-pmic"])[0], 7)
        self.assertEqual(nodes["/soc/pmic@3c"]["compatible"], b"apple,i2c-pmic\0")

    def test_cpio_reader_last_entry_wins_and_names(self):
        data = newc("usr/bin/evtest", b"x") + newc("etc/deviceinfo", b"ecm.usb0") + \
            newc("TRAILER!!!", b"") + newc("usr/bin/btattach", b"y")
        entries = v.cpio_entries(data)
        self.assertEqual(set(entries), {"usr/bin/evtest", "etc/deviceinfo", "usr/bin/btattach"})
        self.assertIn("btattach", {n.rsplit("/", 1)[-1] for n in entries} & v.FORBIDDEN_BINARIES)

    def test_forbidden_set_covers_i2c_and_bluetooth_userland(self):
        for name in ("i2cset", "i2ctransfer", "i2cget", "btattach"):
            self.assertIn(name, v.FORBIDDEN_BINARIES)


if __name__ == "__main__":
    unittest.main()
