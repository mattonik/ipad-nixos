"""Scripted test of the mapping-only campaign. No device connection is opened."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import j81_map_probe_campaign as c

OK = ["stage=before-map-walk",
      "map name=page5 pa=0x000000020e005000 va=0x0000ffffa0000000",
      "walk name=page5 result=ok va=0xffffa0000000 level=pte attr_idx=0 mair_byte=0x00 sh=2 pxn=1 uxn=1",
      "map name=gpc-state pa=0x0000000201e01000 va=0x0000ffffa0001000",
      "walk name=gpc-state result=ok va=0xffffa0001000 level=pte attr_idx=0 mair_byte=0x00 sh=2 pxn=1 uxn=1",
      "map name=core pa=0x0000000201000000 va=0x0000ffffa0002000",
      "walk name=core result=ok va=0xffffa0002000 level=pte attr_idx=0 mair_byte=0x00 sh=2 pxn=1 uxn=1",
      "stage=finished rc=0"]


class Sock:
    def __init__(self, lines):
        self.data = ("\r\n".join(lines) + "\r\n").encode(); self.sent = []
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def settimeout(self, t): pass
    def sendall(self, b): self.sent.append(b)
    def recv(self, n):
        chunk, self.data = self.data[:n], self.data[n:]
        if not chunk: raise TimeoutError
        return chunk


def go(job, lines, preflight=b"MAP_GO/ #", load=b"MODULE_OK/ #", boots=None):
    d = job / "art"; d.mkdir(exist_ok=True)
    (d / "j81-map-walk.ko").write_bytes(b"m"); (d / "j81-map-probe").write_bytes(b"p")
    seq = [preflight, b"STAGED_OK/ #", load]
    out = iter(seq)
    sock = Sock(lines)
    with patch.object(c, "MODULE_SHA", c.hashlib.sha256(b"m").hexdigest()), \
         patch.object(c, "PROBE_SHA", c.hashlib.sha256(b"p").hexdigest()), \
         patch.object(c, "boot_id", side_effect=boots or ["b"] * 4), \
         patch.object(c, "shell", side_effect=lambda cmd, timeout=10: next(out)), \
         patch.object(c, "stage"), patch.object(c.socket, "create_connection", return_value=sock):
        c.run(job / f"log-{len(list(job.iterdir()))}", d)
    return sock


with TemporaryDirectory() as t:
    job = Path(t)
    sock = go(job, OK)
    logs = [p for p in job.iterdir() if p.name.startswith("log-")][0]
    s = (logs / "summary.txt").read_text()
    assert "core: " in s and "pa=0x0000000201000000" in s and "mair_byte=0x00" in s, s
    assert sock.sent == [b"mkdir /tmp/j81-map-probe.once && /tmp/j81-map-probe\n"]
    for bad, kw in (("preflight", dict(preflight=b"x")), ("module", dict(load=b"fail")),
                    ("incomplete", None), ("rc", None)):
        try:
            if bad == "incomplete":
                go(job, [l for l in OK if "name=core" not in l])
            elif bad == "rc":
                go(job, OK[:-1] + ["stage=finished rc=1"])
            else:
                go(job, OK, **kw)
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"{bad} accepted")
print("PASS: mapping-only campaign: full run, preflight/module/incomplete/bad-exit all stop")
