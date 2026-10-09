# Wi-Fi H1B handoff (2026-10-09): firmware is up; the first ring buffers reset the iPad

Everything below is verified on hardware unless marked "static" or "hypothesis". Detail per run: `2026-10-07-wifi-h1b-modelA-run.md` (runs 1-30); campaign overview:
`2026-10-08-wifi-h1b-campaign-summary.md`; payload/build records: `2026-10-07-wifi-h1b-payload.md`; firmware analysis: `2026-10-07-c2-firmware-static-analysis.md`,
`2026-10-08-live-ram-device-state-analysis.md`, `2026-10-08-wifi-macaddr-provisioning.md`; Apple driver comparison: `2026-10-07-ios-wifi-bus-driver-analysis.md`.

## 1. Where we are

**Solved.** The BCM4350 (C2 stepping, PCIe `14e4:43a3`) with the private C2 `rieslinga` firmware boots and its PCIe/msgbuf driver is fully open once the NVRAM has a `macaddr` line.
Before that the firmware's `wl` (D11) core failed to attach (bmac attach returns 0x15), `pciedev open()` never ran, the PCIe2 interrupt stayed masked and the host's doorbell was ignored (runs 1-14).
Evidence on hardware (run 25): PCIe2 `IntMask` = `0x010303c0`, shared flags `0x00010005`, firmware console `wl0: Broadcom BCM4350 802.11 Wireless Controller 7.15.114.157`. The test payloads add a locally
administered MAC (`--nvram-macaddr 02:6a:38:70:00:01`). The permanent route (device tree + m1n1 filling `local-mac-address`) is described in `2026-10-08-wifi-macaddr-provisioning.md`.

**Blocking problem.** With the firmware running, the iPad **hard-resets** (display powers off within ~30 ms, Apple logo ~3 s later; no panic/oops/SError text ever shown; filmed at 4K/120 fps, run 23)
as soon as brcmfmac starts posting receive buffers in `brcmf_proto_msgbuf_attach()` (`msgbuf.c`: ~271 `dma_map_single` mappings, ring item writes, the write-pointer update and one doorbell write to PCIe2 `0x140`).
The USB link dies with it, so the host log is lost; the last line the Mac receives only bounds the reset time from below.

## 2. What the hardware has shown (facts)

| # | Observation | Run |
|---|---|---|
| 1 | Firmware alive and running: whole-RAM snapshot/diff over 9 s shows only timer-like words changing; ARM CR4 core up | 14 |
| 2 | 41 s of idle running firmware (30.5 s -> 71.6 s), through every host setup phase (download, ring buffers, scratch, `request_irq`, msgbuf hookup), no reset | 22 |
| 3 | A doorbell with **empty rings** (and, in D7, TCM indices instead of host-memory indices) is harmless: survived 8.4 s (D7) and 20 s pauses (D8); the firmware reacts (RAM diff: new `txf` object, ring pointers) | 24, 25 |
| 4 | Reset follows the host's buffer feeding every time; with 150 ms marker sleeps the last delivered line is `sync: before feeding` (26.204 s) after attach entry, ioctl-buffer mapping and the "Feeding buffers" line were all delivered 150 ms apart; ASPM was off | 30 |
| 5 | DART registers look clean right before: `tcr` 0x80, `error` 0x100 / `error_addr` 0x01e0f000 (stale, unchanged), TTBR stream 0 = 0x80804232..35, stream 1 = 0x80ffff80 (null table); port-1 event status 0x3000 stale | 25 |
| 6 | PCIe2 core rev 11; BAR2 = 4 MiB maps ARM addresses (ROM 0x0-0xA0000, RAM from 0x180000, size 0xC0000); reads past the mapped ROM reset the iPad | 12, 14 |
| 7 | Firmware shared struct v5, flags 0x00010005 after open (bit 16 = DMA indices offered); ring memory table word0 (id/type) is zero unless the host writes it; firmware console silent after init | 12, 13, 25 |

