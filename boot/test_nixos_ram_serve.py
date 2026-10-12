#!/usr/bin/env python3
import http.client
import pathlib
import tempfile
import threading
import unittest
import http.server

import nixos_ram_serve as srv


class ServeTests(unittest.TestCase):
    def test_serves_only_the_two_files(self):
        with tempfile.TemporaryDirectory() as d:
            img = pathlib.Path(d) / "root.img"
            img.write_bytes(b"sq" * 5000)
            httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), srv.make_handler(img, "/nix/store/abc-nixos-system-x"))
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            try:
                c = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=5)
                c.request("GET", "/toplevel"); r = c.getresponse()
                self.assertEqual((r.status, r.read()), (200, b"/nix/store/abc-nixos-system-x\n"))
                c.request("GET", "/root.squashfs"); r = c.getresponse()
                self.assertEqual((r.status, len(r.read())), (200, 10000))
                for path in ("/", "/etc/passwd", "/../root.img", "/root.squashfs/x"):
                    c.request("GET", path); r = c.getresponse(); r.read()
                    self.assertEqual(r.status, 404, path)
            finally:
                httpd.shutdown()

    def test_toplevel_must_be_a_store_path(self):
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / "a.img").write_bytes(b"x")
            with self.assertRaises(SystemExit):
                srv.resolve(d, d)


if __name__ == "__main__":
    unittest.main()
