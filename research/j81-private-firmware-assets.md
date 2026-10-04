# J81 private firmware assets: recovery and integration gates

Date: 2026-09-26

## Scope and result

This is a read-only audit of the matching iPad5,3 iOS 8.1 (`12B410`)
filesystem, the private J81 ADT capture, the pinned Hoolock kernel, and public
Asahi Linux extraction code. No payload was built, no device was accessed,
and no firmware was uploaded. Apple binaries, firmware, NVRAM and per-device
calibration remain outside Git under the ignored `firmware/` or private
scratch directories.

The local restore filesystem contains everything needed to prepare the touch
firmware parser and the Wi-Fi firmware package. It does **not** contain a
standalone Bluetooth HCD patch. Wi-Fi still needs the PCI endpoint's actual
chip revision and OTP module tuple before choosing files. Touch still needs a
driver adaptation for Apple's preconstructed N1/Z2 packet. Bluetooth firmware
is downstream of the unresolved radio-power condition and the first controller
version response.

Labels used below:

- **E — evidence:** directly observed in the named artifact or source.
- **I — inference:** supported conclusion which still needs a runtime check.
- **U — unknown:** information which must not be guessed.

## Reproducible artifact identity

The source filesystem was mounted read-only. Hashes permit later comparison
without publishing the files:

| Private/local artifact | Size | SHA-256 | Use |
| --- | ---: | --- | --- |
| Decrypted `058-01629-167.dmg` filesystem | 2,123,313,195 | `b187f71f38d53e227cfbd2bacb3bb76b55c19f5c7285e913b2154e467ad965bb` | Exact iPad5,3 `12B410` filesystem used for this audit. |
| `usr/share/firmware/multitouch/J81.mtprops` | 83,479 | `4feb5081f071760d37b7cf8802b729f6bd36f48eb8a7890222c21ea2b1e5d1dc` | Touch property list and constructed firmware. |
| `usr/libexec/wifiFirmwareLoader` | local binary | `1df653a906de960b112b6994e7b690797cd865f7655fc624e7141e70013fa470` | Apple Wi-Fi selection/upload implementation. |
| `usr/sbin/BlueTool` | local binary | `167d72d19b0af185f5b6bdd9eb22184ff1dae033844eac940964f601ef9fa9db` | Bluetooth identity and patch-name table. |
| `usr/sbin/BTServer` | local binary | `dac42b6fcd1ddc14b616f4ff2e29568c7882c4bf3a54c78e09e06415593640cc` | Production UART-open policy. |

The private J81 ADT is separately identified in the touch and Bluetooth
research notes. It contains radio addresses and calibration values, so it
must remain ignored. This note records only non-unique platform selectors.

## Wi-Fi: recoverable now, selection pending

### Exact source assets

**E:** The filesystem has both of these BCM4350 directories:

```text
usr/share/firmware/wifi/C-4350__s-C2/
usr/share/firmware/wifi/C-4350__s-C4/
```

Each contains a `rieslinga` firmware, regulatory blob and transmit-power-cap
blob. The live J81 ADT says `module-instance = rieslinga`, so the parallel
`rieslingb` assets are not candidates for this board.

| Apple source file | Size | SHA-256 |
| --- | ---: | --- |
| `C-4350__s-C2/rieslinga.trx` | 566,531 | `e42b32ab33fcadfaa34414a8ea2c6f90f7931c9a194dad207095275fe3493177` |
| `C-4350__s-C2/rieslinga.clmb` | 9,001 | `f1a77b5d933be97f472530c10c9c8d3ae204e8977c32275a113798c00cb2fa66` |
| `C-4350__s-C2/rieslinga.txcb` | 316 | `9d270addd113628f9d30fe89a7cbd27ce127503343b5e7bb1ba7b1072cd1722a` |
| `C-4350__s-C4/rieslinga.trx` | 566,387 | `8aa9c0ce91af27684ccc2427fc81eb8bcd008392cb0534771a6464ccd2d38391` |
| `C-4350__s-C4/rieslinga.clmb` | 9,001 | `f019088130abc0773fd8fbef143da483f7650448c2346a8e934ad03e0439d883` |
| `C-4350__s-C4/rieslinga.txcb` | 316 | `da69bc267fe59ab4623f6f9b9fc8d712feb766562c9d313cb1c0af988375f4e2` |

