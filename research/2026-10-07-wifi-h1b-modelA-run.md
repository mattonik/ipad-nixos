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

# Run 5: E2, DEVICE_WAKE (GPIO 165) held high (Model A + 0067 `pcie_apple_t7000.device_wake=1`)

Identity-qualified (token in `/proc/cmdline`), with the user's explicit go-ahead for the GPIO output.

- `t7000-pcie: DEVICE_WAKE asserted, GPIO reads 1`: the pin was driven high after link-up and read back high. Link, enumeration, DMA mappings, MSI
  capability and interrupt chain are unchanged from the earlier runs.
- **The firmware behaviour changed for the first time**: there is **no deep-sleep request and no interrupt at all** (`isr count 0`, no mailbox
  status), whereas every earlier run had the request about 10 ms after the first control query. Holding DEVICE_WAKE high therefore does what iOS relies on:
  the firmware stays awake and no longer asks to sleep. This confirms the link between the NVRAM's `device_wake_opt=1`, the wake pin and the
  firmware's sleep request.
- But the **rings are still not consumed**: control and rx-post rings device read index 0 (17 and 255 posted), d2h scratch word 0, the control query times out
  at 2.0 s with the same `-5`, no DART or PCIe error. The sleeping firmware was therefore *not* the only reason it ignored the rings.

So there are two separate findings: (1) DEVICE_WAKE must be driven (done for E2; the controller driver or DT needs a permanent, board-correct
implementation later); (2) with the firmware awake, something else still keeps it from servicing the rings. The remaining evidence gap is the firmware's own console and
the mailbox/shared-structure state: the console is only read when an interrupt arrives or on error, and E2 produced no interrupt, so we saw only the banner.
Next (read-only): poll the firmware console every 100 ms while the query is pending, read it at the failure snapshot, and log the shared-structure flags,
version, mailbox data words and mailbox registers.

# Run 6: E2b, DEVICE_WAKE high with the firmware console poll and shared-state snapshot (Model A + 0068)

Identity-qualified. Same as run 5 plus the new read-only evidence:

- **The awake firmware is completely silent**: the console was polled every 100 ms for the whole 2 s the control query was pending and printed nothing after its
  start banner (no error, no trap text, no "host not ready"). It is alive but idle, not crashed.
- Shared structure: protocol **version 5, flags `0x00000005`** (only the version field; no host-ready doorbell flag, no DMA-index capability, so TCM indices and no
  extra "host ready" step are right for this firmware). Host-to-device and device-to-host mailbox words 0 (nothing pending in either direction); the host's
  mailbox mask is `0x30300`.
- **`h2d_mailbox_0` still reads `1` two seconds after the host rang it**: the doorbell latch was never cleared, i.e. the firmware never serviced the
  host-to-device doorbell, consistent with the ring read indices staying at 0 (control ring 17 items, rx-post 255) and the scratch word 0.
- No interrupt (isr count 0), no DART or PCIe error.

So with the wake pin held high the firmware stays awake (confirmed twice) and does not process the doorbell. What the missing piece is remains open. The ADT
shows the Wi-Fi port is enabled by the Wi-Fi driver itself (`manual-enable`, port control function) with ASPM and L1 power-management settings of its own
(`pci-aspm-default 2` on the endpoint, `pci-l1pm-control`, `~cpie-l1ss-workaround 0xf`), while Linux enabled L1 on both ends by default (`ASPM: default states L1`).
A link that has dropped into L1 would explain a device that cannot issue its DMA reads or serve the doorbell without reporting any error, so the cheapest next test
is to run with ASPM disabled (`pcie_aspm.policy=performance`), which needs no new kernel.

# Run 7: E4, DEVICE_WAKE high and ASPM disabled (Model A + 0068, `pcie_apple_t7000.device_wake=1 pcie_aspm.policy=performance`)

Identity-qualified. The change took effect: after boot both ends read `LnkCtl` ASPM control bits 0 (disabled; link x1 at 2.5 GT/s, `LnkSta` `0x1011` endpoint /
`0x7011` root port), compared with the "default states L1" the kernel had enabled in the earlier runs. Result: **identical to run 6**: firmware awake and silent
after its banner, no deep-sleep request, no interrupt, `h2d_mailbox_0` still `1`, control ring 17 and rx-post ring 255 items posted with device read index 0, scratch word 0,
query timeout at 2 s, no DART or PCIe error.

