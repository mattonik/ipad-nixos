#!/usr/bin/env python3
"""Check a J81 paired result and its preceding poll in a log-show NDJSON export."""
import argparse
import json
import re
from pathlib import Path
from uuid import UUID

WORD = r"([0-9a-fA-F]{8})"
PAIR = re.compile(r"\bJ81_FENDER_ID stage=" + WORD + " page5=" + WORD
                  + " fender=" + WORD + " gpu_id=" + WORD + "$")
POLL = re.compile(r"\bJ81_BOOT GPC TICKS=[0-9a-fA-F]{8}$")


def verify(rows, boot):
    polls, samples = [], []
    for row in rows:
        if not isinstance(row, dict) or str(row.get("bootUUID", "")).lower() != str(boot):
            continue
        message = row.get("eventMessage", "")
        if "J81_FENDER_ID" not in message and not POLL.search(message):
            continue
        tick = row.get("machTimestamp")
        if type(tick) is not int or tick < 0:
            raise ValueError("missing or invalid machTimestamp on a matching record")
        if POLL.search(message):
            polls.append(tick)
        else:
            match = PAIR.search(message)
            if not match:
                raise ValueError("malformed J81_FENDER_ID record")
            samples.append((tick, *(int(word, 16) for word in match.groups())))
    if len(samples) != 1:
        raise ValueError(f"expected one paired sample on {boot}, found {len(samples)}")
    tick, stage, page5, fender, gpu_id = samples[0]
    if not any(poll < tick for poll in polls):
        raise ValueError("missing earlier GPC poll record on this boot")
    if stage != 3 or not page5 & (1 << 30):
        raise ValueError(f"incomplete pair: stage={stage} page5={page5:#010x}")
    return (f"boot={boot} machTimestamp={tick} page5={page5:#010x} "
            f"fender={fender:#010x} bit29={(fender >> 29) & 1} gpu_id={gpu_id:#010x}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ndjson", type=Path)
    parser.add_argument("boot", type=UUID)
    args = parser.parse_args()
    try:
        with args.ndjson.open() as source:
            print(verify((json.loads(line) for line in source if line.strip()), args.boot))
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
