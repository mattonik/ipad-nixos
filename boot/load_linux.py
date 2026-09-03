#!/usr/bin/env python3
# load_linux.py — Upload Linux kernel/dtb/initrd to pongoOS via USB
#
# From: https://github.com/checkra1n/PongoOS/blob/master/scripts/load_linux.py
# License: MIT (checkra1n project)
#
# Usage: sudo python3 load_linux.py -k Image.lzma -d dtbpack -r initrd -c "cmdline"
#
# Requires: pyusb (pip install pyusb)
# The pongoOS USB device presents as 05ac:4141 (Apple DFU/recovery variant)

import usb.core
import struct
import sys
import argparse
import time

parser = argparse.ArgumentParser(description='A little Linux kernel/initrd uploader for pongoOS.')

parser.add_argument('-k', '--kernel', dest='kernel', help='path to kernel image')
parser.add_argument('-d', '--dtbpack', dest='dtbpack', help='path to dtbpack')
parser.add_argument('-r', '--initrd', dest='initrd', help='path to initial ramdisk')
parser.add_argument('-c', '--cmdline', dest='cmdline', help='custom kernel command line')
parser.add_argument('--diagnostic', action='store_true',
                    help='run the guarded T7001 payload diagnostic instead of bootl')

args = parser.parse_args()

if args.kernel is None:
    print(f"error: No kernel specified! Run `{sys.argv[0]} --help` for usage.")
    exit(1)

if args.dtbpack is None:
    print(f"error: No dtbpack specified! Run `{sys.argv[0]} --help` for usage.")
    exit(1)

dev = usb.core.find(idVendor=0x05ac, idProduct=0x4141)
if dev is None:
    print("Waiting for device...")

    while dev is None:
        dev = usb.core.find(idVendor=0x05ac, idProduct=0x4141)
        if dev is not None:
            dev.set_configuration()
            break
        time.sleep(2)
else:
    dev.set_configuration()

kernel = open(args.kernel, "rb").read()
fdt = open(args.dtbpack, "rb").read()

if args.cmdline is not None:
    dev.ctrl_transfer(0x21, 4, 0, 0, 0)
    dev.ctrl_transfer(0x21, 3, 0, 0, f"linux_cmdline {args.cmdline}\n")

if args.initrd is not None:
    print("Loading initial ramdisk...")
    initrd = open(args.initrd, "rb").read()
    initrd_size = len(initrd)
    dev.ctrl_transfer(0x21, 2, 0, 0, 0)
    dev.ctrl_transfer(0x21, 1, 0, 0, struct.pack('I', initrd_size))

    dev.write(2, initrd, 1000000)
    dev.ctrl_transfer(0x21, 4, 0, 0, 0)
    dev.ctrl_transfer(0x21, 3, 0, 0, "ramdisk\n")
    print("Initial ramdisk loaded successfully.")

print("Loading device tree...")
dev.ctrl_transfer(0x21, 2, 0, 0, 0)
dev.ctrl_transfer(0x21, 1, 0, 0, 0)
dev.write(2, fdt)

dev.ctrl_transfer(0x21, 4, 0, 0, 0)
dev.ctrl_transfer(0x21, 3, 0, 0, "fdt\n")
print("Device tree loaded successfully.")

print("Loading kernel...")
kernel_size = len(kernel)
dev.ctrl_transfer(0x21, 2, 0, 0, 0)
dev.ctrl_transfer(0x21, 1, 0, 0, struct.pack('I', kernel_size))

dev.write(2, kernel, 1000000)
print("Kernel loaded successfully.")

dev.ctrl_transfer(0x21, 4, 0, 0, 0)

if args.diagnostic:
    print("Running guarded T7001 diagnostic (no Linux jump)...")
    try:
        dev.ctrl_transfer(0x21, 4, 0xffff, 0, b"", timeout=5000)
        dev.ctrl_transfer(0x21, 3, 0, 0, b"linux_diag\n", timeout=5000)
        deadline = time.monotonic() + 10
        output = b""
        while time.monotonic() < deadline:
            time.sleep(0.25)
            output += bytes(dev.ctrl_transfer(0xa1, 1, 0, 0, 4096, timeout=5000))
            if b"diagnostic only, no jump attempted" in output:
                break
    except usb.core.USBError as error:
        print(f"T7001 diagnostic failed: {error}")
        exit(1)
    text = output.rstrip(b"\0").decode("utf-8", "replace")
    print(text)
    if b"diagnostic only, no jump attempted" not in output:
        print("Diagnostic did not prove that the no-jump guard ran.")
        exit(1)
    print("Payload ranges validated; PongoOS remains running.")
else:
    print("Booting...")
    try:
        dev.ctrl_transfer(0x21, 3, 0, 0, "bootl\n")
    except usb.core.USBError:
        # PongoOS intentionally tears down USB before the Linux jump.  This proves
        # only that handoff began; inspect the device before calling the boot good.
        print("PongoOS disconnected after bootl; handoff began, not a Linux boot confirmation.")
    else:
        print("PongoOS accepted bootl without disconnecting; Linux did not start.")
