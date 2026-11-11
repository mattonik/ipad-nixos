# J81 19H394 firmware: independent LDR cross-check

The A9 project's META LDR decoder was run on the privately extracted
`AGXFirmwareKextG4G.__TEXT.__const` section from the J81 19H394 kernelcache.
The new `tools/gpu_ldr_crosscheck.py` compares that decoder's JSON against
our existing `gpu_ldr_inspect.host_report` in original order: kind, load and
zero destination/length, configuration write pairs, and thread-start fields.
It reports the first mismatched record without printing firmware contents.
The A9 decoder's interpretation of thread fields remains inferred.

On this local image the two parsers agree on **88 records**: 67 loads,
13 zeroes, 5 comments, 2 configuration records and 1 thread-start record.
Our parser reports 109,996 load bytes, 26,280 zero bytes, 27 configuration
writes and two thread entries. The two thread entries' second address fields
fall inside loaded ranges; their first address fields fall inside zero ranges
that our static models say the iOS 8.1 and 15 paths skip. These are parser
and static-model conclusions, not observations that a loader executed.

The separately extracted iOS 8.1 G4G image contains 80 records, including
58 loads, 14 zeroes, 27 configuration writes and two thread entries. The
counts alone do not imply ABI compatibility. The existing
`gpu_g4g_loader_compare.py` identifies decisions that a Linux G4G loader must
make; entries reported when the Linux core-memory size is unknown are
unresolved, not proven incompatibilities. Core access and firmware boot remain
unimplemented on J81.

Reproduce using a locally generated A9 `meta-ldr.json`:

```sh
python3 tools/gpu_ldr_crosscheck.py PRIVATE_G4G_LDR PRIVATE_META_LDR_JSON
python3 tools/test_gpu_ldr_crosscheck.py
python3 tools/test_gpu_ldr_inspect.py
```

The comparison checks metadata; it does not independently validate the META
LDR checksums, compare payload bytes, establish the firmware-return binding,
or guarantee correctness of either parser. A mismatch fails closed. The A9
extractor and all locally generated Apple-derived outputs remain outside the
public repository; see the [A9 tool review](2026-11-11-a9-gpu-research-review.md).