**ASPM/L1 is eliminated** as the cause. Eliminated so far: DMA translation errors (no fault anywhere), the MSI route (an interrupt was delivered when the firmware asked
for one), the deep-sleep acknowledgement (E1), the firmware sleeping (E2: it stays awake with DEVICE_WAKE high), and ASPM. Established: the host side is right, the
firmware runs its start-up and then neither prints nor services the host-to-device doorbell.

## Run 8: G1 (DEVICE_WAKE high, read-only ChipCommon GPIO snapshot, patch 0069)

Payload: Model A + 0069, `pcie_apple_t7000.device_wake=1`. Same stall as runs 5-7: DEVICE_WAKE GPIO reads 1,
firmware banner, control query times out, isr count 0, mailbox int 0x0, `h2d_mailbox_0` stays 0x1,
host-to-dev and dev-to-host mailbox words 0, d2h scratch 0.

ChipCommon snapshot, identical after `request_irq` (0.73 s) and at failure (2.81 s):

| register | value |
|---|---|
| gpiopullup 0x58 | 0x00000000 |
| gpiopulldown 0x5c | 0x00000002 |
| gpioin 0x60 | 0x0000290e |
| gpioout 0x64 | 0x00000000 |
| gpioouten 0x68 | 0x00000001 |
| gpiocontrol 0x6c | 0x00000000 |
| 0xc40 | 0x00000001 |
| 0xe00 | 0x00022000 |

Reading: the firmware has already made chip GPIO 0 an output driving low. That equals the state Apple's D0 path
writes (`FUN_c0e27c(.., 0)`: control 0, outen 1, out 0), so the missing-GPIO0-setup hypothesis is not supported for
the low level. The GPIO is not held high at any point; Apple's high write (`FUN_c10a24`, caller unknown) is the
open question. `0xc40`/`0xe00` hold different values from what Apple writes (0 and 1) but their meaning is unknown, and
the firmware may have set them itself. Nothing changes between 0.7 s and 2.8 s, which is consistent with a firmware
that is idle rather than hung mid-init. G0 (stock) not yet run.

## Run 9: G0 (stock, no toggles, ChipCommon GPIO snapshot)

Same stall. The firmware's deep-sleep request arrived (isr #1, mailbox status 0x100), the stock config-space
ACK was written (host-to-dev mailbox word 0x2), and the control query still timed out; `h2d_mailbox_0` stayed 0x1,
d2h scratch 0, mailbox int 0x1 at failure.

ChipCommon GPIO, identical after `request_irq` and at failure, and identical to run 8 except `gpioin`:
pullup 0, pulldown 0x2, **in 0x0000290c** (G1: 0x290e), out 0, outen 0x1, control 0, 0xc40 = 1, 0xe00 = 0x22000.
`gpioin` bit 1 follows the host DEVICE_WAKE level (1 with the GPIO high, 0 without), so chip GPIO 1 is the
DEVICE_WAKE input and the wiring is confirmed. Chip GPIO 0 is an output driving low in both runs, and the rest of the
GPIO block does not depend on the host. Conclusion: no GPIO-side difference explains the stall; chip GPIO 0 and the
GPIO block are closed as hypotheses unless Apple's high write (`FUN_c10a24`) is found to matter.

## Run 10: S7 (Apple shared-memory parity, mask 7, DEVICE_WAKE high)

Payload: Model A + 0070, `brcmfmac.h1b_apple_shared=7` and `pcie_apple_t7000.device_wake=1`. The log confirms the
toggle took effect: 4096-byte scratch buffer (IOVA 0xbfff5000), "ring-update buffer not provided". Result is the
same stall as runs 5-9: no interrupts, `h2d_mailbox_0` stays 0x1, mailbox words 0, d2h scratch 0, control query
times out. Matching Apple's scratch length, omitting the ring-update buffer and using Apple's ring depths therefore
makes no difference. These three shared-memory differences are closed as causes (taken together; not bisected
because the combined run is negative).

Note: `h1b_run_record.py` needs Python 3.10+ (`ipad_console.py` uses `X | None`); the first attempt with the system
`python3` (3.9.6) failed before touching the device; rerun with `/opt/homebrew/bin/python3`.

## Run 11: Model B (raw DMA window, no Apple rebase), stock wake