The `.clmb` and `.txcb` files begin with Broadcom `BLOB` containers. The
`.trx` files are raw firmware images rather than text configuration.

**E:** Board NVRAM is ASCII `key=value` data. The filenames encode platform,
module, vendor and version:

```text
P-rieslinga_M-<CIDR|STEL>_V-<m|u>__m-<version>.txt
```

The C2 directory contains these exact version sets:

| Module/vendor tuple | Versions present |
| --- | --- |
| `CIDR/m` | `1.2`, `1.3`, `1.8`, `1.9`, `2.0`, `2.1`, `2.11`, `2.2`, `2.3`, `2.9` |
| `CIDR/u` | `1.2`, `1.3`, `2.0`, `2.1`, `2.5` |
| `STEL/m` | `3.8`, `3.9`, `4.0`, `4.1`, `4.11`, `4.2`, `4.3`, `4.6`, `4.7`, `4.9` |
| `STEL/u` | `2.10`, `2.11`, `3.0`, `3.1`, `3.4`, `3.5` |

The C4 `rieslinga` set has exactly
`P-rieslinga_M-CIDR_V-m__m-2.13.txt` and
`P-rieslinga_M-CIDR_V-u__m-2.9.txt`. Several versioned names have identical
content, but that does not authorize choosing a tuple by hash alone.

### Linux names and one old-platform gap

