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

## Hardware result (2026-10-06): 768-byte shadow captured, CRC verified

Payload `m1n1-hoolock-pcie-j81-bcm-shadow` (`m1n1-linux.bin` SHA-256 prefix `09d32ad0...`,
host-side identity only). Boot normal, link and enumeration unchanged, one PMU byte written as
usual. The probe lines are the same as in the metadata run (chip `0x4350`, ChipCommon rev 47,
`chipcommon` path, window restore PASS) plus:

```
t7000-bcm-probe: shadow: captured 384 words (768 bytes) crc32=<matches> allones=0 zero=320; bytes in debugfs ...
```

The blob was read over the telnet shell (`base64` of the root-only debugfs file), the host-side
CRC32 matched the kernel's, and the 768 bytes are stored **only** under the ignored
`artifacts/live/private/` (mode 0600). The values, the CRC and the file hash are deliberately not
recorded in Git: the OTP is per-device calibration/identity data.

Structure only (no values), 16-bit words indexed from ChipCommon `+0x800`:

- 384 words captured, **320 are zero, 64 are non-zero**, none are `0xffff`;
- non-zero runs (word index, inclusive): `0-5`, `16`, `28`, `31-38`, `44-62`, `74-76`, `80-82`,
  `84-85`, `96-97`, `99-116`, and one isolated word at `273` (byte offset `0xa22`);
- so the populated region is the first 117 words (offsets `0x800-0x8e9`), then zeros up to the
  stray word at `0xa22`, then zeros to the end of the captured span.

Observation for the research agent, **not a conclusion**: word index 96 is byte offset `0x8c0`,
the record start other Broadcom chips in the Hoolock reader use, and a non-zero run begins exactly
there (`96-97`, `99-116`). The earlier audit's candidate `0x840` (word 32) falls inside the run
`31-38`. Neither offset is established for BCM4350/J81; decoding the record format, locating the
module/vendor/version tuple and the Apple C2/C4 selection is phase 1b's analysis (private, local,
research-agent work). The span reported by the 40 nm formula (384 words) was readable and
contained no all-ones words, so the formula and the ChipCommon shadow window behaved as the
source audit predicted on this module.

Unrelated, already known log lines were unchanged (`g_multi` `-22`, `retraining failed`,
`of_irq_parse_pci` `-22`).

## Next

1. Local, private analysis of the capture with the existing Apple-record parser contract
   (`research/j81-otp-parser-validation.md`) and the layout facts above: find the system-vendor
   record, the M/V/m tuple and chip revision. Keep outputs under `artifacts/`.
2. Only after a nonempty tuple is proven: firmware/NVRAM selection (`j81-wifi-loader-selection.md`)
   and the DMA-rebase candidate (plan phase 2).
