# J81 Wi-Fi firmware-loader selection and missing-calibration policy

## Result

The pinned loader can accept a request with no NVRAM, CLM or TxCap file.
Consequently, observing successful firmware-request completion is insufficient
proof that J81's calibration was supplied. This is an existing generic PCIe
policy, not a new J81 change. We should record the selected filenames and
nonzero calibration length during a later controlled bring-up.

This audit extends the [private asset inventory](j81-private-firmware-assets.md)
and [BCM4350 access-path research](j81-bcm4350-nvm-validation.md). It does not
select a module/vendor/version, install proprietary firmware, change driver
policy, or remove the existing REG_ON/PCIe/OTP/calibration gates.

## Exact public source

Hoolock Linux commit `6831bc701a6ce059e71e5aaa9488c9195bea6927`:

- [`firmware.c`](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/drivers/net/wireless/broadcom/brcm80211/brcmfmac/firmware.c),
  SHA-256 `f2b6fe570981bf69a81fd5965712f18840df9b97dabcdbd4aa4cf260b4e9760b`.
- [`pcie.c`](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c),
  SHA-256 `2bc4ff2f06eb515b404e08973a39c029ec975155a17a7baaf6f62e76ca181b4c`.

### Selection is per file

`brcmf_fw_request_firmware()` restarts the board list at index zero for each
subsequent item. It does not remember which board suffix supplied the earlier
binary. Its first successful file request wins; exhausting alternatives tries
the canonical basename. A NULL candidate terminates the list, and failure to
allocate an alternative filename also goes directly to the canonical fallback.

For the proposed no-SKU list in inactive patch 0048, the search is:

| Order | Synthetic suffix example |
| --- | --- |
| 1 | `apple,synthetic-M-V-1` |
| 2 | `apple,synthetic-M-V` |
| 3 | `apple,synthetic-M` |
| 4 | `apple,synthetic` |
| 5 | No board suffix: canonical filename |

The suffix goes before the final extension, e.g.
`brcm/brcmfmac4350c2-pcie.apple,synthetic-M-V-1.txt`.
These are synthetic test names, not a proposed J81 identity. Exact chip stepping
and module/vendor/version still need evidence. A leftover generic `.txt` can
therefore satisfy lookup after all intended board files are missing. Avoid
populating generic fallbacks with an arbitrarily chosen calibration file.

The first `.bin` is requested through asynchronous callbacks instead of this
synchronous function. Source inspection finds the same ordered alternatives and
canonical fallback in `brcmf_fw_get_firmwares()` and
`brcmf_fw_request_done_alt_path()`, but the new harness **does not execute the
asynchronous callbacks**. Its `.bin` case exercises the shared filename format
and synchronous required-file behavior only.

### Optional is not validated

`brcmf_pcie_prepare_fw_request()` marks the request items as follows:

| Item | Flag | Missing-file behavior at completion |
| --- | --- | --- |
| `.bin` | Required | `-ENOENT` |
| `.txt` | Optional NVRAM | Tries platform NVRAM sources; can succeed empty |
| `.clm_blob` | Optional binary | Missing data does not fail completion |
| `.txcap_blob` | Optional binary | Missing data does not fail completion |

The NVRAM fallback sources are BCM47xx platform contents and an EFI variable;
these are generic driver paths, not demonstrated sources on J81.
`brcmf_fw_request_nvram_done()` also accepts a NULL result from
`brcmf_fw_nvram_strip()` when NVRAM is optional. The completion wrapper masks
errors for all optional items. This does not imply the later firmware boot,
interface creation or radio operation will succeed.

We deliberately do not globally make NVRAM mandatory: that changes policy for
other supported devices and would require device-specific design and testing.
For J81, evidence collection should distinguish (a) a matching file requested,
(b) nonempty parsed calibration, (c) firmware boot, and (d) a usable radio.
The existing restriction on intentional transmission while old per-device ADT
calibration handling is unresolved still applies.

## Offline validation

`kernel/test_brcmfmac_firmware_loader.py` verifies the exact source hash and
extracts four actual functions into a temporary native C harness. It checks:

- Four extensions and all six lookup outcomes: each of four board candidates,
  canonical success, or total absence.
- Required versus optional warning path; first-NULL list termination; allocation
  failure falling back to canonical; invalid filename/no-board handling.
- Required and optional NVRAM with no source, a simulated NULL parser result,
  and a simulated successful parse; required and optional binary absence.

The NVRAM parser and firmware request APIs are **host stubs**. Tests validate
control flow and completion policy, not real NVRAM parsing, kernel allocation,
firmware compatibility, asynchronous lifecycle, or hardware. The separately
existing `test_brcmfmac_otp_patch.py` validates the PCIe request builder.

```sh
ASAN_OPTIONS=detect_leaks=0 python3 kernel/test_brcmfmac_firmware_loader.py \
  --source /path/to/pinned/brcmfmac/firmware.c --sanitize

ASAN_OPTIONS=detect_leaks=0 python3 tools/check_offline.py \
  --firmware-source /path/to/pinned/brcmfmac/firmware.c --sanitize
```

ASan and UBSan passed. LeakSanitizer is disabled because this hosted environment
cannot enumerate `/proc` tasks for its leak phase. No Nix build or device test
was performed. The optional runner input adds one check; without the public
source supplied, it is explicitly skipped.
