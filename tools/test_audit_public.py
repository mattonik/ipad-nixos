#!/usr/bin/env python3
import unittest

import audit_public as a


class AuditTests(unittest.TestCase):
    def kinds(self, text, path="x.md"):
        return [h[0] for h in a.scan(text, path)]

    def test_flags_real_looking_mac_but_not_the_synthetic_one(self):
        self.assertEqual(self.kinds("addr 00:1a:2b:3c:4d:5e here"), ["mac"])
        self.assertEqual(self.kinds("macaddr=02:6a:38:70:00:01"), [])        # locally administered: synthetic or per-boot, not a burned-in address
        self.assertEqual(self.kinds("gadget ca:03:00:00:3f:72 and aa:bb:cc:dd:ee:ff"), [])

    def test_flags_wifi_keys_not_placeholders(self):
        self.assertEqual(self.kinds("network={\n  psk=\"hunter2hunter2\"\n}"), ["wifi-secret"])
        self.assertEqual(self.kinds("psk=<secret>"), [])

    def test_flags_private_keys_device_ids_and_home_dirs(self):
        self.assertIn("private-key", self.kinds("-----BEGIN OPENSSH PRIVATE KEY-----"))
        self.assertIn("device-id", self.kinds("ECID: 0x001A2B3C4D5E6F"))
        self.assertIn("home-dir", self.kinds("cd /Users/someone/work/repo"))
        self.assertEqual(self.kinds("cd /Users/someone/", path="tools/audit_public.py"), [])

    def test_flags_hex_dumps(self):
        self.assertIn("long-hex-dump", self.kinds(" ".join(["ab"] * 60)))
        self.assertEqual(self.kinds("0x4bc1 and 18 e1 18 e1"), [])


if __name__ == "__main__":
    unittest.main()
