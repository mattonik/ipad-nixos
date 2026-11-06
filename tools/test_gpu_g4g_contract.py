#!/usr/bin/env python3
import sys
import struct
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gpu_g4g_contract import assess

synthetic = bytearray(256)
struct.pack_into("<I", synthetic, 8, 16)
struct.pack_into("<HHIII", synthetic, 16, 0, 20, 36, 0x1000, 128)
struct.pack_into("<HHII", synthetic, 36, 4, 16, 52, 0x2000)
struct.pack_into("<I", synthetic, 48, 8)
struct.pack_into("<HH", synthetic, 128, 0, 10)
synthetic[132:136] = b"test"
struct.pack_into("<HH", synthetic, 52, 0x10, 16)
struct.pack_into("<I", synthetic, 56, 0xffffffff)
result = assess(synthetic, {"complete": False})
assert result["execution_allowed"] is False
assert result["alive_state_model"] == "FIRMWARE_READY"
assert result["firmware_handshake_ready"] is False
assert result["mmio_operations"] == 0
assert result["firmware_bytes_copied"] is False
assert result["sequence"][-1] == "boot-descriptor-review"
assert "DART mappings and command-buffer ABI" in result["unresolved"]
print("PASS: G4G contract assessment remains execution-disabled")
