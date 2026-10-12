# Making the project ready for the community, and upstreaming what can be upstreamed

Status 2026-10-12. Nothing here has been published or sent anywhere; every outward step below waits for an explicit decision.

## What exists
A reproducible build and bring-up of Linux 7.3-rc1 and NixOS on an iPad Air 2 (A8X/T7001, J81): checkm8 -> PongoOS -> Hoolock m1n1 -> kernel -> NixOS in RAM (stage-1 hand-off), with Wi-Fi (BCM4350 over a PCIe/DART port), USB networking, charging, battery gauge, SPI3, UARTs. About 460 tracked files: 105 research/findings notes, 100 boot tools and tests, 211 kernel files (100 patches, many of them staged experiments), the flake, and the NixOS system. What does NOT work is documented honestly: touch (controller ROM never acknowledges the firmware), Bluetooth (controller silent), audio, GPU acceleration, storage (NAND is deliberately read-only).

## Audience and value
- People bringing up other A7-A11 / Apple SoC devices: the findings that cost days here (DART leaf format and init order, S5L SPI transfer bugs, UART sampling-factor baud, D2207 charger and ADC, Wi-Fi bring-up root cause) are directly reusable.
- The Hoolock and Asahi kernel communities: several fixes are generic.
- Anyone reproducing the checkm8 -> NixOS path.

## Phases
**A. Hygiene (started).** `tools/audit_public.py` scans every tracked file for per-device MACs, Wi-Fi secrets, private keys, device serials/ECIDs/UDIDs, home directories and hex dumps; it runs clean now (home paths scrubbed). Git history was checked for the real device MAC, the network name and the device serial: none present. Still to do: decide what to leave out (see decisions), license review of bundled binaries (`boot/Pongo.bin`), run the audit as part of the test suite.

**B. Documentation.** Rewrite the README (it still describes the early boot-only state), a hardware status matrix with the evidence for each line, a curated `docs/FINDINGS.md` of the technical discoveries, a reproduction guide (build, DFU, load, NixOS-in-RAM), a safety page (the hazards: PCIe/BAR reads reset the SoC, PMIC writes, never touch NAND), and an index that makes the 105 research notes navigable. Move the 160 KB running log (`docs/project-status.md`) and the agent briefs into an `archive/` section.

**C. Clean kernel series.** The production stack is 63 patches touching 34 files (about 4.2 k added lines) but it is the history of experiments: staged increments (0040-0045, 0052-0057), diagnostic-only code behind `*_DIAG` options, and test payloads. For sharing, regenerate it as a short series of logical, reviewable commits against the Hoolock base: drop the diagnostics (kept in `archive/`), squash staged steps, write real commit messages (cause, fix, evidence), and add Device Tree binding documentation where a new property exists (`apple,baud-factor-select`, the DART `apple,*` options, the PCIe node).

**D. Upstream.** Candidates, in the order I would send them (pilot first, then the larger stack):

| Series | Content | Target | Notes |
|---|---|---|---|
| 1 | serdev stop-bit selection API (0003), bq27xxx HDQ-over-UART frontend + identification retry (0004, 0091) | linux-serial / power-supply lists | generic, small |
| 2 | `spi-apple` S5L fixes: transfer loop only serviced one FIFO round (silently truncated every longer transfer, returned success), word delay register, functional clock | Hoolock tree (S5L SPI is not in mainline); possibly linux-spi | real bugs with a measured reproducer |
| 3 | `samsung_tty` Apple S5L sampling-factor baud (0092, 0093) for rates above 1.5 Mbaud | linux-serial | needs a binding for the DT property |
| 4 | `apple-dart` / `io-pgtable-dart` T7000 support: iOS-format PTEs, error-reflector first init order, leaf bits, DT options (0080-0090) | Hoolock tree, then linux-iommu | the root cause of the Wi-Fi DMA problem |
| 5 | `pcie-apple-t7000` host controller (0052-0057 final state) + DT | Hoolock tree first | largest; needs cleanup and a binding |
| 6 | brcmfmac fixes needed on this platform (local-mac-address handling, TxCap, OTP parser bounds) | linux-wireless | verify what is generic |
| 7 | D2207 charger/ADC driver (0010, 0017, 0099) | Hoolock tree | J81-specific until a proper PMIC MFD exists |

Process notes: the Linux kernel's rules on AI-assisted contributions apply (the human submitter signs off, with an `Assisted-by:` style disclosure, not a co-author tag); every patch must be checked with `checkpatch.pl` and build-tested; Hoolock changes go through its maintainers, so the first step for series 2-7 is a conversation, not a pull request.

**E. Release.** Export a clean tree (no history, or a filtered history) to a public repository with the audit passing, the license settled, and no Apple firmware, no per-device data, no raw captures.

## Decisions needed from the project owner
1. Where to publish (account/organization and repository name), and whether to publish the history or a squashed export.
2. License for the non-kernel parts (currently MIT; kernel patches stay GPL-2.0-only).
3. What stays private: `CLAUDE.md` and the agent briefs (process artifacts with personal paths and instructions), the long status log, any note you consider sensitive.
4. Whether to contact the Hoolock maintainers (and which of the series to offer first), and how contributions should be credited (author identity and sign-off).
5. How much to invest: pilot (series 1-3 and the documentation) is days; the PCIe/DART/Wi-Fi stack is weeks.
