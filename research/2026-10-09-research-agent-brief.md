# Brief for the research agent: why does the iPad hard-reset when brcmfmac posts its first ring buffers?

Read first: `research/2026-10-09-wifi-h1b-handoff.md` (full state, facts, ruled-out list, tooling) and the run log `research/2026-10-07-wifi-h1b-modelA-run.md` (runs 8-30).
Project: Linux on an iPad Air 2 (J81, A8X/T7001); BCM4350 Wi-Fi over PCIe port 1, private C2 `rieslinga` firmware. Repo: `<repo>` (branch `main`).

## The problem in one paragraph
With the NVRAM carrying a `macaddr` line, the firmware boots and its PCIe/msgbuf driver is fully open. The iPad then **hard-resets (no panic text, display off in ~30 ms)** as soon as brcmfmac posts its rx buffers in
`brcmf_proto_msgbuf_attach()` (271 `dma_map_single` calls through the DART, ring writes, one doorbell). A doorbell with empty rings and 41 s of idle firmware are harmless. The DART page-table index model (rebased/raw, even both at once)
and entry format (Apple's iOS S5L8960X format), ASPM, DS ACK, DEVICE_WAKE, ring ids, shared-memory layout were all tested and are not the cause. We need the cause.

## Your job: static / offline analysis only (no hardware, no builds, no commits of private data)
Produce a note `research/2026-10-09-<topic>.md` per question that finds something (evidence = function addresses/offsets and short values; **no raw firmware bytes, decompiler dumps or device identifiers**), and a final ranked list of testable host-side
changes. Each proposal must say how it would be tested with the existing toggle mechanism (`brcmfmac.*`, `apple_dart.*`, `pcie_apple_t7000.*` module parameters, off by default).

1. **DART start-up, iOS vs Linux.** Decode the ADT `dart-apcie1` node (`artifacts/adt/20260908T082112Z-j81.adt`, private): `error-reflector` = 0x2_0fff_f000 (twice), `fetch-config` = 0x000e0303, `diag-config` = 0x100, `stt-idx-width` = 10,
   `vm-offset` = bytes `00 00 00 80 00 00 00 08`, `vm-size` = 0x3ffff000, `reg`/IRQ. Find in the iOS 8.1 kernelcache (`AppleS5L8960XDART`; the functions near 0xffffff80026b2ed4-0xffffff80026c6000 were decompiled before) every register it writes at start-up and
   per stream/page (TCR, TTBR, TLB invalidate, fetch/diag config, error reflection, anything else) and compare with `drivers/iommu/apple-dart.c` (hoolock tree, S5L8960X paths). Question: does a missing register (fetch-config, error reflector, bypass/stream setup)
   turn a DMA access or a DART fault into a fabric-fatal event? Also: which DART stream id does the endpoint's DMA use? (Linux assumes RID 0x100 -> stream 0 via `iommu-map`; TTBR stream 1 is the null table; TCR = 0x80 enables only stream 0.)
2. **PCIe controller DMA/inbound.** In `AppleT7000PCIe`/`AppleEmbeddedPCIE` (kernelcache) list every controller/port register write between link-up and the first endpoint DMA (tunables from the ADT `apcie-config-tunables`, per-port AXI/inbound/DMA attributes,
   bus-master related, coherency). Compare with what our driver applies (`drivers/pci/controller/pcie-apple-t7000.c` after patches 0040-0057, `research/t7000-pcie-hardware-findings.md`). The earlier trace found no inbound/ATU programming; check again, including the shared window (index 9) and the port window.
3. **Reset cause after the fact.** Find, in the iOS kernelcache, the register map the iOS kernel reads at boot to report a reset/panic reason and PMU events (the D2207 PMU "event/fault" registers, SoC/PMGR reset status). Output: addresses/offsets and bit meanings that Linux
   can read **read-only** after the next boot to tell watchdog/PMU/brown-out resets apart. This is the highest-value item: it would tell us which kind of reset this is.
4. **Firmware side (private ROM + original image).** What exactly does the firmware do when the rx-post ring gets its first items? (ROM: `rom-live.bin`, base 0; image: `firmware/j81-12B410/wifi/C-4350__s-C2/rieslinga.trx`, base 0x180000; combined Ghidra projects under
   `/private/tmp/claude-501/.../scratchpad/fwproj*`; method in `research/2026-10-08-live-ram-device-state-analysis.md`.) In particular: how it forms host DMA addresses (64-bit values, the "host high 32" flag Broadcom uses for DMA over PCIe, address-extension bits), which DMA engine
   (PCIe2 core DMA channels) it uses for ring reads and index writes, whether it writes to host addresses outside the rings/scratch/ring-update buffers, and whether posting buffers starts anything with large current (radio/PHY).
5. **Linux side.** Read `drivers/net/wireless/broadcom/brcm80211/brcmfmac/{msgbuf,pcie,commonring}.c` (patched tree: `/nix/store/*-linux-hoolock-pcie-j81-wifi-h1b-t7001-source`) for anything in the rx-buffer posting path that reaches hardware besides the DMA mappings and the one doorbell
   (e.g. cache maintenance by physical address, large `dma_sync` ranges, `iommu` sync calls). The Apple DART driver's TLB-invalidate path in strict mode (`apple_dart_iotlb_sync_map`) runs 271 times in this step.

## Constraints
No hardware access (the user runs hardware tests). No downloads without asking the user. Never commit firmware, NVRAM, calibration, OTP, ROM/RAM dumps, MACs, device identifiers, Ghidra projects or session transcripts. Use `/opt/homebrew/bin/python3` (3.14), write scripts to files (no stdin heredoc python),
`command ls` (ls is aliased). Ghidra recipe: `tools/ghidra/README.md` (`ThumbSweep.java` for the raw Thumb firmware). If a Nix store path is missing, ask the user before downloading.

## Ready-to-run experiments the user can do in the meantime (no build)
`D13-feed0` and `D13-rxpost1` payloads are assembled under `artifacts/live/private/` (see `/tmp/wifi_toggle_payloads` if still present, or `ls artifacts/live/private | grep D13`); run with the commands in section 6 of the handoff.
