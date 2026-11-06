#!/usr/bin/env python3
"""Combine J81 G4G layout and alive-contract checks without executing firmware."""
import argparse, json, struct
from pathlib import Path

from gpu_g4g_alive_contract import transition
from gpu_g4g_view_plan import build_plan
from gpu_ldr_inspect import host_report

def assess(data, view_plan):
    report = host_report(data)
    state = transition("META_STARTED", "event-0", payload=0)
    state = transition(state["state"], "controller-ready", controller_ready=True,
                       payload=state["payload"])
    loader_ready = bool(report["records"])
    layout_ready = bool(view_plan.get("complete"))
    return {
        "execution_allowed": False,
        "sequence": [
            "ldr-review",
            "meta-start-model",
            "alive-event-0",
            "controller-ready-model",
            "interrupt-disable-review",
            "meta-handshake-review",
            "gpc-control-list-review",
            "boot-descriptor-review",
            "meta-bootloader-slot-review",
            "j81-resource-window-review",
            "firmware-object-resource-init-review",
            "firmware-kext-start-review",
            "private-map-wrapper-review",
            "provider-map-init-review",
            "provider-map-address-review",
            "firmware-service-registration-review",
            "final-property-hook-review",
        ],
        "mmio_operations": 0,
        "firmware_bytes_copied": False,
        "loader_records": len(report["records"]),
        "view_layout_complete": layout_ready,
        "alive_state_model": state["state"],
        "firmware_handshake_ready": loader_ready and layout_ready and state["state"] == "FIRMWARE_READY",
        "unresolved": [
            "J81 META-address to Linux GPU-address mapping",
            "A8X META boot-descriptor ownership and image-to-slot binding",
            "J81 META_BOOTLOADER slot 2 versus generic FW_DATA mapping",
            "J81 segment 3 global/alias ownership and address-view conversion",
            "J81 core MMIO window versus four 0x90007 resource windows",
            "descriptor-backed map address materialization and DART ownership",
        ],
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--offset", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--size", type=lambda value: int(value, 0))
    args = parser.parse_args()
    try:
        with args.image.open("rb") as stream:
            total = stream.seek(0, 2)
            size = total - args.offset if args.size is None else args.size
            if args.offset < 0 or size < 16 or args.offset + size > total:
                raise ValueError("invalid image span")
            stream.seek(args.offset); data = stream.read(size)
        if len(data) != size: raise ValueError("short image read")
        print(json.dumps(assess(data, build_plan()), sort_keys=True))
    except (OSError, ValueError, struct.error) as error:
        parser.exit(1, f"invalid image span: {error}\n")

if __name__ == "__main__": main()