## 3. What has been ruled out (each with a hardware test; payload names in the run notes)

DMA translation *index model* (A rebased page 0 vs B raw 0x80000, and **both** mapped at once: `apple_dart.pci_alias=1`); the DART **entry format** (Apple's iOS S5L8960X format: valid bit 1, directory `|3`, leaf `|2`:
`apple_dart.ios_pte=1`); ASPM/L1 (`pcie_aspm=off`); deep-sleep ACK; DEVICE_WAKE; ring id/type words; shared-memory differences vs Apple (scratch, ring-update buffer, ring depths); host-memory vs TCM indices
(both end in the same reset); firmware activity while idle; payload size; ChipCommon `0xc40/0xe00` reads (those were a separate, real cause of resets in runs 15-17: my own diagnostic, now removed).
Model B (`apple_dart.pci_rebase=0`) hung the boot twice before any Wi-Fi code ran (run 19-20); unexplained, may be the same intermittent early-boot hang below.

## 4. Open questions / hypotheses (not yet separated)

1. **Is it the host's DMA mapping of the buffers (CPU side), the firmware's DMA read/write of ring items, or the firmware's reaction to buffers (e.g. radio/power start)?**
   Cheapest discriminators are built and assembled (private, ready): `D13-feed0` (`h1b_feed=0`: no rx buffers; the first ioctl is the first ring traffic) and `D13-rxpost1` (`h1b_rxpost=1`: 17 instead of 271 buffers).
   Not yet run. Run `D13-feed0` first; its markers continue to `query ioctl about to be posted`.
2. **PCIe inbound/AXI path of the controller** (no inbound/ATU programming has been found in Apple's `AppleT7000PCIe` static trace; MSI works because the port decodes MSI writes itself, never through the DART, so the MSI success
   proves nothing about DMA). Unexplored: which `apcie-config-tunables` entries and port registers Apple programs for DMA.
3. **DART state beyond TCR/TTBR**: the ADT `dart-apcie1` node carries `error-reflector` = 0x2_0fff_f000 (twice), `fetch-config` = 0x000e0303, `diag-config` = 0x100, `stt-idx-width` = 10, `vm-offset` = bytes
   `00 00 00 80 00 00 00 08`, `vm-size` = 0x3ffff000. Apple's driver may program registers for these; Linux's `apple-dart` writes only TCR/TTBR/invalidate. A DART fault whose "reflection" target is unconfigured could
   escalate to a hardware reset instead of an AER/IRQ.
4. **Power**: the reset might be a PMU/brown-out event when the firmware starts something (radio/PHY) in response to the buffers; nothing measured. The D2207 PMIC may keep a fault/event flag across the reset (idea below).
5. **Intermittent early-boot hang** (4 of ~20 deferred-start boots froze at `### postmarketOS initramfs ###`, none of the earlier non-deferred boots): only seen with the 25-40 s deferred driver registration (chip powered, idle, DEVICE_WAKE high); D13 with
   `pcie_aspm=off` booted fine (n=1). Unexplained.

## 5. Ideas for the next experiments (ordered by cost)

1. Run `D13-feed0`, then `D13-rxpost1` (no build needed).
2. Finer markers inside the rx data fill (a marker/sleep every N buffers; cannot sleep under the commonring lock, so split `brcmf_msgbuf_rxbuf_data_post` calls, or log from a thread that polls a progress counter).
3. **Identify the reset cause after the fact:** after a reset, boot Linux again and read read-only: D2207 PMU event/fault registers (an iOS "PMU event/reset reason" register map can be decoded from the kernelcache), the SoC/PMGR reset-reason, `/proc/uptime`; add a debug command for it (the h1b query interface pattern; keep to a safe list).
4. Log DART error registers (`error`, `error_addr`) **in the loop** before and after each map call from a second CPU/thread, or force one deliberate DART fault of a *harmless* kind (unmapped IOVA used by a harmless firmware-visible address) to see whether any DART fault resets the machine.
5. Decode and (if Apple programs them) apply the DART `fetch-config`/`diag-config`/error-reflector registers; compare the complete iOS `AppleS5L8960XDART` start sequence with `apple-dart`'s.
6. Compare the iOS PCIe driver's per-port register writes after link-up with ours (tunables), looking for DMA/inbound-related ones.

