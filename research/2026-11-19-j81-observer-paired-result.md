# J81 observer-matched paired run, 2026-11-19

One run, one boot, observer kernel (notes sha256 a2dda271...), packet revision ed70e358..., private bundle `j81-observer-paired-20261119-v1` (raw logs stay in git-ignored `artifacts/live/private/j81-observer-results-20261119-run2`; copy also in the NAS builder mailbox `from-builder/2026-11-19-j81-observer-finished-ed70e35-result`).

Boot: palera1n `--pongo-shell --override-pongo <bundle>/Pongo.bin`, then `boot/load_m1n1.py <bundle>/m1n1-linux.bin` (bundle has no PRIVATE_MANIFEST.json, so `run_m1n1_debug.sh` cannot be used). One Lightning replug was needed after palera1n. `j81_preflight.sh gfx-request-observer` said GO.

Packet bug: the campaign preflight required output exactly `OBSERVER_GO`, but the console appends the prompt (`OBSERVER_GO/ #`). The first `--run` stopped before any staging or write. The second run used a scratch copy with one line changed (`output.removesuffix(b"/ #").strip()`), same boot. Offline tests passed with the patch.

Result (all stages rc=0, watchdog disarmed, same boot id):
- pre-GPC MiscACG (PMGR 0x32000) = 0x00000000, bit0 = 0 (iPadOS reference right after enable: 0x00000001).
- Snapshots A and B identical for all seven offsets; only C (after the GPC batch) differs: 0x1c200 0x80000000 -> 0x80110100, 0x2300c 0 -> 0x164.
- GPC poll raw 0x00000001 after 11 polls; page-5 first and later samples 0x00000000 (bit 30 clear).
- Observer rows: three gfx-request lines (0xf, 0xf0, 0xf).

Reading: with the existing get/put/get cycle and the bridge plan, MiscACG is still 0 before the GPC batch, unlike iPadOS. The batch itself did not set it either (snapshot C offset 0x32000 still 0). Not run again on this boot (one-shot).
