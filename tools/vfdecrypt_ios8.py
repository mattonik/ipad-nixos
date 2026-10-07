#!/usr/bin/env python3
"""Decrypt an iOS <= 9 root filesystem DMG (`encrcdsa` v2) on macOS without mounting it.

Usage: vfdecrypt_ios8.py ENCRYPTED.dmg OUT.dmg KEYFILE

KEYFILE holds the public firmware key as 72 hex characters (16-byte AES key + 20-byte HMAC-SHA1
key) after the text `RootFSKey` (the format of the public firmware-key pages). Each 512-byte block is
AES-128-CBC decrypted with IV = HMAC-SHA1(hmac key, big-endian block number)[:16]; the data starts
at the header's data offset and ends at its data size (the last partial block is truncated).
Uses macOS CommonCrypto through ctypes; the output is created exclusively. The result can be
attached read-only with `hdiutil attach -readonly -nobrowse`. Keep keys, the image and extracted
firmware outside the repository (firmware/ is ignored).
"""
import ctypes
import hashlib
import hmac
import re
import struct
import sys


def main(src, dst, keyfile):
    text = open(keyfile).read()
    key = re.search(r"=\s*([0-9a-fA-F]{72})", text.split("RootFSKey")[1]).group(1)
    aes, hmac_key = bytes.fromhex(key[:32]), bytes.fromhex(key[32:])
    f = open(src, "rb")
    hdr = f.read(0x100)
    assert hdr[:8] == b"encrcdsa", "not an encrcdsa image"
    blocksize = struct.unpack(">I", hdr[52:56])[0]
    datasize, dataoffset = struct.unpack(">QQ", hdr[56:72])
    cc = ctypes.CDLL("/usr/lib/libSystem.B.dylib")

    def decrypt(iv, data):
        out = ctypes.create_string_buffer(len(data))
        moved = ctypes.c_size_t()
        status = cc.CCCrypt(1, 0, 0, aes, 16, iv, data, len(data), out, len(data), ctypes.byref(moved))
        assert status == 0, status
        return out.raw

    f.seek(dataoffset)
    done = block = 0
    with open(dst, "xb") as o:
        while done < datasize:
            n = min(blocksize, datasize - done)
            chunk = f.read(blocksize)
            chunk += b"\0" * (-len(chunk) % 16)
            iv = hmac.new(hmac_key, struct.pack(">I", block), hashlib.sha1).digest()[:16]
            o.write(decrypt(iv, chunk)[:n])
            done += n
            block += 1
    print(f"decrypted {done} bytes in {block} blocks")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
