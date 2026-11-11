import unittest
from verify_sites import GPC, MACH_TIME, locate


class SignatureTests(unittest.TestCase):
    def test_unique_aligned(self):
        self.assertEqual(locate(b'\x00' * 4 + GPC, GPC), 4)
        self.assertEqual(locate(MACH_TIME, MACH_TIME), 0)

    def test_missing_duplicate_and_unaligned(self):
        for data in (b'', GPC + GPC, b'\x00' + GPC):
            with self.subTest(length=len(data)), self.assertRaises(ValueError):
                locate(data, GPC)


if __name__ == '__main__':
    unittest.main()
