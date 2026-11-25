#!/usr/bin/env python3
"""Run the guarded J81 GPU fork-point test through the PongoOS USB shell."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import re
import struct
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "artifacts/live/private/gpu-offline/gfx-bridge-plan.bin"
PLAN_SHA256 = "1c7b3839da2e7aa914a393e914a7a427c12190293ba5d2b50fe06cf4d8df6435"
GFX_PS = 0x20E020320
PAGE5 = 0x20E005004
PERF = 0x20E01C200
VOLTAGE = 0x20E02300C
GPC_CONTROL = 0x201E00000
GPC_STATE = 0x201E01000
CORE_REVISION = 0x201000020
CORE_ID = 0x201000018


class Stop(RuntimeError):
    pass


class NoResponse(RuntimeError):
    pass


def load_plan(path: Path, expected_hash: str = PLAN_SHA256) -> list[tuple[int, int]]:
    data = path.read_bytes()
    if sha256(data).hexdigest() != expected_hash:
        raise ValueError(f"bridge plan hash mismatch: {path}")
    if len(data) != 2 * 33 * 8:
        raise ValueError(f"bridge plan must be 528 bytes: {path}")
    words = struct.unpack("<132I", data)
    pairs = list(zip(words[::2], words[1::2]))
    for table in range(2):
        for index in range(33):
            expected = 0x18 if index == 0 else 0x40000 + 4 * (index - 1)
            if pairs[table * 33 + index][0] != expected:
                raise ValueError(f"invalid bridge offset at table {table}, index {index}")
    return pairs


class UsbTransport:
    def __init__(self) -> None:
        import usb.core

        self.usb = usb.core
        self.device = usb.core.find(idVendor=0x05AC, idProduct=0x4141)
        if self.device is None:
            raise RuntimeError("PongoOS USB device 05ac:4141 not found")
        self.device.set_configuration()

    def _control(self, request_type: int, request: int, value: int = 0,
                 data: bytes | int | None = None, timeout: int = 3000):
        try:
            return self.device.ctrl_transfer(request_type, request, value, 0,
                                             data, timeout=timeout)
        except self.usb.USBError as error:
            raise NoResponse(str(error)) from error

    def command(self, command: str) -> str:
        self._control(0x21, 4, 0xFFFF, b"")
        self._control(0x21, 4, 1, b"")
        self._control(0x21, 3, 0, (command + "\n").encode())
        output = bytearray()
        deadline = time.monotonic() + 3
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise NoResponse("USB command timeout")
            status = bytes(self._control(0xA1, 2, 0, 1, max(1, int(remaining * 1000))))
            chunk = bytes(self._control(0xA1, 1, 0, 0x1000,
                                        max(1, int(remaining * 1000))))
            output.extend(chunk)
            if status == b"\0":
                break
        return output.decode("utf-8", "replace")


class MockTransport:
    def __init__(self) -> None:
        self.commands: list[str] = []
        self.registers = {
            GFX_PS: 0x300, PAGE5: 0, PERF: 0x80110100, VOLTAGE: 0,
            GPC_STATE: 0, GPC_CONTROL: 0, CORE_REVISION: 0x00090F00,
            CORE_ID: 0x12345678,
        }
        self.gpc_polls = 0

    def command(self, command: str) -> str:
        self.commands.append(command)
        operation, address_text, *value_text = command.split()
        address = int(address_text, 16)
        if operation == "peek":
            if address == GPC_STATE and self.gpc_polls:
                self.registers[address] = 0x11 if self.gpc_polls == 1 else 1
                self.gpc_polls += 1
            value = self.registers.get(address, 0)
            return f"0x{address:x}: {value:x} ({value & 0xff:x} 0 0 0)\n"
        value = int(value_text[0], 16)
        self.registers[address] = value
        if address == GFX_PS and value == 0xF:
            self.registers[address] = 0xFF
        elif address == GFX_PS and value & (1 << 28):
            self.registers[address] = 0x3FF
        elif address == GPC_STATE and value == 0x11:
            self.gpc_polls = 1
        return f"writing {value:x} @ 0x{address:x}\n"


class Runner:
    def __init__(self, transport, plan: list[tuple[int, int]], transcript,
                 no_core_read: bool = False) -> None:
        self.transport = transport
        self.plan = plan
        self.transcript = transcript
        self.no_core_read = no_core_read

    def log(self, message: str) -> None:
        print(message, file=self.transcript, flush=True)

    def command(self, command: str) -> str:
        self.log(f"command> {command}")
        try:
            output = self.transport.command(command)
        except NoResponse:
            self.log("response> NO RESPONSE")
            raise
        self.log("response> " + output.rstrip().replace("\n", "\nresponse> "))
        return output

    def peek(self, address: int) -> int:
        output = self.command(f"peek {address:x}")
        match = re.search(rf"0x0*{address:x}:\s*([0-9a-f]+)\b", output, re.I)
        if not match:
            self.stop(f"invalid peek response for 0x{address:x}")
        return int(match.group(1), 16)

    def poke(self, address: int, value: int) -> None:
        output = self.command(f"poke {address:x} {value:x}")
        if not re.search(rf"writing\s+0*{value:x}\s+@\s+0x0*{address:x}\b", output, re.I):
            self.stop(f"poke echo mismatch for 0x{address:x}")

    def stop(self, reason: str) -> None:
        self.log(f"STOP: {reason}; no further writes")
        raise Stop(reason)

    def run(self) -> str:
        try:
            power = self.peek(GFX_PS)
            if power != 0x300:
                self.stop(f"GFX PS is 0x{power:08x}, expected 0x00000300")
            self.peek(PAGE5)
            self.peek(PERF)
            self.peek(VOLTAGE)

            requested = (power & ~((1 << 28) | (3 << 8) | 0xF)) | 0xF
            self.poke(GFX_PS, requested)
            for _ in range(64):
                power = self.peek(GFX_PS)
                if (power >> 4) & 0xF == 0xF:
                    break
            else:
                self.stop("GFX power-on poll limit reached")
            self.poke(GFX_PS, (power & ~(3 << 8)) | (1 << 28))
            power = self.peek(GFX_PS)
            if power != 0x3FF:
                self.stop(f"GFX PS is 0x{power:08x} after power-on, expected 0x000003ff")

            state = self.peek(GPC_STATE)
            if state != 0:
                self.stop(f"GPC state is 0x{state:08x}, expected zero")
            for table, base in enumerate((0x201F00000, 0x201F80000)):
                for offset, value in self.plan[table * 33:(table + 1) * 33]:
                    self.poke(base + offset, value)

            self.poke(0x201E10000, 0xFFFF0000)
            self.poke(GPC_CONTROL, 0x40000000)
            self.poke(GPC_STATE, 0x11)
            for _ in range(64):
                state = self.peek(GPC_STATE)
                if not state & 0x10 and state & 0x1F == 1:
                    break
            else:
                self.stop("GPC poll limit reached")

            for sample in range(1, 4):
                page5 = self.peek(PAGE5)
                self.log(f"PAGE5 AFTER GPC sample={sample} value=0x{page5:08x} bit30={(page5 >> 30) & 1}")
            self.peek(PERF)
            self.peek(VOLTAGE)
            control = self.peek(GPC_CONTROL)
            if control != 0x40000000:
                self.stop(f"GPC control is 0x{control:08x}, expected 0x40000000")
            if self.no_core_read:
                self.log("RESULT: steps 1-6 complete; core read disabled")
                return "no-core-read"

            self.log("BEFORE CORE READ: 0x201000020; a hang is final and will not be retried")
            try:
                revision = self.peek(CORE_REVISION)
            except NoResponse:
                self.log("RESULT: core-read=no-response")
                return "no-response"
            core_id = self.peek(CORE_ID)
            self.log(f"RESULT: core-read=answered revision=0x{revision:08x} id=0x{core_id:08x}")
            return "answered"
        except NoResponse as error:
            self.stop(f"USB no-response before the core read: {error}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path,
                        help="new private output directory (default: timestamped artifacts/live/gpu path)")
    parser.add_argument("--mock", action="store_true", help="simulate PongoOS and MMIO; never access USB")
    parser.add_argument("--no-core-read", action="store_true", help="run only steps 1-6")
    args = parser.parse_args()
    output = args.output or ROOT / "artifacts/live/gpu" / (
        "pongo-split-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    try:
        plan = load_plan(PLAN)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if output.exists():
        parser.error(f"output directory already exists: {output}")
    output.mkdir(parents=True, mode=0o700)
    transcript = output / "transcript.log"
    try:
        fd = os.open(transcript, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as log:
            runner = Runner(MockTransport() if args.mock else UsbTransport(), plan, log,
                            args.no_core_read)
            result = runner.run()
    except (OSError, RuntimeError) as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 1
    print(f"result={result} transcript={transcript}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
