# BCM4350 Wi-Fi bring-up on the iPad Air 2: root cause, permanent fix, MAC provisioning

Status 2026-10-10: the brcmfmac control path works end to end on real J81 hardware (run 38, payload D20): the C2
`rieslinga` firmware boots, every ioctl completes, `wlan0` registers. This document explains **why** it failed for so long,
what the permanent fix is, how each piece was proven, and what remains. The day-by-day evidence is in
`research/2026-10-07-wifi-h1b-modelA-run.md` (runs 1-38); the previous hand-off state is in
`research/2026-10-09-wifi-h1b-handoff.md`. No MAC address, firmware, NVRAM, calibration or dump appears in this document or
anywhere in Git.

## 1. Symptom history

1. Firmware ran, but the host's first control request was never answered (runs 1-12): no MSI, no reply.
2. With the firmware running, as soon as brcmfmac posted its first ring item the iPad **hard-reset** within ~30 ms: display off,
   Apple logo 3 s later, no oops, no panic, no SError text (runs 13-31). Every harmless-looking host action was exonerated one by
   one: DMA mappings, ring writes, pointer writes, a doorbell with empty rings, ASPM, DEVICE_WAKE, deep-sleep ACK, shared-memory layout.
3. The decisive isolation (runs 31, 32): with **no rx buffers** the reset still happened at the first ioctl; with the
   **doorbell skipped** (patch 0084, `brcmfmac.h1b_no_bell=1`) there was no reset at all and the request sat unconsumed in ring 0.
   So the reset needed the firmware to *consume* the ring item: its first device-initiated DMA **read** through the PCIe DART.

## 2. Root cause: four things, all needed

| # | Problem | Evidence | Fix |
|---|---|---|---|
| 1 | NVRAM had no `macaddr`; the firmware's bmac attach returns 0x15/0x16 without it, so `wl` never attached and the PCIe interrupt was never enabled | live-RAM analysis + firmware decompile; run with a test MAC enabled the firmware (runs 1-12) | MAC from the device tree (section 4) or the private assembler for bring-up |
| 2 | The S5L8960X DART ignored our page-table **leaf** entries | run 35: page walk shows the intended leaf present; hardware says `NO PTE FOR IOVA`. Run 36: with Linux's native format the fault is `NO PMD` (directory bit 0 alone is not valid). Run 37: leaf `\|3` makes the DMA work | directory `\|3` (valid is bit 1, bit 0 set too) **and** leaf `\|3` (bits 1 and 0) |
| 3 | A DART fault produced a **silent SoC reset** instead of an interrupt | with Apple's start-up order the same fault arrives as an ordinary interrupt (run 33) | write Apple's `error-reflector` first, then `fetch-config`, `diag-config` (section 3) |
| 4 | Linux's S5L8960X fault handler dereferenced a NULL pointer (`cfg->dma_min` of the DART's own device) | run 33 oops at `apple_dart_s5l8960x_irq+0xa8` | patch 0086: NULL-safe, prints the raw error address |

Why the reset looked unexplainable: the leaf format (2) made every device read fault; the missing error reflector (3) turned that
fault into a SoC reset with no message; the NULL dereference (4) hid the fault the first time it became visible.

Why MSI "worked" the whole time: MSI delivery is a device **write** to the port's own decoder, never through the DART. No
device-initiated DMA had ever succeeded, so nothing was known about the DART path.

## 3. What Apple does and what we now do (J81 PCIe DART, ADT `dart-apcie1`)

Apple's `AppleS5L8960XDART::_dartRecoverFromPowerdown` (iOS 8.1 kernelcache `0xffffff80026c5d40`):

1. `DART+0x24 = error-reflector >> 12` (ADT `0x20ffff000` gives `0x0020ffff`) **before anything is read**;
2. restore TCR (`+0x0c`), `fetch-config` (`+0x30`, `0x000e0303`), `diag-config` (`+0x20`, `0x00000100`);
3. clear and poll the TLB operation.

