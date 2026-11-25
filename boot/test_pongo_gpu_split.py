#!/usr/bin/env python3
"""Host-only checks for the PongoOS GPU split runner."""
from hashlib import sha256
from io import StringIO
from pathlib import Path
import struct
import tempfile

import pongo_gpu_split as split


def plan_bytes(bad_offset=False):
    words = []
    for table in range(2):
        for index in range(33):
            offset = 0x18 if index == 0 else 0x40000 + 4 * (index - 1)
            if bad_offset and table == 1 and index == 9:
                offset += 4
            words.extend((offset, 0x80010004 + table * 0x100 + index))
    return struct.pack("<132I", *words)


with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "plan.bin"
    data = plan_bytes()
    path.write_bytes(data)
    plan = split.load_plan(path, sha256(data).hexdigest())
    assert len(plan) == 66
    try:
        split.load_plan(path, "0" * 64)
        raise AssertionError("bad plan hash accepted")
    except ValueError as error:
        assert "hash mismatch" in str(error)
    data = plan_bytes(True)
    path.write_bytes(data)
    try:
        split.load_plan(path, sha256(data).hexdigest())
        raise AssertionError("bad plan offset accepted")
    except ValueError as error:
        assert "invalid bridge offset" in str(error)


def run(transport=None, no_core_read=False):
    transport = transport or split.MockTransport()
    log = StringIO()
    try:
        result = split.Runner(transport, plan, log, no_core_read).run()
        return result, transport.commands, log.getvalue()
    except split.Stop as error:
        return error, transport.commands, log.getvalue()


result, commands, log = run()
assert result == "answered"
expected = [f"peek {split.GFX_PS:x}", f"peek {split.PAGE5:x}",
            f"peek {split.PERF:x}", f"peek {split.VOLTAGE:x}",
            f"poke {split.GFX_PS:x} f", f"peek {split.GFX_PS:x}",
            f"poke {split.GFX_PS:x} 100000ff", f"peek {split.GFX_PS:x}",
            f"peek {split.GPC_STATE:x}"]
for table, base in enumerate((0x201F00000, 0x201F80000)):
    expected += [f"poke {base + offset:x} {value:x}"
                 for offset, value in plan[table * 33:(table + 1) * 33]]
expected += ["poke 201e10000 ffff0000", "poke 201e00000 40000000",
             "poke 201e01000 11", "peek 201e01000", "peek 201e01000",
             "peek 20e005004", "peek 20e005004", "peek 20e005004",
             "peek 20e01c200", "peek 20e02300c", "peek 201e00000",
             "peek 201000020", "peek 201000018"]
assert commands == expected
assert "PAGE5 AFTER GPC sample=3" in log and "RESULT: core-read=answered" in log

result, commands, _ = run(no_core_read=True)
assert result == "no-core-read" and commands == expected[:-2]


class Fault(split.MockTransport):
    def __init__(self, target, replacement=None, no_response=False):
        super().__init__()
        self.target = target
        self.replacement = replacement
        self.no_response = no_response
        self.hits = 0

    def command(self, command):
        output = super().command(command)
        if command == self.target:
            self.hits += 1
            if self.no_response:
                raise split.NoResponse("mock hang")
            if self.replacement is not None:
                return self.replacement(self.hits, output)
        return output


bad = split.MockTransport()
bad.registers[split.GFX_PS] = 0x301
result, commands, log = run(bad)
assert isinstance(result, split.Stop) and len(commands) == 1 and "no further writes" in log

fault = Fault("peek 20e020320", lambda hit, output: output if hit < 3 else "0x20e020320: 3fe\n")
result, commands, _ = run(fault)
assert isinstance(result, split.Stop) and commands[-1] == "peek 20e020320"

fault = Fault("peek 20e020320", lambda hit, output: output if hit == 1 else "0x20e020320: f\n")
result, commands, _ = run(fault)
assert isinstance(result, split.Stop) and "poll limit" in str(result) and commands.count("peek 20e020320") == 65

bad = split.MockTransport()
bad.registers[split.GPC_STATE] = 2
result, commands, _ = run(bad)
assert isinstance(result, split.Stop) and commands[-1] == "peek 201e01000"

fault = Fault("poke 201f00018 80010004", lambda hit, output: "wrong echo\n")
result, commands, _ = run(fault)
assert isinstance(result, split.Stop) and commands[-1] == "poke 201f00018 80010004"

fault = Fault("peek 20e005004", lambda hit, output: "malformed\n")
result, commands, _ = run(fault)
assert isinstance(result, split.Stop) and len(commands) == 2

fault = Fault("peek 201e01000", lambda hit, output: output if hit == 1 else "0x201e01000: 11\n")
result, commands, _ = run(fault)
assert isinstance(result, split.Stop) and "GPC poll limit" in str(result)

fault = Fault("peek 201e00000", lambda hit, output: "0x201e00000: 0\n")
result, commands, _ = run(fault)
assert isinstance(result, split.Stop) and commands[-1] == "peek 201e00000"

fault = Fault("peek 201000020", no_response=True)
result, commands, log = run(fault)
assert result == "no-response" and commands[-1] == "peek 201000020"
assert "core-read=no-response" in log and "peek 201000018" not in commands

fault = Fault("peek 20e005004", no_response=True)
result, commands, log = run(fault)
assert isinstance(result, split.Stop) and len(commands) == 2
assert "USB no-response before the core read" in log

wrapper = Path(__file__).with_name("run_pongo_gpu_split.sh").read_text()
for digest in ("950c357b6ae5df36128f6e42a3c6d371e55aeb69a5afcde276f096276210d0c9",
               "1e5543fd8e6dbd84c334b87d71aa473f4d347c2ba8a5e863b6e10f18461c7575",
               split.PLAN_SHA256):
    assert digest in wrapper
assert "--pongo-shell --override-pongo" in wrapper
print("PASS: Pongo split plan, order, stop gates, echo check and no-response result")
