# Wi-Fi H1B run 1 (DMA model A, private C2 firmware): result and classification

Date: 2026-10-07. First run of the private Model A payload from `2026-10-07-wifi-h1b-payload.md`.
Payload: 0052-0057 + 0063 + 0064 + brcmfmac PCIe, C2 `rieslinga` firmware/CLM/TxCap + tuple-selected
NVRAM staged under the canonical names. Loaded through the usual palera1n/PongoOS route. The raw
`/proc/cmdline`, `dmesg` and run record are private (`artifacts/live/private/wifi-h1b-modelA-*/run-*`).

## Identity

`/proc/cmdline` on the device carried the payload's `j81.run_id` token: **device_token_observed**
(first identity-qualified hardware run). The overlay listing on the device shows exactly the four
brcmfmac files with the expected sizes.

## What happened (boot-relative seconds)

| t | Event |
| --- | --- |
| 0.24-0.36 | Known-good host path: MSI domain, link `0x3011`, endpoint `14e4:43a3` enumerated, DART/iommu group 0 |
| 0.37-0.54 | brcmfmac probes the endpoint; recognises **BCM4350/5**, ChipCommon rev 47 (matches the OTP probe), RAM 0xc0000; picks `brcmfmac4350c2-pcie`; board type is `apple,j81` (from the machine compatible) |
| 0.55 to 62.4 | **60 s stall**: the loader first requests `...apple,j81.*` names that do not exist, and the `FW_LOADER_USER_HELPER_FALLBACK` sysfs fallback waits for its 60 s timeout before the canonical names are tried (the same happens to `regulatory.db`) |
| 62.45-62.50 | firmware, then NVRAM downloaded (canonical `brcmfmac4350c2-pcie.{bin,txt}`), ARM started |
| 62.55-62.57 | **firmware runs**: shared RAM found, PCIe protocol version 5, console prints `RTE (SDIO-MSG_BUF) 7.15.114.157 (r504364) on BCM4350 r5`, `pciemsgbuf0` driver up; 40 flowrings; rings and 255+8+8 buffers posted; mailbox doorbell writes succeed |
| 62.592 | `cur_etheraddr` control query submitted; **an interrupt is taken within about 50 us**: `quick_check_isr`, then `isr_thread` with status `0x100` (`FN0_0`, the D2H mailbox-data bit) and `D2H_MB_DATA: DEEP SLEEP REQ`, which the driver acknowledges |
| 64.607 | `brcmf_msgbuf_query_dcmd: Timeout on response for query command`; `cur_etheraddr failed -5`; "dongle is not responding"; `brcmf_fw_crashed`; the driver removes itself (a `__flush_work` warning in the remove path is the stock brcmfmac failure-unwind quirk) |

No `wlan0` was created, no scan/association/transmission happened, no DART error line appeared (the
only DART line in the whole log is its init message), no port `MSI_ERR`/`MSI_BAD_DATA` evidence.

## Classification (matrix of `2026-10-07-wifi-h1b-evidence-matrix.md`)

- The asset/loader gate **passed**: right files, non-empty NVRAM, firmware and NVRAM downloaded, firmware booted and ran.
- Host-side ring setup completed and the mailbox/doorbell write path works.
- **An endpoint-originated interrupt was delivered to Linux** while the MSI was configured as the only interrupt source
  (`of_irq_parse_pci` finds no INTx, so `pdev->irq` can only be the MSI): the first non-configuration evidence that the
  endpoint to doorbell to (DART/fabric) to AIC to Linux path works. It was a mailbox event (deep sleep request), not the
  control completion, and the AIC line/count could not be read in time (see below), so it counts as strong but not
  line-identified evidence (slot 8 / AIC 232 not confirmed).
- The control request itself got **no response and no D2H completion**. Matrix row: "control request remains pending ... firmware/DMA or
  endpoint-start failure". With zero DART faults, the leading explanation is the DMA model: the firmware's reads/writes of the
  host rings may not be reaching the data the driver wrote (or the response is not arriving back), without any translation
  fault being reported. This is exactly the question model B was defined for.

So: **not an H1B pass, and not an MSI failure.** H1B (control completion by MSI) is undecided because the control path
failed one step earlier.

## Observation gaps to close before the next run

1. The capture ran after the driver had removed itself, so the endpoint MSI capability readback and `/proc/interrupts` show an
   already torn-down state (zeros). The capture must sample while brcmfmac is bound (about 60 s after boot with the current
   fallback timing), as a time series, to prove address `0xbffff000`, data 8 and the AIC 232 count.
