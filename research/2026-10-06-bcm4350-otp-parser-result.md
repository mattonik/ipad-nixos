# BCM4350 OTP record analysis

Date: 2026-10-06. Software-only analysis of the private 768-byte shadow capture
from the J81 BCM4350 run. The capture remains under ignored `artifacts/live/private/`;
no raw bytes, hashes, or calibration values are committed.

## Result

The pinned Broadcom parser's chip-specific start offset is correct for this module:
the shadow record begins at ChipCommon offset `0x8c0` (byte 192 within the captured
`+0x800` window). Parsing from the start of the shadow would stop on unrelated
prefix data and is therefore incorrect.

At `0x8c0` there is one valid `BRCMF_OTP_SYS_VENDOR` record with the required
four-byte vendor header, NUL-terminated chip and board strings, and a complete
module/vendor/version (M/V/m) tuple. The record ends cleanly; the following bounded
unknown record and zero terminator do not invalidate it under the pinned parser.

This proves that the J81 capture contains a usable Apple-style identity record and
closes the NVM identity gate. The exact tuple is intentionally kept out of Git and
the raw capture remains private.

## Consequence

The coding agent can now select the firmware/NVRAM quartet from the proven tuple and
prepare the next test-only loader path. Do not enable the loader or DMA candidate in
the deployed image yet: the next hardware gate is the first preinit control
completion, followed by endpoint DMA/MSI validation.
