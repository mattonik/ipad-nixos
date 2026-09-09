#!/usr/bin/env python3
"""Guard the HDQ framing and receive-order invariants in patch 0004."""

from pathlib import Path


patch = Path(__file__).with_name("patches").joinpath(
    "0004-add-bq27xxx-hdq-uart-frontend.patch"
).read_text()
transact = patch[patch.index("+static int hdq_transact") : patch.index("+static int hdq_read_byte")]

assert "+\t.write_wakeup = serdev_device_write_wakeup," in patch
assert transact.index("+\thdq_arm_receive") < transact.index("+\twritten = serdev_device_write")
assert "+\tint ret, rx_want = n_tx + (resp ? HDQ_UART_BYTE_LEN : 0);" in transact
assert "+\t\tmemcpy(resp, rx + n_tx, HDQ_UART_BYTE_LEN);" in transact
assert "+\t\tif (in[i] >= HDQ_UART_ONE_MIN)" in patch


def encode(value: int) -> list[int]:
    return [0xFE if value & (1 << bit) else 0xC0 for bit in range(8)]


def decode(samples: list[int]) -> int:
    return sum((sample >= 0xF0) << bit for bit, sample in enumerate(samples))


def collect(stream: list[int], start: list[int], want: int) -> list[int]:
    received: list[int] = []
    for sample in stream:
        if len(received) < 8 and sample != start[len(received)]:
            continue
        if len(received) < want:
            received.append(sample)
    return received


for value in range(256):
    assert decode(encode(value)) == value
    varied_response = [0xF8 if value & (1 << bit) else 0xC3 for bit in range(8)]
    assert decode(varied_response) == value

command = encode(0x2C)
response = encode(0xA5)
assert collect([0x00, 0xFF] + command + response, command, 16) == command + response

print("HDQ UART patch test passed")
