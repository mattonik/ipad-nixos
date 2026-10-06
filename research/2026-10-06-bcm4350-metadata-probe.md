# BCM4350 metadata observation probe (plan phase 1a), built and verified offline

Date: 2026-10-06. Implements phase 1a of `docs/plans/2026-10-06-j81-wifi-dma-msi-path.md`.
Patch `0061-pcie-apple-t7000-bcm-probe.patch` (test kernels only). **Nothing was booted; no
device access happened.** The separate bounded shadow-capture diagnostic (phase 1b) is not
written: it must wait for the iPad observation to select a supported mapping path.

## What the probe does

A built-in PCI driver for `14e4:43a3` (`CONFIG_PCIE_APPLE_T7000_BCM_PROBE`, depends on the host
driver being built in; do not combine with the MSI self-test, same device). At boot it:

1. saves the BAR0 window register (PCI config `0x80`, the mechanism brcmfmac chip attach uses);
2. enables memory decode only (`pci_enable_device_mem`; never bus mastering) and maps one 4 KiB
   BAR0 window;
3. selects ChipCommon (`0x18000000`) and reads `chipid` (chip `0x4350`, chip revision, package)
   and `eromptr`; any other chip stops here;
4. selects the EROM page named by `eromptr` (must lie in the 16 MiB enumeration space), scans at
   most 8 descriptor words for the first component and reads ChipCommon's own part number
   (must be `0x800`) and **core revision**; core revision below 44 or a different first
   component stops here;
5. only then selects ChipCommon again and reads `capabilities` (`+0x04`), `otplayout` (`+0x1c`)
   and `sromcontrol` (`+0x190`);
6. logs the values, the OTP size / wrapper-type / SROM present, size, OTPSEL, OTP-present fields,
   **both** published predicates (Android `otpsel && otp_present` and the newer
   `otp_present && !srom_present`, neither chosen) and a mapping verdict:
   `chipcommon` (core rev 44..48, 50, 51), `gci` (rev >= 49 except 51; needs its own review) or
   `STOP` with the reason (unknown chip, first component not ChipCommon, rev < 44, OTP wrapper
   not the documented 40 nm type);
7. on **every** exit restores the BAR0 window register, reads it back and logs
   `BAR0 window restore PASS|FAIL`, then releases the region and disables the device, and
   returns `-ENODEV` so it never stays bound.

It does not: write anything except the BAR0 window register, touch the OTP/SPROM selector or
status/control/program registers, read the `sromotp` shadow (`ChipCommon +0x800..`), load
firmware, use DMA, enable bus mastering or MSI, or involve brcmfmac.

## Offline evidence

- Contract test (`kernel/test_bcm_probe_patch.py`, registered in `tools/check_offline.py` via
  `--pcie-j81-selftest-source`): forbidden constructs absent (writes, selectors, shadow, DMA,
  IRQ, brcmf...), exactly two config writes in the source (select and restore), restore on the
  single exit label.
- Host harness (`kernel/bcm_probe_trace/`): the real driver compiled against a fake BCM4350
  with a PCI config window register, a ChipCommon/EROM backplane model and failure injection;
  `iowrite*`, `pci_set_master`, firmware and DMA symbols deliberately do not exist, so using
  them cannot compile. 14 scenarios (ok rev 48 / 49 / 51, rev 43, chip 4354, all-ones chip id,
  window rejected, `eromptr` out of range, first component not ChipCommon, no component,
  wrapper not 40 nm, non-default initial window, enable failure, region failure). Invariants on
  all: always declines the device, only config offset `0x80` accessed, window restored to its
  initial value, no read at or above `0x800` in ChipCommon, enable/disable and region
  request/release balanced, last window write equals the saved value; unknown chip, revision
  or EROM reads no OTP-related register. A 352-line golden trace pins the access sequence.
- Eight deliberate bugs (restore dropped, rev check dropped, shadow read added, unknown chip
  continues, wrong restore value, window readback not verified, device not disabled, region not
  released) are all caught; a write helper or `pci_set_master` fails to compile.
- Payload verifier mode `boot/verify_pcie_j81_reg_on_payload.py DIR --bcm-probe`: the probe strings
  present, **no `brcmfmac` anywhere in the kernel**, and other `--msi*` modes reject the probe.

## Known limits

- Reading ChipCommon metadata before firmware is what brcmfmac's own chip attach does; whether
  J81's BCM4350 answers these reads before firmware (clocks/backplane up after `REG_ON`) is
  exactly what the iPad observation will show. An all-ones answer stops cleanly.
- The ChipCommon core revision comes from the first EROM component descriptor (as in
  brcmfmac); the `chiprev` in `chipid` is the silicon revision, a different field.
- The verdict only says which published path the observed values would select; it does not
  validate that path on this module. Do not infer shadow offsets from BCM4355/4364.

## Hardware run (not done; needs the user's separate go-ahead)

Same recipe as the other test payloads (`m1n1-hoolock-pcie-j81-bcm-probe`); it writes the usual
one PMU byte (`0x0403`) at boot and, in addition, the BAR0 window register (restored) and the
device's memory-decode enable (undone). Expect the `t7000-bcm-probe:` log lines above.

## Build result (2026-10-06)

`m1n1-hoolock-pcie-j81-bcm-probe` builds cleanly (first attempt, no builder disk problem):
store path `/nix/store/3f7d8in121qpwibfs5s6wxfddpm1cbad-ipad-air2-m1n1-hoolock-pcie-j81-bcm-probe`,
`m1n1-linux.bin` SHA-256 `4eff68d7b33d18f02fe910d4cecb89384dd96e2a688f74d5b23ffbe695ae3ccf`.
`--bcm-probe` verifier passes (probe strings present, no `brcmfmac`); `--msi` and
`--msi-selftest` correctly reject this payload. `result` points at it. Not booted.