Linux's `apple_dart_hw_reset()` started with a read of `+0x00` and wrote none of these. Patch 0089 does Apple's order for the DART whose
device-tree node has the properties below (no effect on any other DART).

Page-table entry format (iOS decompile `0xffffff80026c4c88-0xffffff80026c5078`, corrected by hardware):

| | iOS | what the hardware accepts | Linux generic DART1 format |
|---|---|---|---|
| TTBR | `(paddr >> 12) & 0xffffff \| 0x80000000` | same | same |
| Directory entry | `(paddr & 0xffffff000) \| 3` | `\|3` | `paddr \| 1` (rejected: NO PMD) |
| Leaf entry | `(pfn << 12) \| 2` plus a flag the lookup reads as `& 1` | `\| 3` (bit 0 is required; `\|2` is ignored: NO PTE) | `\| 1 \| 2` plus subpage fields |
| Page split | TTBR `page >> 18 & 3`, L1 `page >> 9 & 0x1ff`, L2 `page & 0x1ff` | same | same |

Rebased indexing (Apple's model A: IOVA minus the window start, window `0x80000000..0xbffff000`) plus the raw-index alias
(`pci_alias`) were on in every successful run. Whether the alias is strictly needed has **not** been isolated (section 7).

## 4. Permanent kernel changes (patches 0089 and 0090)

**0089, `apple-dart.c` / `io-pgtable-dart.c`:** the test toggles became device-tree properties on the DART node; module parameters stay as overrides.

| DT property (on `dart_apcie1`) | Effect | Replaces |
|---|---|---|
| `apple,ios-pte` | iOS-format entries (directory `\|3`, leaf `\|3`, no subpage/protection fields) | `apple_dart.ios_pte=1` (0081) |
| `apple,pci-alias` | map every PCI window page also at the raw index | `apple_dart.pci_alias=1` (0080) |
| `apple,error-reflector` (+ `apple,fetch-config`, `apple,diag-config`) | Apple's start-up order, section 3 | `apple_dart.h1b_apple_init=1` (0085) |

The leaf value `|3` is now the compiled default of `io_pgtable_dart.ios_leaf_bits` (was 0, then tested as 1 in run 37). All options parse only for `DART_S5L8960X`.
Patch 0086 (NULL-safe fault handler) stays unconditional. Patch 0087 (software page-table walk printed on a DART fault) stays behind `CONFIG_APPLE_DART_H1B_DIAG`.

**0090, `t7001.dtsi` / `t7001-air2.dtsi`:** `&dart_apcie1` gets the properties above with the ADT values; the Apple root port node is `pci@1,0`
(`reg = <0x800 ...>`: the port enumerates at 00:01.0, it was `<0>` and matched nothing); a child `wifi0: network@0,0` (`reg = <0x10000 ...>`,
`compatible = "pci14e4,43a3"`) carries an all-zero `local-mac-address` placeholder; `aliases { wifi0 = &wifi0; }`.
`pci_host_common_parse_ports()` and the device-wake lookup ignore `reg`, so PERST# and DEVICE_WAKE behave as before.

**Base bootargs** of the Wi-Fi H1B base payload now carry the proven link settings: `pcie_aspm=off pcie_apple_t7000.device_wake=1`.
Not isolated: whether ASPM-off or DEVICE_WAKE is strictly needed (section 7).

## 5. MAC address provisioning (the proper route)

Chain, all of it built in or already present:

1. iBoot's ADT has `/chosen/mac-address-wifi0` (value is a device identifier and is never recorded).
2. The prebuilt Hoolock m1n1 (checked: it contains the strings `mac-address-%s`, `wifi0`, `local-mac-address`) copies
   `/chosen/mac-address-<name>` into `local-mac-address` of the device-tree node that the alias `<name>` points to.
   Patch 0090 provides the alias and the node.
3. At firmware load, brcmfmac (`brcmf_fw_nvram_strip` in `firmware.c`) calls `eth_platform_get_mac_address()` for the PCI device. The all-zero
   placeholder counts as absent; a real address is written into the NVRAM text as `macaddr=...`, replacing any `macaddr` line already there.
4. The firmware's bmac attach finds it and attaches `wl0`.

So the public image carries no MAC (a zero placeholder), the private assembler needs no `--nvram-macaddr`, and a device without a MAC still
falls back to a `macaddr` line in its NVRAM. **Status: hardware-verified in run 39 (section 6).**

## 6. Verification plan

Run 39 (`wifi-h1b-modelA-D21-permanent-...`): the kernel built from patches 0001-0090 and base bootargs, assembled **without** any
`apple_dart.*`, `io_pgtable_dart.*` or `brcmfmac.h1b_*` boot argument and **without** `--nvram-macaddr`. Expected: `J81 PCIe DART options: ios-pte 1
pci-alias 1 apple-init 1` at boot, the full brcmfmac bring-up of run 38, and an interface address that is the device's own (not the test
address). If the device-tree MAC does not arrive (m1n1 does not fill the node), the firmware fails to attach exactly as in runs 1-12 and the
fallback is the private assembler's `--nvram-macaddr`.

