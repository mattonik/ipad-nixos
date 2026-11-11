import copy
import unittest

from gpu_ldr_crosscheck import crosscheck
from test_gpu_ldr_inspect import fixture


def external():
    return {"records": [
        {"kind": "load", "destination": 0x1000, "size": 4},
        {"kind": "zero", "destination": 0x2000, "size": 8},
        {"kind": "config", "writes": [{"address": 0x1234, "value": 5}]},
        {"kind": "start_threads", "threads_inferred": [
            {"thread": 1, "sp": 0x2000, "pc": 0x1000, "catch": 0}]},
        {"kind": "comment"},
    ]}


class CrosscheckTests(unittest.TestCase):
    def test_agreement(self):
        self.assertEqual(crosscheck(fixture(), external()), 5)

    def test_mismatch_per_record_type(self):
        changes = [(0, "size", 5), (1, "destination", 1),
                   (2, "writes", []), (3, "threads_inferred", []), (4, "kind", "zero")]
        for index, field, value in changes:
            with self.subTest(index=index):
                metadata = copy.deepcopy(external())
                metadata["records"][index][field] = value
                with self.assertRaises(ValueError):
                    crosscheck(fixture(), metadata)

    def test_missing_records(self):
        metadata = external()
        metadata["records"].pop()
        with self.assertRaisesRegex(ValueError, "count mismatch"):
            crosscheck(fixture(), metadata)


if __name__ == "__main__":
    unittest.main()
