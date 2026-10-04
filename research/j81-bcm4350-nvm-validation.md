# BCM4350 NVM access-path validation, 2026-10-04

This follows the [source audit](j81-bcm4350-otp-source-audit.md) and
[Apple-record parser validation](j81-otp-parser-validation.md). It exercises
public reference code with synthetic host cores. No BCM4350 device, PCI
transaction, power transition, firmware, private capture or Nix build is used.
No reader is enabled in the kernel or payload.

## Exact public sources

The native harness uses StreamUnlimited's public DHD tree at
`953f6d11b48a8178904c831722f231627a53a6ef`:

- [`dhd_pcie.c`](https://github.com/StreamUnlimited/broadcom-bcmdhd-4359/blob/953f6d11b48a8178904c831722f231627a53a6ef/dhd_pcie.c), SHA-256
  `837e468f978ac9b7f670aa335c2b18b03b8c74b28deaad77d30dee33729aa17c`.
- [`include/sbchipc.h`](https://github.com/StreamUnlimited/broadcom-bcmdhd-4359/blob/953f6d11b48a8178904c831722f231627a53a6ef/include/sbchipc.h), SHA-256
  `ae1ea2b9b96531f4dddfd73a2540bfe026082da36ba19aeba17e305e2e89a45e`.
- [`siutils.c`](https://github.com/StreamUnlimited/broadcom-bcmdhd-4359/blob/953f6d11b48a8178904c831722f231627a53a6ef/siutils.c)
  and [`include/siutils.h`](https://github.com/StreamUnlimited/broadcom-bcmdhd-4359/blob/953f6d11b48a8178904c831722f231627a53a6ef/include/siutils.h)
  clarify the current-core API. These helpers were source-reviewed, not
  compiled into this harness.

`kernel/test_bcm4350_nvm_reference.py` verifies both input hashes, extracts
the actual `dhdpcie_cc_nvmshadow()` definition and the relevant header
constants, and compiles them temporarily. Third-party code is not vendored.
Core selection, registers and text output are synthetic interfaces. The
register stub is not a validation of physical offsets or PCI BAR behavior.

## Reproduced behavior

| Synthetic condition | Actual reference behavior | Consequence for a future design |
| --- | --- | --- |
| Core rev 43 or unsupported chip | Returns unsupported after selecting ChipCommon | Cleanup must also cover validation failures |
| `bus->regs == NULL` | Returns not-ready with ChipCommon still selected | Validate access before touching registers/mappings |
| Valid legacy 40 nm encoding 1 through 7 | Reads 128 through 512 words | Units are bits divided by 16; explicit mapping bounds still required |
| SPROM encodings 0, 1, 2 | Reads 512 words for all three | The `sprom_size > 8` comparison causes a 1-Kbit selection to be over-dumped relative to its declared 64 words, and a 4-Kbit selection relative to its declared 256 words |
| Rev 49, 40 nm row encoding 11 | Selects GCI, reads 768 words | ChipCommon's 512-word window cannot be assumed to cover the newer path |
| Rev 51 with the same row encoding, legacy capability encoding 1 | Uses ChipCommon and reads 128 words | Rev 51 is an explicit exception to the newer path |
| GCI unavailable | Returns not-found after ChipCommon selection | Mapping failure requires cleanup |
| Original core instance 1, successful dump | Restores original core ID but instance 0 | Core ID alone does not preserve exact selection |
| Rev 49, non-40 nm wrapper, row encoding 8 | Sanitizers report indexing past the eight-entry 65 nm table | Reject unsupported wrappers/indices before deriving a read span |
| OTP present, no SPROM, OTPSEL clear | Newer reference permits OTP reading | Record the predicate difference from the older Android reader; do not silently equate them |

The instance-loss result is a synthetic counterexample, not evidence that
the BCM4350 diagnostic is called from instance 1 in production. The API
explains the distinction: `si_coreid()` returns the type of the current
core; `si_coreidx()` returns its exact index. `si_setcore()` resolves a type
and unit, whereas `si_setcoreidx()` selects the index. Other functions in
`siutils.c`, such as `si_get_armcoreidx()`, save and restore the index.

Zero size encoding also deserves explicit handling: the 40 nm calculation
would give 1024 bits, but a later absence check rejects a no-SPROM state
with capability encoding zero (or row encoding zero in the newer path).
The header describes capability zero as none. This is an ambiguity to
resolve from real metadata, not justification to enable that encoding.

The sanitizer case intentionally reproduces a fault in the public
reference. A passing harness means the expected behavior was reproduced;
it does not certify that the vendor routine is safe to import. No claim is
made that the synthetic bad state is reachable on J81.

## Power and mapping context cannot be omitted

The dump routine itself contains no explicit OTP-power or radio-power
sequence. It is called through the `cc_nvmshadow` IOVAR. In this source,
`dhd_bus_iovar_op()` conditionally acquires/releases a PCIe power request
when `MULTIBP_ENAB(bus->sih)` is true and the IOVAR does not request bypass.
`cc_nvmshadow` has zero flags. This wrapper is **outside** the native harness.
Its conditional behavior does not establish which power prerequisites J81
needs, and its helpers must not be transplanted as guessed GPIO/PMIC writes.

This distinction matters: extracting an apparently read-only helper drops
its caller's lifecycle assumptions. A future diagnostic must establish that
the radio is powered, PCIe enumerated, the backplane accessible and mapping
operations serialized before reading metadata. Preserve mapping state on
every exit; report restoration failure separately from read failure.

## Comparison with the pinned Linux path

The existing Hoolock
[`pcie.c`](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c)
still has no BCM4350 case. Its existing ChipCommon cases select the core,
read `sromcontrol`, set OTPSEL, then allocate the capture buffer. If that
allocation fails, the early return precedes restoration of `sromcontrol`;
when OTPSEL was previously clear it can therefore remain set. Successful
reads restore that selector but do not themselves save/restore the prior
BAR0 window. This is source analysis of existing other-chip paths, not a
newly demonstrated J81 hardware fault or a patch proposal.

The OTP parser improvements do not address these access-lifecycle concerns.
Nor does the vendor routine establish an Apple record start at `0x8c0` or
`0x840`. A full private shadow capture and proven record boundaries remain
separate prerequisites before selecting firmware/calibration by identity.

## Validation and narrowed handoff

```sh
ASAN_OPTIONS=detect_leaks=0 python3 kernel/test_bcm4350_nvm_reference.py \
  --source /path/to/pinned/dhd_pcie.c \
  --header /path/to/pinned/include/sbchipc.h --sanitize
python3 tools/check_offline.py \
  --dhd-source /path/to/pinned/dhd_pcie.c \
  --dhd-header /path/to/pinned/include/sbchipc.h
```

The runner requires both DHD inputs together. It never fetches sources or
connects to hardware. With all public-source arguments and sanitizers,
19 scripts pass and two built-artifact checks are skipped. Default mode
passes 14 scripts with seven optional skips.

After the existing passive radio-power capture and PCI enumeration gates,
the useful first metadata is the observed chip/revision, discovered core
base/revision, capabilities, layout and SROM control. Keep raw NVM and
device identifiers private. The next implementation should separate pure
span selection from transport access, reject unknown combinations, avoid
selector writes in its initial observation phase, and provide one cleanup
path for exact mapping/selector restoration. This work supplies regression
cases for that design; it does not supply a hardware transaction recipe.
