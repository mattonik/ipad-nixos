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
module/vendor/version (M/V/m) tuple. Its chip-parameter string is `s=C2`, so the
Apple stepping is directly proven as **C2**. The record ends cleanly; the following
bounded unknown record and zero terminator do not invalidate it under the pinned
parser.

This proves that the J81 capture contains a usable Apple-style identity record and
closes the NVM identity and C2/C4 stepping gates. The raw capture remains private;
only the non-calibration selector metadata is recorded here.

## Consequence

The exact private selection is now the C2 `rieslinga` firmware/CLM/TxCap set plus
NVRAM `P-rieslinga_M-CIDR_V-u__m-2.1.txt`. The coding agent can stage that quartet
and prepare the next test-only loader path. J81's legacy calibration fields still
need separate mapping; do not treat a successful firmware request as proof that
calibration is complete. Do not enable the loader or DMA candidate in the deployed
image yet: the next hardware gate is the first preinit control completion, followed
by endpoint DMA/MSI validation.