2. The 60 s stall is a loader artifact of the board-suffixed lookups plus the sysfs fallback; it hides the interesting window.
   Either disable `FW_LOADER_USER_HELPER_FALLBACK` for the test kernel or stage the files under the first requested name too.
3. brcmfmac's own debug does not print the ring IOVAs; a DMA-model discrimination needs them (and a DART fault/stream state
   readout), so a small test-only logging patch is warranted before a Model B comparison.

## Next (not started; each hardware run needs the user's go-ahead)

- Improve the capture (watch mode) and fix the 60 s stall; add ring-address logging; then repeat Model A once for a cleaner record.
- Build and run Model B (`m1n1-hoolock-pcie-j81-dma-raw`) with the same private overlay, now that Model A fails at the DMA/ring
  stage, and compare using the same classification.

# Run 2 (Model A + 0065 diagnostics, sysfs fallback off): result

Payload `wifi-h1b-modelA2-*` (private), identity-qualified again (token seen in `/proc/cmdline`). With the sysfs fallback
removed the 60 s stall is gone: firmware, NVRAM and the control query all happen in the first 3 s of boot, before the
shell is reachable, so the watch (started after the device answers pings) sampled one tick after brcmfmac had already
removed itself. The in-kernel `t7000-h1b:` log carries everything instead (private run record, `dmesg.txt`).

## Host side: all as designed

- IOMMU domain: type `0x3` (DMA), aperture `0x80000000..0xbfffefff`, force aperture 1, i.e. `0063`/`0064` are active.
- Every DMA buffer given to the firmware is inside the window, allocated top-down (control submit ring `0xbfffe000`,
  rx-post ring `0xbfff0000`, ... scratch `0xbffdf000`, ring-update `0xbffde000`), and the DART resolves each IOVA to a
  physical page (`0x804ea0000`, ... in DRAM). The translation tables are correct from the CPU side.
- MSI: capability control `0x0089`, address `0x00000000_bffff000`, data 8 both after `pci_enable_msi` and after
  `request_irq` and at the failure snapshot; interrupt chain `PCI-MSI hwirq 0` to `pcie hwirq 8` to AIC `65768` (event 232, i.e.
  slot 8 / AIC 232), exactly the designed mapping.
- One interrupt was delivered (`isr #1 irq 56 mailbox status 0x100`, the firmware's DEEP SLEEP REQ): the MSI route works
  end to end for a device-originated MSI. `pci command 0x0406` at the snapshot (memory + bus master).

## Device side: the firmware consumed nothing

Snapshot when the control query times out (2.0 s after submission):

| Ring | Host w | Device r | Device w |
| --- | --- | --- | --- |
| 0 control submit | 17 | **0** | 17 |
| 1 rx-post | 255 | **0** | 255 |
| 2, 3, 4 (device to host) | 0 | 0 | 0 |

- the device never advanced the read index of either host-to-device ring: it fetched none of the 17 control items nor the 255
  rx-post buffers (the first control item in host memory is a well-formed ioctl request pointing at an in-window buffer);
- the d2h scratch word the device writes by DMA is still `0`, and there is no completion;
- no DART translation-fault message (the S5L8960X fault handler exists and would print `translation fault: ... NO TTBR/PTE`),
  no port `MSI_ERR`/`MSI_BAD_DATA` evidence, no firmware crash text; the firmware console printed only its start banner.

## Classification

Matrix row "control request pending, no D2H ring update": **the first host-to-device DMA read never completes** (or the firmware
never reacts to the doorbell), while device-to-host signalling works (MSI/mailbox). The MSI route is therefore *validated for
delivery* but H1B (a control *completion* by MSI) cannot be observed until the firmware reads its rings. Two explanations remain
and are exactly what the model comparison was designed to separate:

1. DMA read path: the endpoint's reads of the host rings are not reaching memory correctly (fabric/DART address model), possibly
   without a DART error being latched or reported (DART IRQ delivery itself is not yet proven);
2. doorbell/protocol: the firmware does not see or act on the host-to-device doorbell (for example after its deep-sleep
   handshake) so it never starts fetching, which would make the DMA model irrelevant.

## Next (offline work first; each hardware run still needs the user's go-ahead)

- Build Model B (`m1n1-hoolock-pcie-j81-dma-raw` equivalent for the Wi-Fi payload) with the same overlay and diagnostics.
- Add read-only discriminators for explanation 1: the DART's latched error registers (S5L8960X `ERROR`/`ERROR_ADDR`, plus
  stream state) and the port-1 event status/mask (`+0x100`/`+0x104`, read-only) exposed through debugfs so the run record can read
  them after the failure without any write; whether reading `+0x100` has side effects must be confirmed from the iOS trace
  (the Apple driver reads it in its handler and acknowledges with a separate write).
