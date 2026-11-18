# J81 GPU — identify the power transition preceding the first core read

Builder handoff against `ab0cf1e3273e516d20ca1c4fa3095cf4e56c0330`, 2026-11-18. Target J81, T7001, stock reference iPadOS 15.8.5 (19H394). The first driver milestone is a repeatable RGX revision result on Linux matching iPadOS's `0x00070500`. The next piece to build is an address-filtered record of the working GFX power transition. First use the existing archives to see how much of it is already available.

For the expected raw request words and the exact J81 device-tree lookup, see the [register comparison](2026-11-18-j81-gfx-state-word-comparison.md).

## Why reopen this one transition?

The [November 18 capture](2026-11-10-j81-gpc-page5-cross-os-audit.md#follow-up-same-process-fender-status-capture) reports state 1 after five polls, Fender control `0x40000000`, and PMGR page-5 +4 zero. The new [campaign](../boot/j81_gpc_fender_campaign.py) stages a PMGR cycle and a Fender probe. It has no explicit 66-entry bridge stage. The [November 17 run](2026-11-17-j81-fender-page5-capture-result.md) reports a bridge stage and the same five final words. Together these runs give no reason to repeat a Linux Fender snapshot. In the C probe, the variable printed as the successful poll word has already been overwritten by a second state read. The actual successful poll passed the low-five-bit test. The capture does not time the interval between that poll and the sysfs page-5 read. [Probe source](../boot/gpu-gpc-fender-status.c)

The [November 17 ordinary-writer note](2026-11-17-j81-ios-g4g-ordinary-pmgr-store-capture.md) describes 32 printed rows in one boot and 17 in a second. Its inference of complete coverage needs correcting. In the sampled builds at `53e9766` and `71d026b`, the formatter emits O from the staging area's +4, whose maximum is 32. The tail sampler skips 32 events and can stage the next 32. The merge copies only min(staged, 128 − generic rows). For example, 111 generic rows leave room for 17 ordinary rows even when all 32 slots are occupied. That example is arithmetic, not a measurement of this boot's generic rows. Output loss could also occur downstream. On the reported O=0x20, **15 staged slots are unaccounted for by the 17 printed rows** if the binary matches the tail source. Events after the full sample are unconstrained. Earlier count-only builds have a different formatter. [Sample recorder at the tail commit](https://github.com/mattonik/ipad-nixos/blob/53e9766/research/probes/j81-thread/j81_thread_shell.S)

Two other limits matter for a driver decision. The ordinary reader of the window flag is global. The export assigns its ordinary rows P1T1 and a synthetic instance field of 0x80000000. It does not measure their thread or instance. Its counter updates are non-atomic, and it stages the arguments before executing the original store. Consequently the observed list cannot establish that the provider thread completed those operations, or that no GFX write occurred in either callback. The control-bank classification as MCC/CPU work still stands. [Merged recorder](../research/probes/j81-thread/j81_thread_shell.S)

## Exact-build offline checks

I selected the J81AP BuildIdentity from Apple's restore BuildManifest, extracted its kernelcache, verified the decompressed length and Adler-32, and matched the repository's full-image SHA-256 (`c3507666766775dc854d5bcf6c375e6651ac8b2d1adb13d06331c60deb6a0008`). The following are static observations from that file. [Apple restore image](https://updates.cdn-apple.com/2025FallFCS/fullrestores/082-67137/2FF7F5F3-3900-4F6D-BBDF-A68EEBE7B83F/iPad_64bit_TouchID_15.8.5_19H394_Restore.ipsw) · [Project image comparison](2026-11-11-j81-19h394-code-parity.md)

* The reviewed T7001 PMGR vtable resolves startup slot +0x5c8 to VA `0xfffffff006c8872c`. It performs read/modify/write on offsets 0x1008 then 0x4008 with the upper two bits replaced by binary 01. This predicts the order and top bits of the first two published provider-window rows. It supplies a concrete alternate source for those rows. Their caller and thread in that boot remain unknown.
* In the state setter at VA `0xfffffff006bc6ed8`, a branch through the ordinary write slot +0x988 leads into the existing +0x990 actual-state poll. The normal writer and poll pair also occurs at VA suffixes `bc7268` and `bc7294`. There are conditional paths. A prior working boot already observed the matching GFX region 0 / offset 0x20320 / instance 0 poll returning 0x3ff. This makes the **requested GFX word, previous word, caller and order relative to that poll** more informative than another post-poll status value. [Working poll result](2026-11-10-j81-ios-linux-poll-result.md)
* The [public J82 device tree](https://github.com/SoMainline/adt_collection/blob/768d800c46140c9ba39a372d097fa49f7197a66d/a8/J82.adt) contains a GPU `gfx-qos` property with two LE32 cells (1,1). A byte search of the exact decompressed J81 kernel returned zero literal ASCII occurrences of that property and one of `gpu-perf-integral-gain`. This leaves indirect names and other consumers open. The sibling property alone supplies no J81 operation to implement.
* [PR #42](https://github.com/mattonik/ipad-nixos/pull/42) merged a November 4 feasibility study. Its raw core-read proposal predates both the PongoOS stall and the successful stock identity measurement. The A10 RTKit path does not supply this missing A8X transition.

## Instructions for the in-place builder

1. Use the matching private probe binary hashes/build records and the retained November 17 10:24, 10:45 and 12:01 local archives. Identify prefix, clock-tail and combined-tail separately. Verify the producer/formatter in each binary against its source revision. For each sampled build, export the original messages once in chronological order to a separate plain text file. Keep complete header and payload on the same line. On a Mac with unified logs, use `log show --style syslog --info --debug --archive "$ARCHIVE" --predicate 'eventMessage CONTAINS "P1T1:" OR eventMessage CONTAINS " M"'` and retain the original archive privately. Confirm that batches without ordinary rows were kept.
2. Run the host-only commands below from this checkout or the in-place builder checkout containing the two scripts. Set MESSAGES to one per-boot export. The checker counts textual observations. It cannot identify duplicated delivery of a row with identical contents, prove thread identity, recover lost events, or identify a boot from its header. Check the archive identity and log export before combining results. It expects the sampled formatter only.

   ```sh
   python3 tools/test_audit_gpu_store_export.py
   python3 tools/audit_gpu_store_export.py "$MESSAGES"
   ```

3. If a region-0 0x20320 row survives, retain its full value and order. Recover the real instance and phase independently if available. Compare the pre-state, requested word and poll with the Linux power-domain trace. In particular the cycle module performs get → put → get and holds the last reference. Matching the last 0x3ff word alone leaves the intermediate off/on edges unresolved. If an existing trace already covers all of these, use that directly. [Linux cycle](../kernel/gpu-pmgr-cycle/gpu-pmgr-cycle.c)
4. If the old export cannot resolve this, run the [host GFX transition recorder](../tools/gpu_gfx_transition.py) on any independently attributed saved traces. It has a dedicated small buffer for region 0, offset 0x20320, instance 0. Inputs are existing driver observations of the state setter and poll. Include phase (before provider, clock, power), measured same/other/unknown thread, old word when already read, requested value, poll return, and event order. Track matched, stored, dropped and overflow independently. Reserve space for a positive poll marker and eventual identity result. Represent unavailable fields explicitly. Keep the first matching transition even if thousands of unrelated events precede it. The host version consumes synthetic events or saved traces with no device access. Emit one compact transition report. This is a change of question from sampling the first N global writes.
5. Accept the host build when one synthetic target after 128 unrelated rows is retained, a different instance is rejected, another thread is distinguishable, and a dropped target or missing positive control gives an inconclusive result. Where private working traces exist, expect the existing 0x3ff poll and 0x00070500 identity. The builder's deliverables are the per-boot coverage summaries, hash/revision mapping, tested recorder and a stock/Linux transition diff. A host test alone does not establish that a later instrumented build is suitable for a device.
6. Use the diff to decide the next Linux piece. An additional **identified** stock GFX transition with known owner, width and preconditions merits an isolated Linux PMGR test ending at the existing readiness observations. A matching GFX transition shifts the search earlier to the reset/clock/fabric dependency and rules out replaying these same stores as the next experiment. A missing or dropped control leaves both paths open. Schedule an RGX identity attempt only after a new prerequisite has evidence behind it. The existing stalled ID read, the auxiliary hold write and a guessed page-5 or voltage write do not answer this comparison.

The owner has the original capture binaries and archives. This checkout has the public source and published row counts only. The export discrepancy is reproducible at source level, while the identity of the missing rows and the reason the GPU stalls remain open.

### Host recorder and local comparison

Run the acceptance test, then supply one chronological JSON Lines stream per boot. The first argument is the stock reference. The optional second argument adds the Linux comparison.

```sh
python3 tools/test_gpu_gfx_transition.py
python3 tools/gpu_gfx_transition.py stock.jsonl linux.jsonl
```

A **synthetic example** for the input format follows. The write value is illustrative. Each input line holds one object, with numeric fields encoded as unsigned decimal JSON integers. A boot header identifies the role and carries a local archive alias. Verify the real board, image, capture interval and producer revision against the corresponding archive before normalization.

```jsonl
{"kind":"boot","role":"stock","boot":"example-stock"}
{"kind":"write","region":0,"offset":131872,"instance":0,"phase":"clock","thread":"same","caller":"example setter","old":768,"value":783}
{"kind":"poll","region":0,"offset":131872,"instance":0,"phase":"clock","thread":"same","value":1023}
{"kind":"identity","value":460032}
{"kind":"end","lost":0}
```

Write and poll events describe actual observed values in input order. `write` means the requested word observed at the setter and carries no readback guarantee. Only use `poll` for the GFX actual-state poll of mask 0xf0, expected 0xf0, with the raw returned word. Use `identity` for the observed first RGX revision result. In the Linux stream, end at the equivalent pre-identity boundary if the read did not return. Use the same window on both sides, from baseline through first identity or its checkpoint. A successful Linux identity observation remains visible in its own report.

Permitted phases are `before`, `clock`, `power`, and `unknown`. Use `unknown` for a Linux event without a corresponding provider phase. The thread label is `same`, `other`, or `unknown` relative to the tracked provider or Linux cycle thread. Set it only from independent attribution. Use JSON `null` for an unavailable instance, previous word or caller. Keep unverifiable raw legacy samples in the separate store-export analysis. A legacy synthetic instance tag cannot be normalized into instance zero. `end.lost` counts dropped or unobservable potential target events upstream. Supply zero only with independently verified producer coverage over the selected window. Omit the end record for unknown coverage.

The host report holds the first 32 matching PMGR events. It counts further matching events as dropped and retains the first qualifying same-thread poll following a same-thread write, and the identity result independently. The reference stock poll must equal 0x3ff. Linux qualifies on ACTUAL=15 and retains the complete raw return. The comparison reports ordered **requested write values only**. The event reports retain phases, previous words, caller, thread, poll values and source positions for manual comparison. Missing target writes, a missing positive control, an unverified source window, unknown target instances or dropped target observations make the comparison inconclusive. A matching sequence alone cannot establish equal timing, register effects or GPU readiness.