Payload `wifi-h1b-modelB-20261007T125638Z` (public base `...-h1b-base-raw`: 0063 without 0064, no toggles/0068/0069).
Same stall as every Model A run: the deep-sleep request arrived (isr #1, mailbox status 0x100), the control query
timed out, isr count 1 and mailbox int 0x1 at failure, d2h scratch 0, no DART fault, no MSI error. The aperture is
reported as 0x80000000..0xbfffefff in both models. DMA Model A versus B therefore makes no difference to the stall;
the DMA-model hypothesis is closed only in the weak sense below.
Caveat: the Model B ring IOVAs in the log (e.g. 0xbfffe000, 0xbfff0000) are the same top-down addresses Model A uses,
so B does not exercise a different addressing scheme at the device. Both models hand the device the same IOVAs; the
difference is only in how the host-side allocator and aperture were derived. A real "raw low-IOVA" control would need
a different window, which has not been tried.

## Run 12: Q1 (patch 0071 hold + query interface, DEVICE_WAKE high) - first look inside the firmware's shared memory

Setup failed as before (same stall; `h1b_hold` left the driver bound, "device held for queries"). The failure-time dump
and the first two queries worked. The third query, `core pcie2 0x0 256` (a PCIe2-core register sweep through the BAR0
window), killed the USB link and the iPad restarted. The PCIe2 sweep is therefore unsafe: some register in 0x00-0xff
hangs the bus or faults when read in this state. Patch 0072 limits `core` reads to a safe-register list.
(The ChipCommon GPIO read before it returned the same values as runs 8-10: in 0x290e, out 0, outen 1.)

Decoded shared memory (firmware build id `eeb18431`; all addresses TCM offsets, version 5, flags 0x5):

| field | value |
|---|---|
| console address (+0x14) | 0x0023deb0 |
| max_rxbufpost (+0x22) | 255 |
| host-to-dev / dev-to-host mailbox data (+0x28 / +0x2c) | 0x0023aa7c / 0x0023aa80 |
| ring info (+0x30) | 0x0023a60c |
| scratch len / addr (+0x34 / +0x38) | 8 / 0xbffdf000 (what the host wrote) |
| ring-update len / addr (+0x40 / +0x44) | 0x400 / 0xbffde000 (host-written) |
| +0x50 | 0x001883f9 (looks like a Thumb code pointer; meaning unknown) |
| ring info: ringmem, h2d w/r idx, d2h w/r idx | 0x23a644, 0x23a914, 0x23a9bc, 0x23aa64, 0x23aa70 (TCM index mode) |
| max_flowrings | 0x2a |

Common ring memory table at 0x23a644 (16-byte entries): max_item/len_item and base address are the host's values
(e.g. entry 0: 0x0040 x 0x0028 at IOVA 0xbfffe000), and **word 0 (ring id u16 + ring type u8) is zero in all five
entries**: the firmware does not fill it in and Linux does not write it.

Apple's driver does write it. From `FUN_c05974` and the ring constructor (`FUN_c11eec` stores id at +0xb8, type at
+0xba; `FUN_c06b6c`/`c06ccc` write them into the table at +0 as a u16 and a u8): per Linux ring number
(H2D ctrl, H2D rxpost, D2H ctrl, D2H tx, D2H rx) the ids are {0,1,0,1,2} (per-direction ring numbers) and the types are
{0,2,1,4,3}. Hypothesis for the next run: the ROM msgbuf code identifies rings by these fields, so with all five
reading id 0 / type 0 it does not wire up the control submit ring and never consumes it. Patch 0072
(`brcmfmac.h1b_ring_ids=1`) writes Apple's words (type << 16 | id) after max_item/len_item.

## Run 13: R1 (Apple ring id/type words, hold, DEVICE_WAKE high)

Payload `wifi-h1b-modelA-R1-ringids-hold-devwake-20261008T015746Z` (0072, `h1b_ring_ids=1`, `h1b_hold=1`, `device_wake=1`).
The five id/type words were written (log) and read back from TCM through the query interface:
`ringmem 0x23a644: 0x00000000, 0x00020001, 0x00010000, 0x00040001, 0x00030002` in word 0 of the five entries, with the
host's max/len/base words unchanged. Result: the same stall (control query `cmd=262` timed out at 2 s, isr count 0, mailbox
int 0x0, `h2d_mailbox_0` 0x1, d2h scratch 0). With `h1b_hold` the endpoint stayed bound and MSI stayed enabled (address
0xbffff000, data 8). The query interface worked: `core pcie2 0x48 8` read mailbox int 0x00000000 and mask 0x00030300.

Conclusion: the ring id/type hypothesis is refuted. The firmware's silence does not depend on those words.

