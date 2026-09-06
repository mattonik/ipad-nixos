#!/usr/bin/env python3
"""Upload an m1n1 payload to PongoOS and request its dedicated bootm path."""

import argparse
import struct
import time

import usb.core


parser = argparse.ArgumentParser(description="Upload m1n1 to PongoOS")
parser.add_argument("payload", help="m1n1.bin or a combined m1n1 payload")
args = parser.parse_args()

with open(args.payload, "rb") as payload_file:
    payload = payload_file.read()
if not payload or len(payload) > 128 * 1024 * 1024:
    parser.error("payload must be between 1 byte and PongoOS's 128 MiB limit")

device = usb.core.find(idVendor=0x05AC, idProduct=0x4141)
while device is None:
    print("Waiting for PongoOS USB device 05ac:4141...")
    time.sleep(2)
    device = usb.core.find(idVendor=0x05AC, idProduct=0x4141)
device.set_configuration()

print(f"Uploading {len(payload)} bytes...")
try:
    # Discard any previously buffered upload first -- matches load_linux.py's
    # sequence. Harmless on a fresh boot (the buffer already starts empty),
    # but without it a second upload in the same PongoOS session (e.g. after
    # linux_diag) could start from a non-empty buffer state.
    device.ctrl_transfer(0x21, 2, 0, 0, 0, timeout=5000)
    device.ctrl_transfer(0x21, 1, 0, 0, struct.pack("<I", len(payload)), timeout=5000)
    written = device.write(2, payload, 1_000_000)
except usb.core.USBError as error:
    raise SystemExit(f"m1n1 upload failed: {error}") from error
if written != len(payload):
    raise SystemExit(f"m1n1 upload was short: {written} of {len(payload)} bytes")

print("Requesting PongoOS bootm handoff...")
try:
    device.ctrl_transfer(0x21, 4, 0, 0, b"", timeout=5000)
    device.ctrl_transfer(0x21, 3, 0, 0, b"bootm\n", timeout=5000)
except usb.core.USBError as error:
    print(f"PongoOS disconnected during bootm ({error}); inspect the iPad for m1n1 output.")
else:
    print("bootm was accepted; inspect the iPad for m1n1 output.")
