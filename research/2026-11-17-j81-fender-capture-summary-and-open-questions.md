# J81 GPU: Fender capture summary and open questions (2026-11-17)

**November 20 correction.** A stock software path forwards a runtime firmware-event word to Fender +0, including bit 29. The paired-bit guard calls the state getter; the +0x20000 override is a separate virtual method. Linux subsequently reached page-5 high with Fender bit 29 clear. The working iPadOS observer tests page 5 and leaves the physical Fender bit unmeasured. The [19H394 writer and corrected dispatch trace](2026-11-20-j81-fender-bit29-producer.md) supersedes the earlier interpretations below.

**November 18 coverage correction.** The 32 prefix rows and 17 tail rows
are visible samples across separate boots. The tail formatter reports staged
slots before a capacity-limited merge. Ordinary rows carry synthetic thread
and instance labels. The published counts therefore leave the presence of
a GFX state-word store in the working transition unresolved.
[Exact-build review and builder handoff](2026-11-18-j81-gfx-transition-builder.md)

## Achieved today

- Rebuilt `gpu-pmgr-cycle.ko`; bit-identical to the original
  (sha256 `c27f7a9044c99104b13b3089e52ca3311de0fc257e47d307ec3b451c5cb20f23`).
- Verified probe, supervisor, runner and page-5 module hashes (see
  [capture result](2026-11-17-j81-fender-page5-capture-result.md)).
- One clean supervised capture (PMGR cycle, bridge, then known GPC setup and one
  read-only Fender/page-5 snapshot): Fender +0 `0x40000000` (our own write read
  back), +0x8 `0`, state `1`, +0x20000 `0`, page-5 +4 `0`.
- Bit 29 and page-5 bit 30 are hardware responses; no software in iOS 8.1 or
  15.8.5 writes them. In iOS, page-5 bit 30 appears only after the stock `0x11`
  GPC request and poll. Linux and bare PongoOS reach state 1 but never see them
  ([interpretation](2026-11-17-j81-fender-bit29-interpretation.md)).
- A scan of all refs (39 refs, 144 notes since 2026-11-09, 75 only off `main`,
  mostly on `j81-pmgr-store-sample` and `claude/project-thread-gb81y1`) shows these
  are already bounded: bridge stores (66, match iOS), ordinary PMGR stores
  (49 in the G4G window, none to GFX `+0x20320`), control-bank `+0x22000` bank
  (memory-controller setup), DWI, display and perf registers, entry-hook series,
  bare-PongoOS replay.

## Caveats

- The 2026-11-14 "recipe works at end of `ApplePMGR::start()`" result is
  qualified by the 2026-11-15 review (possible log-register reuse in the GPC
  readback; entry-probe stalls left no checkpoints; VM word `0x1` also seen on
  failing Linux).
- The iOS 8.1 SoC-busy/MCC callback path is not used by iOS 15 on J81 (the
  special-action handler does not bind), so modelling it is a weak lead.

## Open for other researchers

- What makes the GPC block respond to the `0x11` request with the ready bits: a
  GPU-specific dependency outside all captured paths (reset/isolation, fabric,
  direct MMIO bypassing PMGR's ordinary store path, or autonomous firmware).
- Untested: PMGR clock/divider/mux registers outside pages 0-5, and GPC
  registers beyond its three words (both need a specific safe register list
  first; do not sweep).
- Not worth more boots: Fender/GPC re-reads, writing bit 29 or page-5 bit 30,
  replaying the 66 bridge stores or the control-bank writes.