Query-tool notes: `core cc 0x58 32` was rejected by the safe-register list (0x70 is outside it); the default is now
`core cc 0x58 24`. The `tcm` bound check compares the offset with `ramsize`, but the firmware's addresses are absolute
ARM addresses (shared structure at 0x1dd6c8, ring memory at 0x23a644; RAM starts at 0x180000), so any `tcm` query above
`ramsize` is rejected. The check should be `rambase <= off < rambase + ramsize`. This needs a one-line kernel fix before
`tcm` queries of the live firmware state (ring indices at 0x23a914..0x23aa70, mailbox words 0x23aa7c.., console 0x23deb0)
can be used.

## Run 14: T1 (query interface with snapshot/diff/arm, hold, DEVICE_WAKE high): the firmware is running

Payload `wifi-h1b-modelA-T1-query-hold-devwake-20261008T030909Z` (0073, no ring-id toggle). Same stall (control query timed
out). With `h1b_hold` the queries ran against the live, quiescent device (no crash this time; only safe-list registers read).

- **ARM state (`arm`):** ARM CR4 rev 6 base 0x18002000 up 1; PCIe2 rev 11 base 0x18003000 up 1; ChipCommon rev 47 up 1.
  The PCIe2 core is rev 11, an older core (the 4350's `splitrx` firmware targets `rev <= 13` doorbell behaviour in
  Broadcom's own host driver; Linux's default register table covers it, Apple uses the same 0x140).
- **The firmware is alive:** `snap`, ~9 s wait, `diff` over the whole 768 KiB RAM (0x180000..0x240000) shows only 12 changed
  words, all of them timer-like (e.g. 0x77b1 -> 0x99fb, delta 0x224a, about 8.8 s in ms; 0x78bd -> 0x9b07; a pseudo-random
  word). So the ARM runs its scheduler/timer tick and is neither halted nor trapped (shared trap_addr is 0).
- **Ring state:** host-to-device write indices: control submit 17 (0x11), rxpost 255 (0xff); every read index (device side) 0;
  all device-to-host indices 0. The host wrote its items and rang the doorbell; the firmware consumed nothing.
- **Doorbell:** PCIe2 0x140 reads 1 (pending, never cleared); mailbox int 0x48 = 0, mask 0x4c = 0x30300.
- **Firmware console** (the only text it printed): `RTE (SDIO-MSG_BUF) 7.15.114.157 (r504364) on BCM4350 r5 @ 37.4/240.8/240.8MHz`,
  `allocating a max of 255 rxcplid buffers`, `pciemsgbuf0: Broadcom PCIE MSGBUF driver`, two `reclaim section` lines, `TCAM: 256 used`.
  Nothing after that: no trap, no error text, no "host ready" message.
- A live RAM image (0x180000..0x240000) was assembled to the private run directory (`ram-0x180000-live.bin`, ignored; not
  committed). 97186 of 141632 words of the firmware file equal the live RAM at the same offsets (code and constants); the rest
  are initialised data, heap and runtime state.

Conclusion: the firmware initialised its msgbuf driver and then does nothing with the host's doorbell although its timer
runs. The doorbell interrupt is either masked inside the device (its PCIe2 interrupt mask / the ARM's backplane interrupt
routing) or the ROM's wait condition is not satisfied by something the host has not provided. The ROM (below 0x180000)
holds that logic. A gated ROM read path exists (`unlock rom`, then `rom OFF LEN`, `--allow-rom` on the host tool); it has not
been used. The remaining unprobed registers that would show the device's interrupt masking are PCIe2 0x20 (IntStatus) and
0x24 (IntMask); they are on the safe list but were never read before.

## Run 14 follow-up: PCIe2 interrupt registers and the ROM dump

Same T1 session, held device, safe-list reads only:
- PCIe2 `0x140` (H2D mailbox 0) = 1 (still pending); `0x20` IntStatus = **0x00010000**; `0x24` IntMask = **0x00000000**.
  Mailbox int `0x48` = 0, mask `0x4c` = 0x30300. So the PCIe2 core has a pending event (bit 16) and no interrupt enabled
  in its device-side mask: the doorbell cannot interrupt the ARM. Whether the firmware is supposed to unmask it after
  some trigger (host-ready, deep-sleep state, a capability handshake) is the open question.
