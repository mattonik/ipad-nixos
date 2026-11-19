import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import j81_observer_paired_campaign as campaign

good = b"\n".join(
    f"w 0x{int(offset, 16):06x} raw=0x{index:08x}".encode()
    for index, offset in enumerate(campaign.OFFSETS, 1)
) + b"\nstage=after-pmgr-words-read\n"
assert campaign.parse_words(good) == {f"{int(offset, 16):06x}": index for index, offset in enumerate(campaign.OFFSETS, 1)}
for bad in (good.replace(b"w 0x032000", b"w 0x032004"), good.replace(b"stage=after-pmgr-words-read", b"")):
    try:
        campaign.parse_words(bad)
        raise AssertionError("invalid snapshot accepted")
    except RuntimeError:
        pass
print("PASS: observer paired snapshot requires ordered complete read-only PMGR words")
