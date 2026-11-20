"""Scripted test of the read-only PMGR words dump. No device connection is opened."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import j81_linux_pmgr_words as w

BOOT = "11111111-2222-3333-4444-555555555555"


class Sock:
    """Sends the ready line first and the words only after READ, like the real tool."""
    def __init__(self, offsets, drop=None):
        rows = [f"w 0x{o:06x} raw=0x{(0x80000000 if o == 0x22000 else o):08x}" for o in offsets if o != drop]
        self.data = (f"stage=before-pmgr-words-read base=0x20e000000 words={len(offsets)}\r\n").encode()
        self.rest = ("\r\n".join([*rows, "stage=after-pmgr-words-read"]) + "\r\n").encode()
        self.sent = []
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def settimeout(self, t): pass
    def sendall(self, b):
        self.sent.append(b)
        if b == b"READ\n":
            self.data += self.rest
    def recv(self, n):
        chunk, self.data = self.data[:n], self.data[n:]
        if not chunk: raise TimeoutError
        return chunk


def go(job, first, last, drop=None, shell_out=None):
    d = job / "bundle"; d.mkdir(exist_ok=True); (d / "pmgr-words-peek").write_bytes(b"p")
    offsets = list(range(first, last + 4, 4)); socks = []
    for i in range(0, len(offsets), 64):
        socks.append(Sock(offsets[i:i+64], drop))
    out = iter(shell_out or [BOOT.encode() + b"/ #", b"WORDS_GO/ #", b"STAGED_OK/ #", BOOT.encode() + b"/ #"])
    with patch.object(w, "PEEK_SHA", w.hashlib.sha256(b"p").hexdigest()), patch.object(w, "shell", side_effect=lambda c, t=10: next(out)), \
         patch.object(w, "stage"), patch.object(w.socket, "create_connection", side_effect=socks):
        w.run(job / f"log-{first:x}-{last:x}-{drop}", first, last, d)
    return job / f"log-{first:x}-{last:x}-{drop}"


with TemporaryDirectory() as t:
    job = Path(t)
    log = go(job, 0x22000, 0x223fc)  # 256 words = 4 chunks
    text = (log / "words.txt").read_text().splitlines()
    assert text[0] == "boot=" + BOOT and "0x022000 0x80000000" in text and len(text) == 257, len(text)
    assert len(list(log.glob("chunk-*.log"))) == 4
    for bad in (dict(first=0x22001, last=0x22010), dict(first=0x3fffc, last=0x40000), dict(first=0x22010, last=0x22000)):
        try: go(job, **bad)
        except ValueError: pass
        else: raise AssertionError(f"{bad} accepted")
    try: go(job, 0x22000, 0x22010, drop=0x22004)
    except RuntimeError: pass
    else: raise AssertionError("incomplete chunk accepted")
    try: go(job, 0x22000, 0x22010, shell_out=[BOOT.encode(), b"nope", b"x", b"x"])
    except RuntimeError: pass
    else: raise AssertionError("failed preflight accepted")
print("PASS: read-only PMGR words dump: 4 chunks, alignment/range refused, incomplete chunk and failed preflight stop")