- Gated ROM path used for the first time: `unlock rom` reported BAR2 = 0x400000 bytes, RAM base 0x180000. `rom 0x0 16` and
  larger reads worked; the low addresses are real ROM (1024 of 1024 words non-zero, only the first 9 equal the RAM image's vector
  table). The ROM was dumped in 4 KiB reads from 0x0 up to 0xA0000 with no fault; one transient short read at 0x91000 was a
  console-capture glitch. The read that crossed 0xA0000 (past the end of the ROM) killed the USB link and rebooted the iPad
  again, so the ROM/RAM aperture ends at 0xA0000 for this chip and **reads past the mapped ROM reboot the device**. The last 4 KiB
  chunk (0x9f000..0xa0000) is zero padding; every other chunk of the 0xA0000 bytes has data.
- Private artifacts (ignored, not committed): `rom-live.bin` (0xA0000 bytes, base 0), `ram-0x180000-live.bin`,
  `combined-rom-ram.bin` (ROM at 0, live RAM at 0x180000) in the T1 payload directory.
- A sub-agent is mining the live RAM (and, now, the ROM) for the pciedev interrupt-mask logic; its note will be
  `research/2026-10-08-live-ram-device-state-analysis.md`.

## Run 15: M2 (J81 base package + test MAC + hold + DEVICE_WAKE) did not reach Linux

Payload `wifi-h1b-modelA-M2-base-macaddr-hold-devwake-20261008T064755Z`, 13,016,807 bytes (first payload built through
`mkJ81BasePayload`: kernel with 0017, Dropbear closure, charging-policy and tablet tools in the initramfs, private C2 overlay).
The loader finished the upload and the `bootm` handoff as usual; the iPad then restarted straight back to iOS, and no
172.16.42.1 answer appeared in 2 minutes. No evidence from the device (no Linux log), so the cause is not known.

Candidates, not yet separated:
- **Payload size.** 13.02 MB is the largest payload tried. Booted payloads so far: 10.75-11.12 MB (all Wi-Fi runs), the tablet payload
  12.71 MB (2026-10-05). The earliest m1n1 rounds used 12.58-12.59 MB. The public base of this build is 12.69 MB (just under the
  tablet payload); M2 adds the private overlay (+0.33 MB). No size limit is documented for the Hoolock/m1n1 route.
- **Something in the new base content** (0017 in the H1B kernel, the Dropbear overlay and hook) causing an early reset.
- A one-off failure of the handoff.
To separate them: run the public base payload with no private overlay (12.69 MB); if it boots, the base content is fine and the
size/overlay is the issue. Size reduction is available: the kernel accepts xz/zstd initramfs (CONFIG_RD_XZ/RD_ZSTD=y); xz would
shrink the initramfs from 3.2 MB to about 1.8 MB, and an xz kernel from 8.2 MB to about 5.9 MB if m1n1 accepts it.

## Run 16: D1 (J81 base, deferred Wi-Fi start at 60 s, test MAC, hold, DEVICE_WAKE high): the reset happens inside the probe

Runs with the M1 (no base package) and M2 (base package) payloads, both with the test MAC and no deferral, restarted the iPad to iOS
within seconds of boot, before the USB network (about 12-20 s) came up, so no log existed. D1 (payload `wifi-h1b-modelA-D1-defer60-macaddr-hold-devwake-20261008T075723Z`, 13.0 MB,
`h1b_defer_s=60`) booted with the full J81 base package: the iPad answered at 20 s, telnet worked, the polled kernel log shows
`brcmfmac PCIe registration deferred by 60 s`, then at 62.44 s `deferred brcmfmac PCIe registration now`, the chip probe
(BCM4350/5, ARM CR4 rev 6, PCIe2 rev 11, RAM base 0x180000 size 0xc0000, firmware request `brcmfmac4350c2-pcie`) and, at 62.546 s, the
second `brcmf_chip_get_raminfo` of `brcmf_pcie_setup`; then the link was lost.

Findings: (1) the J81 base payload (13 MB) boots and the base package works as a boot path, which clears size as the cause of the earlier resets.
(2) The reset happens within about 0.3-0.5 s of the start of `brcmf_pcie_setup` (firmware download, ARM start, firmware init), in the
window where T1 (no MAC) logged firmware download and start at +0.01 s and the firmware's console at +0.07 s. The 0.3 s polling interval
hides the last lines. With the test MAC in the NVRAM the machine resets there; without it (T1) it did not.
A power or brown-out reset when the Wi-Fi core attaches (radio/PHY power-up on an unconfigured PMIC rail), or a bus fault, are both
possible; a kernel panic message is not visible. `boot/h1b_stream.py` now follows `/proc/kmsg` in real time (no polling lag) to catch the last
lines; the same D1 payload can be rerun with it.