**E:** Asahi's public
[`WiFiFWCollection`](https://github.com/AsahiLinux/asahi-installer/blob/main/asahi_firmware/wifi.py)
defines the raw-to-Linux extension mapping:

| Apple extension | Linux extension |
| --- | --- |
| `.trx` | `.bin` |
| `.txt` | `.txt` |
| `.clmb` | `.clm_blob` |
| `.txcb` | `.txcap_blob` |

It copies binary data unchanged and normalizes only whitespace around NVRAM
keys. For example, its canonical C2 platform outputs are:

```text
brcm/brcmfmac4350c2-pcie.apple,rieslinga.bin
brcm/brcmfmac4350c2-pcie.apple,rieslinga.clm_blob
brcm/brcmfmac4350c2-pcie.apple,rieslinga.txcap_blob
brcm/brcmfmac4350c2-pcie.apple,rieslinga-CIDR-m-2.11.txt
```

The last filename is an example of the filename transformation, not the
selected J81 NVRAM.

**E:** The pinned Hoolock `brcmfmac/pcie.c` maps BCM4350 chip revisions 0--7
to base `brcmfmac4350c2-pcie` and revisions 8--31 to base
`brcmfmac4350-pcie`. Apple's `C2` and `C4` source directories must not be
blindly equated to those numeric ranges. Record the endpoint chip revision
and Apple's selected stepping before installing either set under the driver's
requested basename.

**E:** Current `brcmfmac` can derive Apple board filenames from OTP as
`<board-type>-<module>-<vendor>-<version>`, but its PCIe path enters that
logic only when both `brcm,board-type` and `apple,antenna-sku` are present.
J81 supplies the `rieslinga` platform identity and older individual
calibration properties, but no `wifi-antenna-sku-info` and no single
`wifi-calibration-msf` blob.

**I:** The smallest eventual integration is to set board type
`apple,rieslinga`, report the BCM4350 chip revision plus OTP module/vendor/
version in a diagnostic probe, and let the Apple filename builder use that
tuple without requiring an antenna SKU. Do not invent an antenna SKU or pick
`CIDR`/`STEL`, `m`/`u`, or a version from filenames. The binary, CLM and
TxCap files can fall back to the platform-only suffix; NVRAM must match the
OTP tuple.

**U:** J81's per-device ADT calibration is split across older properties such
as RX, TX and 2.4 GHz frequency-group calibration. Newer m1n1 copies one
`wifi-calibration-msf` property verbatim to `brcm,cal-blob`; that property
does not exist on J81. Static Apple-driver work must determine whether the old
fields form a `calload` blob, override NVRAM keys, or are optional corrections.
Do not associate or intentionally transmit until that is resolved.

### Wi-Fi evidence gate

1. Enumerate the PCI endpoint without `brcmfmac` or firmware.
2. Record PCI ID, BCM chip revision and OTP module/vendor/version. Keep any
   unique radio address private.
3. Resolve whether Apple chooses `C2` or `C4` for that tuple by tracing
   `wifiFirmwareLoader -f` selection statically or by matching its selector
   logic. Do not infer it from directory names.
4. Convert only the selected `rieslinga` quartet with the mapping above and
   stage it under ignored `firmware/`.
5. First test firmware load and interface creation without association.
   Treat a missing calibration path as a stop condition for RF testing.

## Touch: exact payload recovered, direct upload unsupported

**E:** `J81.mtprops` is an XML property list with one personality,
`C1F15,2`. It contains:

- `Constructed Firmware`: 59,288 bytes;
- `Constructed Firmware Version`: `0x0381.bin`;
- `PreconstructedBootloadPacketType`: `Z2`;
- `ResetInterval`: `432000`.

The extracted constructed payload has SHA-256
`9948ce32f7ec68507d58a01392fc2ac8add5bfeace4c88310da2107b1e2d54e2`.
It begins with little-endian marker `0xe118`, is four-byte aligned, and has no
`Z2FW` header. The matching Apple driver sends it as a preconstructed packet;
upstream Linux `apple_z2` expects a different version-1 container.

A safe host-only extraction from an already mounted, authorized filesystem is:

```sh
mkdir -p firmware/j81-12B410/touch
python3 - firmware/j81-12B410/touch/C1F15,2.constructed.bin <<'PY'
import plistlib
import sys

source = "/path/to/read-only-root/usr/share/firmware/multitouch/J81.mtprops"
with open(source, "rb") as stream:
    props = plistlib.load(stream)
payload = props["C1F15,2"]["Constructed Firmware"]
assert len(payload) == 59288
with open(sys.argv[1], "xb") as stream:
    stream.write(payload)
PY
shasum -a 256 firmware/j81-12B410/touch/C1F15,2.constructed.bin
git check-ignore -v firmware/j81-12B410/touch/C1F15,2.constructed.bin
```

This output is suitable for a parser test fixture kept outside Git. It must
not be wrapped in a guessed `Z2FW` header or sent to the iPad. A bounded
identity/envelope inspector is now implemented below. The remaining parser
work is the internal `0xe118` packet layout and Apple acknowledgement path
described in
[`j81-touchscreen-bringup-offline.md`](j81-touchscreen-bringup-offline.md).
The private ADT touch-calibration blob is a separate input and must not be
published.

### Host-only identity/envelope inspector, 2026-10-04

[`boot/inspect_j81_touch.py`](../boot/inspect_j81_touch.py) replaces the manual
extraction snippet with a bounded, standard-library-only tool:

```sh
python3 boot/inspect_j81_touch.py \
  /path/to/read-only-root/usr/share/firmware/multitouch/J81.mtprops \
  --output firmware/j81-12B410/touch/C1F15,2.constructed.bin --json

python3 boot/inspect_j81_touch.py \
  firmware/j81-12B410/touch/C1F15,2.constructed.bin \
  --format constructed --json

python3 boot/test_inspect_j81_touch.py
```

The tool accepts XML or binary plists, requires the single `C1F15,2`
personality and the recorded Z2/version/reset metadata, then checks the
59,288-byte length, little-endian marker, four-byte alignment and the exact
recorded payload SHA-256. Reads are capped at 1 MiB. It emits only whitelisted
metadata and hashes, never firmware bytes or arbitrary plist properties.
Extraction occurs only after validation, uses exclusive creation with mode
`0600`, and refuses an output inside the repository unless Git ignores it.
Resolved symlink destinations are subject to the same policy. Existing files
are never overwritten.

The optional `--expected-sha256` permits an explicitly supplied out-of-tree
fixture identity; the report distinguishes that from the recorded 12B410
asset. It does not relax the J81 metadata, length or envelope checks. A hash
override is not evidence that another firmware revision is supported.

**Validation:** 15 offline unittest methods pass, including malformed and
truncated plists, wrong personalities/metadata, packet truncation/corruption,
source-size bounds, default-hash rejection of synthetic firmware, XML/binary
equivalence, private-file permissions, overwrite refusal and real Git-ignore
checks including a symlink escape. All fixture bytes are generated synthetic
data; the actual Apple asset is absent from this environment and was not run
through the inspector. No kernel or payload changed, and no device was used.

**Remaining gate:** this verifies asset identity and the established outer
envelope only. Bytes after the marker remain opaque: the notes do not yet
record the internal length/address/checksum layout or the boot ACK success
predicate. Every successful report therefore has `transport_ready: false`.
Those fields must be recovered from the matching Apple disassembly before a
wire parser or Linux upload adaptation is implemented. This tool does not
construct `Z2FW`, generate SPI messages, or enable a touchscreen DT child.

## Bluetooth: metadata recovered, patch bytes absent

**E:** A complete filename search of the mounted `12B410` filesystem found no
standalone `.hcd` patch. `BlueTool` contains the selection table and resolves
the J81 record to the candidate
`BCM4350C2_12.2.253.457_Riesling_OS_MUR_STC_20140916.hcd`; the private
20-byte product selector is intentionally omitted. `BTServer` establishes
the stock 3 Mbaud open policy described in
[`j81-bluetooth-bringup.md`](j81-bluetooth-bringup.md).

The Wi-Fi `.trx` is not Bluetooth patchram and must never be renamed to satisfy
an HCD lookup. If the exact HCD is later recovered from another matching,
lawfully accessible Apple artifact, keep it private, hash it, and validate it
as a complete stream of little-endian HCI command headers (`opcode`, one-byte
payload length, payload). Reject truncation and trailing bytes. This mirrors
the pinned kernel's `btbcm_patchram()` parser without sending commands.

Do not bundle an HCD until a powered controller returns its own HCI version
and subversion. Firmware is not the current Bluetooth blocker: J81 still has
zero RX before patch lookup because the radio-enable write does not persist.

## Safe private workflow

Use only a local IPSW or decrypted filesystem the operator is authorized to
inspect. This note deliberately provides no decryption key lookup or
access-control bypass. Mount an existing filesystem image read-only, copy the
minimum files into the ignored tree, record hashes, and detach it when done:

```sh
hdiutil attach -readonly -nobrowse /path/to/authorized.decrypted.dmg
mkdir -p firmware/j81-12B410/raw
# Copy only the selected files after the gates above are satisfied.
shasum -a 256 firmware/j81-12B410/raw/* > firmware/j81-12B410/SHA256SUMS
git check-ignore -v firmware/j81-12B410/raw firmware/j81-12B410/SHA256SUMS
git status --short
hdiutil detach /dev/diskN
```

Keep `SHA256SUMS` private too: it is a local inventory of proprietary files.
Before any future commit, `git status --short --ignored` must show every
extracted artifact under the ignored `firmware/` tree and no raw ADT, radio
address or calibration file staged.

## Evidence-ranked next software work

| Priority | Work | Certainty | Hardware required |
| ---: | --- | --- | --- |
| 1 | Identity/envelope inspector implemented and synthetic-tested; recover internal `0xe118` fields and ACK predicate from matching disassembly next. | High for identity/envelope; wire layout unresolved | No |
| 2 | Trace `wifiFirmwareLoader` path selection far enough to map BCM revision/OTP tuple to C2 or C4 and confirm old calibration handling. | Medium | No |
| 3 | Prepare a minimal `brcmfmac` patch which permits Apple OTP filename construction when antenna SKU is absent; do not enable it yet. | High for filename gap; runtime pending | No |
| 4 | Search matching local restore/OTA artifacts for the exact Bluetooth HCD filename and validate any recovered stream offline. | Medium; bytes absent here | No |
| 5 | Stage the selected Wi-Fi quartet only after PCI enumeration reports chip and OTP identity. | High dependency order | Yes, read-only enumeration first |

## Public source anchors

- Asahi firmware extension/name conversion:
  [`asahi_firmware/wifi.py`](https://github.com/AsahiLinux/asahi-installer/blob/main/asahi_firmware/wifi.py)
- Asahi ADT-to-DT calibration handoff for newer platforms:
  [`m1n1/src/kboot.c`](https://github.com/AsahiLinux/m1n1/blob/main/src/kboot.c)
- Pinned Hoolock source revision and local PCIe plan:
  [`2026-09-13-j81-wifi-pcie.md`](../docs/plans/2026-09-13-j81-wifi-pcie.md)
- Existing touch and Bluetooth evidence:
  [`j81-touchscreen-bringup-offline.md`](j81-touchscreen-bringup-offline.md) and
  [`j81-bluetooth-bringup.md`](j81-bluetooth-bringup.md)
