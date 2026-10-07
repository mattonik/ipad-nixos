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
