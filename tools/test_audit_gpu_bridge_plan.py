#!/usr/bin/env python3
"""Exercise bridge-plan validation using synthetic tables only."""
import base64
import copy
import struct
import unittest
from audit_gpu_bridge_plan import audit


def fixture():
    enc = lambda b: base64.b64encode(b).decode()
    offsets = [0x18] + list(range(0x40000, 0x40080, 4))
    data = b"".join(struct.pack("<II", o, i) for i, o in enumerate(offsets))
    record = bytearray(44)
    record[3:7] = bytes([0x7c, 6, 9, 10])
    record[28:32] = b"GFX\0"
    pmgr = {"#bridges": 13, "bridge-reg-index": 2, "device-clocks": enc(record),
            "bridge-settings-9": enc(data), "bridge-settings-10": enc(data),
            "reg": [{"addr": 0, "size": 0}] * 11 + [
                {"addr": 0x1f00000, "size": 0x81000},
                {"addr": 0x1f80000, "size": 0x81000}]}
    sgx = {"clock-gates": [0x7c], "power-gates": [0x7c]}
    arm = {"ranges": enc(struct.pack("<QQQ", 0, 0x200000000, 0x100000000)),
           "children": [{"pmgr": pmgr}, {"sgx": sgx}]}
    tree = {"device-tree": {"children": [{"arm-io": arm}]}}
    row = lambda b: " ".join(f"{x:02x}" for x in b)
    device = bytearray(48)
    device[3] = 0x7c
    device[24:26] = b"\x02\x00"
    device[28:30] = b"\x09\x0a"
    device[32:36] = b"GFX\0"
    regs = b"".join(struct.pack("<QQ", r["addr"], r["size"]) for r in pmgr["reg"])
    captured = "\n".join(["        compatible                       pmgr1,t7001",
                           "        devices                          " + row(device),
                           "        reg                              " + row(regs)] +
                          [f"        bridge-settings-{n}                {row(data)}  |synthetic|" for n in (9,10)])
    return tree, captured


class Tests(unittest.TestCase):
    def test_matching_tables_and_addresses(self):
        tree, captured = fixture()
        result = audit(tree, captured)
        self.assertEqual([(x["selector"], x["base"], x["entries"]) for x in result],
                         [(9,"0x201f00000",33),(10,"0x201f80000",33)])
        self.assertEqual(result[0]["sha256"], result[1]["sha256"])

    def test_mismatch_and_unsafe_topology_rejected(self):
        tree, captured = fixture()
        with self.assertRaises(ValueError): audit(tree, captured.replace("00 00 04 00", "04 00 04 00", 1))
        with self.assertRaises(ValueError): audit(tree, captured + "\n" + captured)
        with self.assertRaises(ValueError): audit(tree, captured.replace("02 00 00 00 09 0a", "02 01 00 00 09 0a", 1))
        changed = copy.deepcopy(tree)
        changed["device-tree"]["children"][0]["arm-io"]["children"][1]["sgx"]["power-gates"] = [0]
        with self.assertRaises(ValueError): audit(changed, captured)
        changed = copy.deepcopy(tree)
        changed["device-tree"]["children"][0]["arm-io"]["children"][0]["pmgr"]["reg"][12]["size"] = 0x1000
        with self.assertRaises(ValueError): audit(changed, captured)
        changed = copy.deepcopy(tree)
        arm = changed["device-tree"]["children"][0]["arm-io"]
        arm["ranges"] = base64.b64encode(base64.b64decode(arm["ranges"]) * 2).decode()
        with self.assertRaises(ValueError): audit(changed, captured)


if __name__ == "__main__":
    unittest.main()
