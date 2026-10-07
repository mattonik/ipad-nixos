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

# Run 3 (Model A + 0065 + 0066): register and PCIe-error evidence

Same failure (first control query times out at 2.0 s, device-side read index of the submit and rx-post rings still 0, one
mailbox interrupt) with the new read-only dumps taken afterwards (debugfs had to be mounted by hand: the debug init does not mount
it; the run record now mounts it, a kernel-file exposure only).

## DART (`/sys/kernel/debug/apple-dart-602002000.iommu/regs`)

- `tcr 0x80` (stream 0 translating); stream 0's four TTBRs hold valid table pointers (`0x8080271a..d`), the other streams point
  at the shared dummy table (`0x80ffff80`). The endpoint (requester `0x100`, stream 0) has live tables.
- `error 0x00000100`, `error_addr 0x01e0f000`, **fault flag (bit 31) clear**, and the AIC DART fault interrupt (AIC event 216) count is **0**.
  Apple's own handler (kext function at `0xffffff80026c53f0`) decodes the cause from bits 0 (TTBR invalid), 1 (STE invalid), 2
  (PTE invalid), 3 (write protect), 6:5 (AXI slave error/decode), 10 (write), 25:24 stream: none of the cause bits is set in `0x100`
  (bit 8 is not decoded there; the latched address is a stale value, not one of our buffers). So **no translation fault is recorded**.

## T7000 port 1 (`/sys/kernel/debug/t7000-pcie/port1_regs`)

- link start 1, state `0x15`; MSI config `0x31` / `0x00080008` as programmed; `msiaddr` 0.
- event mask `0x0070afff` (link-up/down, MSI error, bad MSI data, request-address and completion-timeout events unmasked),
  event status `0x00003000` (bits 12 and 13, link-up related and masked-or-benign): **no MSI_ERR, MSI_BAD_DATA, REQADDR_GT32 or CPL_TIMEOUT latched**.

## PCI error state

Endpoint and root port: AER capabilities present; uncorrectable and correctable status registers are all **zero**, root error status
zero. No unsupported request, completer abort, completion timeout or poisoned TLP was recorded on either side. The command register
at the end was back to memory-only because brcmfmac had already torn itself down (bus master was set at the failure snapshot).

## What this changes

There is **no evidence of any DMA error**: no DART fault, no PCIe error status, no controller completion-timeout. The firmware
runs, the MSI/mailbox interrupt path works, the host-side mappings are right, and still the firmware never advances its read index
of the host-to-device rings. That favours explanation 2 (the firmware does not act on the host-to-device doorbell/protocol
state, for example because it sent its own deep-sleep request and nothing wakes it) over a DMA translation problem; Model B stays
a useful but now less likely discriminator. The firmware's first deep-sleep request arrives right after the three ring doorbells
and before the control query, so the host/firmware handshake around the doorbell and the deep-sleep request (what Apple's host
driver sends after `shared` setup, host-ready flags, the doorbell register and any wake action) is the next thing to compare with the iOS
Wi-Fi bus driver rather than more translation experiments.

# Run 4: E1, deep-sleep request not acknowledged (Model A + 0067 `brcmfmac.h1b_ds_ack=1`)

Identity-qualified (token in `/proc/cmdline`). The toggle took effect: `t7000-h1b: deep sleep request NOT acknowledged (h1b_ds_ack=1)`
(brcmfmac's own unconditional debug line "sent DEEP SLEEP ACK" still prints right after it; the line is misleading in this mode, no acknowledgement
was sent). Everything else is the same as the earlier runs: the firmware's `DEEP SLEEP REQ` arrives ~10 ms after the control query is submitted (one
interrupt, `isr #1`, status `0x100`), the control query times out at 2.0 s, rings 0 and 1 have device-side read index 0 (17 and 255 items posted), the d2h
scratch word is 0, no DART or PCIe error.

One new detail: the mailbox interrupt status at the failure snapshot is `0x0` here, whereas the stock run left bit 0 set (`0x1`) after our config-space
acknowledgement. So the stock acknowledgement did reach the device hardware (it latches that bit) and the firmware never consumed it either. The firmware
behaves the same whether or not it is acknowledged, so **the acknowledgement is not what stops it**: with `device_wake_opt=1` it is either asleep after its
own request and needs the wake pin, or stuck for another reason before servicing any host message.

Status of the hypotheses:
- deep-sleep acknowledgement as the cause: **refuted** (E1);
- the ACK route (config `0x98` vs MMIO `0x144`, E3): unlikely given the latched bit, not tested;
- DEVICE_WAKE (GPIO 165, E2): still the leading explanation; it is a GPIO write to the module and needs the user's explicit go-ahead.
