#!/usr/bin/env python3
"""Extract J81 iOS-8.1 allocation requirements without runtime addresses."""
import argparse, json, re
from pathlib import Path

SIZE = re.compile(r"uVar6 = param_1\[(\d+)\] \* (0x[0-9a-f]+)")
SLOT = re.compile(r"param_1\[0x([0-9a-f]+)\] = \(long\)plVar4;")

def extract(source):
    result = []
    for match in SIZE.finditer(source):
        slot = SLOT.search(source, match.end())
        if slot is None: continue
        body = source[match.start():slot.end() + 1200]
        selector = "0x80007" if "0x80007" in body else None
        flags = ("0x22" if re.search(r"\|\s*0x22", body) else
                 ("0x21" if re.search(r"\|\s*0x21", body) else
                  ("0x23" if re.search(r"\|\s*0x23", body) else None)))
        if selector is None or flags is None: continue
        result.append({"size_parameter": int(match.group(1)), "size_multiplier": int(match.group(2), 16),
                       "allocator_flags": flags, "map_selector": selector,
                       "runtime_addresses": "unresolved"})
    return result

def main():
    p = argparse.ArgumentParser(); p.add_argument("source", type=Path); a = p.parse_args()
    try: print(json.dumps({"execution_allowed": False, "views": extract(a.source.read_text())}, sort_keys=True))
    except OSError as e: p.exit(1, str(e))
if __name__ == "__main__": main()
