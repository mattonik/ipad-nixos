# J81 BCM4350 NVM shadow: source evidence, 2026-10-04

This closes part of the source-recovery gate in the
[private firmware audit](j81-private-firmware-assets.md). It does not add a
kernel reader or claim a working radio. No hardware was used.

## Pinned primary implementations

The Android kernel's Broadcom DHD implementation at
`b25668b0a8d7683319d5d8210b417dbb205d1c7f` contains
[`dhdpcie_cc_nvmshadow()`](https://android.googlesource.com/kernel/msm/+/b25668b0a8d7683319d5d8210b417dbb205d1c7f/drivers/net/wireless/bcmdhd/dhd_pcie.c)
and a matching
[`sbchipc.h`](https://android.googlesource.com/kernel/msm/+/b25668b0a8d7683319d5d8210b417dbb205d1c7f/drivers/net/wireless/bcmdhd/include/sbchipc.h).
Unlike the pinned Hoolock reader, this diagnostic explicitly accepts only
BCM4350 and BCM4345, with ChipCommon core revision at least 44.

SHA-256 of decoded Gitiles source:

| File | SHA-256 |
| --- | --- |
| `dhd_pcie.c` | `e33f56d8c54b2fe5508a88f747f474737e6cd9aa7bd9ab05f20f83b45133af6f` |
| `include/sbchipc.h` | `14fd51d84f4e3e9426a15487677d22ad0286b82b5294c5147fb7fe1ad421eb2f` |

A second implementation is available in StreamUnlimited's Broadcom DHD
tree at `953f6d11b48a8178904c831722f231627a53a6ef`:
[`dhd_pcie.c`](https://github.com/StreamUnlimited/broadcom-bcmdhd-4359/blob/953f6d11b48a8178904c831722f231627a53a6ef/dhd_pcie.c)
and
[`sbchipc.h`](https://github.com/StreamUnlimited/broadcom-bcmdhd-4359/blob/953f6d11b48a8178904c831722f231627a53a6ef/include/sbchipc.h).
Its corresponding hashes are
`837e468f978ac9b7f670aa335c2b18b03b8c74b28deaad77d30dee33729aa17c`
and `ae1ea2b9b96531f4dddfd73a2540bfe026082da36ba19aeba17e305e2e89a45e`.
Its reader retains BCM4350 and adds newer chip/core handling. This is a
cross-check of published driver behavior, not a BCM4350 datasheet.

## What is established

Both headers define `chipcregs_t.sromotp[512]` at offset `0x800`.
The older diagnostic describes the shadow as `0x800–0xbff` and reads it as
16-bit words. Its backplane-address comment uses `0x18000800–0x18000bff`.
Those are Broadcom device backplane addresses, **not A8X physical addresses**.
A Linux implementation must discover the core base and use PCI BAR/window
mapping; it must not add these addresses to an iPad device tree as host MMIO.

| ChipCommon item | Core-relative offset / mask | Source interpretation |
| --- | --- | --- |
| `capabilities` | `0x004` | OTP size field below |
| `otplayout` | `0x01c` | Wrapper type; newer implementations also use row size |
| `sromcontrol` | `0x190` | NVM presence and strap selection |
| `sromotp` | `0x800`, 512 16-bit words | 1024-byte ChipCommon shadow window |
| `SRC_PRESENT` | `0x01` | SPROM present |
| `SRC_OTPSEL` | `0x10` | OTP selected |
| `SRC_OTPPRESENT` | `0x20` | OTP present |
| `SRC_SIZE_MASK` | `0x06`, shift 1 | SPROM size encoding |
| `CC_CAP_OTPSIZE` | `0x00380000`, shift 19 | Older OTP size encoding |
| `OTPL_WRAP_TYPE_MASK` | `0x00070000`, shift 16 | Wrapper type 1 means 40 nm |

The older reader computes 40 nm OTP size as `(encoding + 1) * 1024`
**bits**, then divides by 16 to obtain the read count in 16-bit words.
Its alternative 65 nm size table is `{0, 2048, 4096, 8192, 4096, 6144,
512, 1024}` bits and is explicitly described as untested in that path.
Do not apply the 40 nm formula until the wrapper type is observed.

The newer reader uses `otplayout` row-size encoding and a GCI shadow path
when core revision is at least 49, except revision 51. It preserves the
older ChipCommon path for revision 51. Thus BCM4350's name alone does not
select a safe path; its observed ChipCommon revision matters.

## What cannot yet be inferred

The shadow starts at `0x800`; this does **not** establish that Apple's
system-vendor records begin there. Hoolock's implemented BCM4355/BCM4364
readers start at `0x8c0`; copying their record offset or word count into a
BCM4350 case remains unsupported by the evidence above.

The macOS compatibility project AppleBCMWLANCompanion at
`493e08a15bde93aa4a658032976dff66e0fd1d56` documents
[`bcmc-srom-slide`](https://github.com/0xFireWolf/AppleBCMWLANCompanion/blob/493e08a15bde93aa4a658032976dff66e0fd1d56/Documentation/DeviceProperties.md)
as a `UInt32` offset into SPROM, with `0x40` for BCM4350. Its documented
cards are PCI device `14e4:43a3` desktop/laptop modules, not the J81 module.
This is a possible clue about a prefix within the shadow, not proof of a
J81 CIS start. In particular, `0x840` is only arithmetic based on two
different sources; no J81 parser offset is established.

That project also documents injecting BCM4364 chip/user OTP and a default
module instance of `lanai`. Such substitutions cannot establish the real
J81 module/vendor/version or select its calibration. The inspected public
checkout contains documentation and firmware, not the implementation of
the slide mechanism. No firmware from that checkout is copied here.

## Requirements for a future bounded diagnostic

After the earlier radio-power and PCI enumeration gates are satisfied:

1. Record actual BCM chip/revision, discovered ChipCommon core base/revision,
   and the read values of capabilities, layout and SROM control. Keep radio
   serial identifiers and addresses out of public logs.
2. Select a mapping path supported by that core revision. Preserve and
   restore the previous PCI window/core selection on **every** exit.
3. Inspect the already selected NVM shadow first. In the old reader, OTP
   requires both OTPSEL and OTPPRESENT; the newer reader also permits absent
   SPROM plus present OTP. Record this difference rather than silently
   substituting one predicate. If the correct shadow requires a selector
   change, make it an explicitly separate operation with restoration.
4. Validate the size encoding and bound reads by the discovered mapping.
   For the documented ChipCommon path the window is at most 1024 bytes.
   Refuse unsupported wrapper/core combinations rather than extrapolating.
5. Capture the shadow privately as bytes with explicit little-endian word
   conversion. Determine record boundaries from that capture. Only feed a
   proven Apple system-vendor record span to the existing `0x15` parser.
6. Demonstrate a real nonempty M/V/m tuple and chip revision before enabling
   the no-SKU filename patch or staging a C2/C4 firmware quartet.

The published dump function should not be copied unchanged. Its early
errors after switching cores bypass restoration. Its SPROM expression
compares a size measured in bits with `8`, despite the comment describing
8 Kbits, so every documented SPROM size selects a 512-word dump. The newer
65 nm row-size expression also has a four-bit index but an eight-entry
table. A future port needs explicit bounds and cleanup rather than these
assumptions. This audit does not exercise those paths on hardware.

## Result and remaining work

The BCM4350 NVM core/window now has chip-specific source evidence. The
remaining gate is narrower: observe J81's core revision, size/strap state,
and Apple record layout; recover the matching record offset and identity.
Hardware-independent next work can audit the existing Apple-record parser
with bounded synthetic captures and trace older firmware-loader selection.
Radio power, PCI enumeration, and an actual shadow capture still require
the iPad. No kernel/Nix/payload configuration is changed by this note.

The [native access-path validation](j81-bcm4350-nvm-validation.md) now
reproduces the public reader's size/mapping and cleanup behavior, checks its
65 nm table bounds under sanitizers, and traces the surrounding power-request
wrapper. It remains a synthetic reference comparison, not an enabled reader.
