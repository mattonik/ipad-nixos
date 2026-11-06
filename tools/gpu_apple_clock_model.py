#!/usr/bin/env python3
"""Execution-disabled model of Apple's J81 GFX clock-state ordering."""

from dataclasses import dataclass
import json
import sys


@dataclass(frozen=True)
class GfxClockRecord:
    device_id: int = 0x7C
    power_state_index: int = 100
    special_flags: int = 0x06
    selectors: tuple[int, int] = (9, 10)


RECORD = GfxClockRecord()


def model(enable: bool, *, clock_ref: int = 1) -> dict:
    """Return the ordered abstract actions; never emits MMIO writes."""
    if clock_ref < 0:
        raise ValueError("clock_ref must be non-negative")
    if clock_ref == 0:
        return {"enable": enable, "record": RECORD.__dict__, "actions": [],
                "blocked": "no-clock-reference"}
    if enable:
        actions = [
            {"kind": "pmgr-state", "state": 0xF},
            {"kind": "flush-power-state", "index": RECORD.power_state_index},
            {"kind": "special-action", "selector": RECORD.selectors[0]},
            {"kind": "special-action", "selector": RECORD.selectors[1]},
            {"kind": "gpc-setup-and-poll", "required_state": 1},
        ]
    else:
        actions = [
            {"kind": "special-action", "selector": RECORD.selectors[1]},
            {"kind": "special-action", "selector": RECORD.selectors[0]},
            {"kind": "flush-power-state", "index": RECORD.power_state_index},
            {"kind": "pmgr-state", "state": 0},
        ]
    return {"enable": enable, "record": RECORD.__dict__, "actions": actions}


def main() -> int:
    enable = "--disable" not in sys.argv[1:]
    print(json.dumps(model(enable), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