Run 39 result (D21, 2026-10-10): **passed.** The payload had no `apple_dart.*`, `io_pgtable_dart.*` or `brcmfmac.h1b_*` argument and no NVRAM `macaddr`
(private manifest: `macaddr_added: false`). Boot log: `apple-dart 602002000.iommu: J81 PCIe DART options: ios-pte 1 pci-alias 1 apple-init 1` at 0.066 s; the firmware
attached `wl0` (0.68 s) and brcmfmac completed the full bring-up by 2.86 s: `Firmware: BCM4350/5 wl0 ... version 7.15.114.157`, `brcmf_cfg80211_attach`,
`brcmf_net_attach wlan0: Broadcom Dongle Host Driver`. No DART fault, no oops, no hold. Since the firmware cannot attach without a `macaddr` and the NVRAM had none,
the address necessarily came from the device tree: m1n1 filled the `wifi0` node from the ADT and brcmfmac wrote it into the NVRAM. (Only a boolean was checked;
the address itself was not recorded.) Cosmetic log lines present before and after: `pci 0000:00:01.0: retraining failed`, `of_irq_parse_pci: failed with rc=-22`
(MSI is used anyway), `regulatory.db` missing.

## 7. Not yet done / not isolated

- The minimal set: `apple,pci-alias`, `pcie_aspm=off`, `device_wake=1`, deferred registration, the `h1b_hold` (driver held for queries) are
  all part of the proven configuration but their individual necessity has not been tested. Each is a one-property/one-argument bisection now that DMA works.
- Remove the remaining test toggles once the permanent run is clean: `h1b_defer_s`, `h1b_hold`, `h1b_sync_ms`, `h1b_feed`, `h1b_rxpost`, `h1b_no_bell`,
  `h1b_tcm_idx`, `h1b_bell_only`, `h1b_step_s`, `h1b_ring_ids`, `h1b_apple_shared`, `h1b_fast_poll_us`, `apple_dart.pci_rebase`.
- An intermittent early-boot freeze in the initramfs (no USB network) hit 3 of the last ~8 boots at different steps (`### postmarketOS initramfs ###`,
  `configuring kernel firmware image search path`, mount step); a second boot of the same payload is always fine. Unexplained, not tied to Wi-Fi.
- No scan, association or transmit has been done; the standing rule applies until the user decides otherwise.
- Bluetooth (0x0402 write), touch firmware and the other open items are unchanged.

## 8. Lessons

- A hard reset with no text is often a **swallowed bus/IOMMU fault**. Program the reflector/error path first so the fault becomes
  observable, then print the page tables the hardware sees (patch 0087) instead of reasoning about them.
- Isolate "who consumes what": skipping the doorbell (0084) split host-side work from firmware-side DMA in one run.
- Parameterise the unknown bits (`io_pgtable_dart.ios_leaf_bits`) so a format question costs a boot argument, not a 15-minute kernel build.
- Compare against the decompile, then let hardware correct it: Apple's `| 2` leaf plus a "flag in bit 0" was really `| 3`.
