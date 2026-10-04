# Offline touchscreen capture comparison

`boot/analyze_touch_capture.py` gives the next native-boot capture a bounded,
repeatable first inspection. It reads local files only. It cannot capture,
replay, upload firmware, configure SPI, or access hardware. No J81 capture was
available during development; all validation uses synthetic transactions.

The profile derives from the exact [openiBoot source at
866562fdb1cfd019bcd77885c80fbf0af65d5c15](https://github.com/iDroid-Project/openiBoot/blob/866562fdb1cfd019bcd77885c80fbf0af65d5c15/plat-s5l8900/multitouch-z2.c),
reviewed in [the ACK/calibration comparison](j81-z2-legacy-ack-calibration.md).
It describes S5L8900 code, not a proven J81 protocol. The existing native
reference harness verifies that source's hash and actual builder/ACK behavior.

## Normalization contract

Each input line is a JSON object with exactly `tx` and `rx`. Each line must
represent one **complete chip-select interval**, in chronological order, with
byte values normalized to the reference's transfer-buffer ordering. Hex text
allows spaces and upper/lower case. `rx: null` means RX was not captured.
An observed RX must have exactly the TX byte count; never invent zero bytes
to replace missing observations. Blank lines and additional keys are rejected.

These are synthetic examples, not a device transaction recipe:

```json
{"tx":"1a a1","rx":"4b c1"}
{"tx":"18e1 3001 0001 56781234 0115 02010403 000a0000","rx":null}
```

The second example corresponds to address `0x12345678` and synthetic source
data `01 02 03 04` passed through the legacy builder. It is not a real
calibration packet. Packet content is never included in the report.

Keep the original capture, exporter, channel assignment, sampling settings,
SPI mode, bits per word, bit order, timestamps, byte-normalization procedure,
and evidence of chip-select continuity in the private session bundle. The
JSONL format deliberately has no timing/channel fields: those must not be
mistaken for validated facts. Do not concatenate multiple chip-select
intervals to make a candidate packet fit. This release has no vendor CSV
importer, waveform decoder, automatic byte swapping, timing analysis or IRQ
correlation; an adapter needs a real export sample before its format can be
validated.

## What the report establishes

| Observation | Report | Limit |
| --- | --- | --- |
| Exact two-byte `1a a1` TX | Whether observed RX is exactly `4b c1`; null when unobserved | Not proof of J81 upload success or association with the previous transfer |
| Exact eight-byte legacy query | Long-response query category | Response value and semantics remain private/unknown |
| `18 e1 30 01` prefix | Candidate legacy calibration layout | Prefix is not device identity or proof of calibration |
| Candidate with high count byte zero, 1–252 low count words | Exact size and header/data byte-sum checks | Only the legacy caller's 4–1008-byte data domain is recognized |
| Other `18 e1` transfer | Opaque prefixed transfer | The 59,288-byte J81 firmware asset is not reconstructed or parsed |
| Two captures | Per-index TX/RX equality and reference summary | No resynchronization after an inserted, dropped or split transaction |

The header sum covers the six count/address bytes. The data sum covers the
advertised data bytes, and the stored sum is low 16-bit word first, big-endian
within each word. **Byte sums cannot prove payload ordering**: swapping two
payload bytes preserves the checksum. A regression test demonstrates this.
The comparator detects the byte difference but cannot say which ordering is
correct. Likewise, a valid checksum cannot identify original calibration
length versus padding or validate the destination address.

## Usage and privacy

Store real inputs/reports under the existing ignored `artifacts/live/` tree
or another private directory. The tool does not create or modify files:

```sh
umask 077
python3 boot/analyze_touch_capture.py artifacts/live/touch/native.jsonl \
  > artifacts/live/touch/native-summary.json
python3 boot/analyze_touch_capture.py artifacts/live/touch/second.jsonl \
  --compare artifacts/live/touch/native.jsonl \
  > artifacts/live/touch/comparison.json
```

Output includes transaction indices, lengths, categories, boolean checks and
byte-equality results. It omits payloads, destinations, computed checksum
values, unknown response values, input paths and asset hashes. Parse errors
identify only the record number; filesystem errors do not echo local paths.
Reports remain private by default: protocol metadata can still distinguish
captures and must be reviewed before publication. Input limits are 16 MiB,
10,000 records, 262,144 bytes per JSON line and 65,536 bytes per transfer.

## Validation and next work

Run `python3 boot/test_analyze_touch_capture.py` or the standard
`python3 tools/check_offline.py`. Thirteen synthetic tests cover the golden
legacy packet, all 252 caller sizes, malformed/truncated/extended packets,
unsupported counts, checksum corruption, checksum/order ambiguity, ACK byte
direction, missing RX, opaque firmware-size input, schema and size limits,
private error handling, and positional comparison.

The default offline suite now contains 15 passing host scripts; seven checks
remain optional for pinned public sources or laptop build artifacts. This
does not validate a Nix build, SPI electrical interpretation or a touchscreen.

Next useful evidence is a matching J81 native-boot capture with complete
chip-select boundaries and paired TX/RX. It can decide whether the candidate
ACK exists and whether any calibration transfer fits this legacy profile.
Negative results are equally useful: leave such records opaque and use their
private bytes plus the matching Apple provider to derive a new profile.
Do not adjust the existing board resources or power sequence from a match.
