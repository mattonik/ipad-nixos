#!/usr/bin/env python3
"""Summarize a single J81 ordinary-store sample export (19H394, sampled format)."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

HEADER = re.compile(r"\bB([01]) D[01]:[0-9a-f]{8}>[0-9a-f]{8} .*? M[0-9a-f]{8} O([0-9a-f]{8}) ")
ROW = re.compile(r"P[01]T[01]:([0-9a-f]{8})/([0-9a-f]{8}):([0-9a-f]{8})=([0-9a-f]{8});")


def summarize(lines):
    headers = set()
    ordinary = other = unready = 0
    gfx_values = Counter()
    for line in lines:
        header = HEADER.search(line)
        if not header:
            continue
        headers.add(header.groups())
        payload = line[header.end():].strip()
        rows = list(ROW.finditer(payload))
        if re.sub(r"\?;", "", ROW.sub("", payload)):
            raise ValueError("unexpected record text; use a plain per-boot message export")
        unready += payload.count("?;")
        for row in rows:
            region, tag, offset, value = row.groups()
            if tag == "80000000":
                ordinary += 1
                if region == "00000000" and offset == "00020320":
                    gfx_values[value] += 1
            else:
                other += 1
    if len(headers) != 1:
        raise ValueError("expected one consistent sampled-format header from one boot")
    overflow, raw = headers.pop()
    staged = int(raw, 16)
    if staged > 32 or ordinary > staged or ordinary + other + unready > 128:
        raise ValueError("impossible row count; check format, duplicates and boot identity")
    return dict(staged_sample_slots=staged, ordinary_rows_in_text=ordinary,
                staged_minus_printed=staged-ordinary, sample_full=staged == 32,
                other_rows=other, unready_rows=unready, generic_overflow=overflow == "1",
                region0_gfx_word_values=dict(gfx_values))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("messages", type=Path)
    args = parser.parse_args()
    try:
        with args.messages.open() as stream:
            print(json.dumps(summarize(stream), indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
