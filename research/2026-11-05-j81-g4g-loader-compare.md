# J81 G4G Apple/Linux loader comparison (2026-11-05)

`tools/gpu_g4g_loader_compare.py` now compares metadata semantics only; it
does not allocate memory, copy firmware payloads, write registers, or execute
anything. Running it on the extracted 8.1 image produced the ignored capture
`artifacts/live/private/gpu-observations/g4g81-loader-compare.json`.

## Result on the real image

| Apple 8.1 vs generic Linux | Count |
|---|---:|
| Apple skips core-guard zero, Linux zeroes via segment | 3 |
| Both use a zero-via-segment path | 7 |
| Linux needs its core-data size before classifying | 4 |

The three divergent records are the same Apple 8.1 guarded core-memory starts
identified by the host-plan report. This is a concrete incompatibility, not
just an unknown firmware ABI. The four unresolved high-address records are a
separate Linux layout question and are reported without guessing a size.

The image also contains two thread records. Apple preserves them for its G4G
host setup; the generic Linux META path ignores `StartThreads` and constructs
boot arguments independently. The comparator therefore marks explicit thread
handling as required before an Apple image can be considered compatible.

The comparator confirms that the 27 config writes are representable as Linux
boot arguments, but that equivalence is insufficient: region mapping, guarded
zero behavior, thread start, and the firmware-alive handshake remain separate
requirements.

The follow-on `tools/gpu_g4g_loader_sim.py` is now a runnable compatibility
artifact. On the real image it emits 58 load reviews, 11 zero reviews, 3
Apple-skipped zeros, 27 config reviews, and one thread review while reporting
`execution_allowed=false`, `firmware_bytes_copied=false`, and
`mmio_operations=0`. It is the test harness for the eventual host-layout
adapter, not a firmware loader.

