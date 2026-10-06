# BCM4350 OTP shadow capture diagnostic (plan phase 1b), built offline only

Date: 2026-10-06. Patch `0062-pcie-apple-t7000-bcm-shadow-capture.patch` on top of the `0061`
metadata probe (see `2026-10-06-bcm4350-metadata-probe.md`, whose iPad observation selected the
ChipCommon path). **Test kernels only. Not run on hardware. The captured bytes are private
calibration/NVM data and must never be committed.** Running it is the standing-rule
"BCM4350 OTP/NVRAM access" decision and needs the user's explicit go-ahead for each run.

## Design

`CONFIG_PCIE_APPLE_T7000_BCM_PROBE_SHADOW` (default n, needs the probe and `DEBUG_FS`). After the
probe's register stage (window already at ChipCommon) it captures the shadow only when all hold:

- mapping path is `chipcommon` (known chip, ChipCommon core rev 44..48/50/51, 40 nm wrapper);
- OTP present **and** selected, SPROM absent (both published predicates agree), so **no selector
  write is ever needed or made** (otherwise it refuses with that reason);
- OTP size encoding nonzero.

Span: `(encoding + 1) * 1024 / 16` 16-bit words (40 nm formula), with a hard cap of 512 words (the
1 KiB ChipCommon window). On the observed J81 values (encoding 5) that is 384 words, 768 bytes.
Reads are 16-bit, contiguous, from ChipCommon `+0x800`. The bytes are copied to a heap buffer
exposed as a root-only (mode 0400) debugfs blob `t7000-bcm-otp-shadow`; the log gets only the word
and byte counts, the count of all-ones and all-zero words and `crc32_le(~0, data)` (equals
`zlib.crc32(data) ^ 0xffffffff`). Nothing else is written; the BAR0 window is restored as in `0061`.
If allocation or debugfs creation fails the capture is dropped (buffer freed) and the probe
continues; the device is left as before.

Retrieval (when approved): over the existing telnet shell, `base64` the blob to a file under the
ignored `artifacts/live/`, verify the CRC from the log, keep it private. The Apple record offset
inside the shadow is **not** assumed (do not use `0x8c0` or `0x840` from other chips).

## Offline evidence

- `kernel/test_bcm_shadow_patch.py` (registered in `tools/check_offline.py`): text contract
  (no writes, no print of data, 0400 file, cap present, exactly one 16-bit read site); zero-fuzz
  apply of `0061` then `0062`; with the option off the trace equals the `0061` golden; with it on
  the real driver runs against the fake BCM4350 in 23 scenarios (the 14 probe ones plus J81-like
  enc 5 = 384 words, enc 7 = 512, enc 0, SPROM present, OTP not selected, GCI, kmalloc failure,
  debugfs failure, a device returning all ones). Invariants: reads are exactly the derived span,
  contiguous from `0x800`, only in the ChipCommon window, only when allowed; no write except the
  window register, restored on every exit; buffers balanced (freed unless kept by debugfs); the
  published blob has size `2*words` and the expected CRC; no data word appears in any log line
  in hex or decimal. 721-line golden `golden-shadow.trace`.
- Nine deliberate bugs are caught (SPROM check, OTP-selected check, GCI path, one word too many,
  leak when debugfs fails, data word logged, wrong start offset, world-readable file, wrong
  units); the 512-word cap itself is a defence in depth that the 3-bit size field cannot exceed.
- Harness finding: the first run exposed a stub that evaluated `debugfs_create_blob()` twice; the
  driver now assigns the result first and the stub is a function like the kernel's.
- Verifier: `boot/verify_pcie_j81_reg_on_payload.py DIR --bcm-shadow` requires the shadow strings;
  `--bcm-probe` rejects them, so the shadow code cannot ride in the probe-only payload.

## Run (not done)

Payload `m1n1-hoolock-pcie-j81-bcm-shadow`: same recipe as the other test payloads; writes the
usual PMU byte (`0x0403`) plus, as in the probe, the BAR0 window register (restored) and the
memory-decode enable (undone); reads 768 bytes of OTP shadow into kernel memory and debugfs.

## Build result (2026-10-06)

`m1n1-hoolock-pcie-j81-bcm-shadow` builds cleanly (first attempt):
`/nix/store/xmdq4f6fcyfvwmcnd966p4yafzqc1962-ipad-air2-m1n1-hoolock-pcie-j81-bcm-shadow`,
`m1n1-linux.bin` SHA-256 `09d32ad00056ee879f96b3453bf850096a65c9f39cb54434e08691fd9f829324`.
`--bcm-shadow` passes; `--bcm-probe` rejects it (shadow code present). `result` points at it.
**Not booted.**
