# J81 Wi-Fi H1B evidence matrix

Date: 2026-10-07. Software-only review of the pinned Hoolock `brcmfmac` PCIe
path and the J81 MSI/DART evidence. This defines the minimum observations for
the first private-firmware transport run; it does not build or access hardware.

## Ordering established by the driver

The endpoint path reaches MSI only after these earlier gates:

1. PCI memory enable, bus mastering and BAR mapping;
2. firmware and NVRAM download;
3. DART-backed common-ring and scratch-buffer allocation/programming;
4. MSI capability configuration and threaded IRQ registration;
5. preinit host-ready notification and the first control request.

Therefore a failure before step 4 cannot be called an MSI-delivery failure.

## H1B event

Use the first preinit control completion (normally the `cur_etheraddr` query)
as the smallest production-path event. It must be correlated across:

- the control request being submitted;
- a D2H control-ring completion or corresponding mailbox state;
- the endpoint MSI capability still containing address `0xbffff000`, data `8`;
- Linux receiving the initial port-1 MSI on slot 8 / AIC line 232; and
- no DART fault, port `MSI_ERR`/`MSI_BAD_DATA`, or firmware-halt indication.

The pinned ISR first reads the endpoint mailbox interrupt register, writes back
the observed status, and only then triggers D2H ring processing. A D2H completion
without the IRQ therefore remains distinguishable from a missing firmware
completion.

## Classification

| Observation | Classification | Action |
|---|---|---|
| Firmware file/NVRAM lookup or download fails | Asset/loader gate | Fix private asset packaging; do not change DMA/MSI. |
| Firmware starts, then DART fault or ring/scratch setup fails | DMA-model gate | Compare Apple-rebase Model A with raw Model B; do not call MSI broken. |
| Control request remains pending; no D2H ring update and no MSI | Firmware/DMA or endpoint-start failure | Inspect firmware console, mailbox state and DART faults. |
| D2H ring completion appears, but no AIC 232/slot-8 event | MSI/fabric delivery failure | Preserve endpoint capability and mailbox evidence; stop before RF use. |
| IRQ arrives on the wrong AIC/vector | MSI domain/vector mapping failure | Stop; do not broaden vector allocation. |
| AIC 232 arrives and D2H completion is consumed cleanly | H1B MSI delivery pass | Proceed only to interface creation, still no scan/association. |
| Port `MSI_ERR`/`MSI_BAD_DATA` or firmware halt | Controller/fabric or firmware failure | Keep as a separate failure class; do not write `+0x168`. |

## Required run record

Record the exact payload hash and private asset names, then capture boot time,
firmware-request result, DART faults, MSI capability readback
(`+0x58`, `+0x5c`, `+0x60`, `+0x64`), AIC/IRQ event, mailbox interrupt status, D2H completion, and
port-event status. Keep raw logs and firmware/NVRAM outside Git.

This matrix leaves `0060` out of the experiment. The first candidate remains
Model A (`0063` + `0064`); Model B is only a controlled follow-up if Model A
fails at the DMA gate.