## 6. How to run and observe (all tooling is in the repo; see also `docs/plans/2026-10-08-j81-base-package.md`)

* Build: `nix build .#packages.x86_64-linux.m1n1-hoolock-pcie-j81-wifi-h1b-base -o artifacts/live/gcroot-h1b-base` (~25-35 min on the Linux builder; builder auto-GC can fail a build: just retry). Patches 0001-0083
  are listed in `kernel/hoolock-pcie-j81-wifi-h1b.nix`; every patch has an offline test (`tools/check_offline.py --pcie-j81-selftest-source artifacts/live/gcroot-msi-source`; use `/opt/homebrew/bin/python3`).
* Private payload: `boot/assemble_private_wifi_payload.py --public <base> --assets firmware/j81-12B410/wifi/C-4350__s-C2 --out artifacts/live/private/<name> --extra-bootarg ... --nvram-macaddr 02:6a:38:70:00:01`
  (allowlisted test bootargs only; the private overlay, firmware and NVRAM never enter Git or the Nix store).
* Run (needs the user: DFU + `sudo boot/vendor/palera1n-macos-arm64 --pongo-shell --override-pongo "$PWD/boot/Pongo.bin" --debug-logging`, then "pongo up"):
  `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=$PWD/artifacts/live/gcroot-pyusb/lib/python3.14/site-packages /opt/homebrew/bin/python3 boot/load_m1n1.py <dir>/m1n1-linux.bin`, then
  `/opt/homebrew/bin/python3 boot/h1b_stream.py <dir>` (follows `/proc/kmsg` to a private log; needs `brcmfmac.h1b_defer_s=25` so the USB network is up first).
* Probes while the machine is alive and held: `boot/h1b_query.py` (`shared`, `core pcie2 0x20 4`, `snap`/`diff`, gated ROM reads) and `boot/h1b_window_probe.py` for the pause windows (`h1b_step_s`, `h1b_bell_only`).
* Kernel toggles (all off by default; module parameters `brcmfmac.*`, `apple_dart.*`, `pcie_apple_t7000.*`): `h1b_hold`, `h1b_defer_s`, `h1b_step_s`, `h1b_bell_only`, `h1b_tcm_idx`, `h1b_feed`, `h1b_rxpost`, `h1b_sync_ms`,
  `h1b_fast_poll_us`, `h1b_ring_ids`, `h1b_apple_shared`, `h1b_ds_ack`, `device_wake`, `pci_rebase`, `pci_alias`, `ios_pte`.
* GC roots in `artifacts/live/` (never delete): `gcroot-h1b-base`, `gcroot-msi-source`, `gcroot-pyusb`. Private data: ROM/RAM dumps, Ghidra projects (scratch directory), firmware, NVRAM, run directories.
* The J81 base package (charging policy, telnet+SSH, debug console, tablet tools) is built into every H1B payload (`mkJ81BasePayload`).

## 7. Safety rules that still apply

Every hardware run is a separate explicit decision by the user. Standing approvals needed per run: PMU `0x0403` write (REG_ON), the DEVICE_WAKE GPIO 165 drive, `pcie_aspm=off`-type toggles are boot arguments only. No scan, association or intentional transmission;
no write to PCIe port `+0x168`; no Bluetooth `0x0402` write; no new hardware purchases; never commit firmware, NVRAM, calibration, OTP, ROM/RAM dumps, device identifiers or session transcripts. Window-moving register reads only on the safe list
(PCIe2 `0x20 0x24 0x48 0x4c 0x140 0x144`; ChipCommon `0x58-0x6c`); never read BAR2 beyond 0xA0000. Commit each hardware result immediately (path-limited commits, trailer `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`).
