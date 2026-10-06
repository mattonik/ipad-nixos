# J81 Wi-Fi: DMA and MSI continuation plan

Date: 2026-10-06. This is the active plan for turning the hardware-confirmed
BCM4350 PCIe endpoint into a Linux interface. It supersedes no historical
evidence; use the [MSI delivery review](../../research/2026-10-06-pcie-msi-delivery-review.md)
for the current evidence boundary.

## Current facts

- J81's BCM4350 (`14e4:43a3`) powers on, links, and enumerates.
- H1A configured its MSI capability with address `0xbffff000`, data `8`, and
  the expected AIC event `232`; that validates allocation, not delivery.
- iOS composes the same address/data directly from ADT state. `+0x168` is not
  a T7000 MSI setup step and must not be written.
- Apple gives the endpoint DMA addresses in `[0x80000000, 0xbffff000)`, but
  rebases them to zero-based DART PTE pages. Linux currently has no equivalent
  rebase. The fabric-side meaning is not statically observable.
- Correct BCM4350 firmware/NVRAM selection, NVM identity, and J81 calibration
  handling are still gates. Never use generic assets as a substitute.

No new hardware is required for this plan. Every device run needs a separate
user go-ahead and a recorded, recoverable USB-network session.

## Non-negotiable boundaries

- Do not write port `+0x168`, fish adjacent controller offsets, or use an
  AIC software injection as an MSI-delivery claim.
- Do not use the BCM `sbtopcimailbox` register as a test trigger: host-write
  semantics and recovery are not established for BCM4350.
- Do not associate, scan, or intentionally transmit during the first firmware
  and DMA/MSI experiments. Firmware startup cannot promise absolute RF silence;
  it can only avoid intentional network activity.
- Keep firmware, NVRAM, raw NVM captures, calibration, MAC addresses, and raw
  session logs outside Git.
- Keep each test payload narrowly scoped. The research agent does not build or
  deploy payloads; the development agent owns that work.

## Work plan

| Phase | Objective | Research agent | Development agent | iPad run / acceptance |
| --- | --- | --- | --- | --- |
| 0 | Preserve the known baseline | Audit claims and keep run identity evidence current. | None. Do not promote patch `0060`; it is compile-only research. | None. |
| 1 | Prove firmware identity inputs | Recover the BCM4350 NVM-record format, module/vendor/version tuple, Apple C2/C4 selector, and the role of old J81 calibration fields. Review only private captures locally. | Prepare only a bounded, test-only NVM metadata-capture design after review. It must identify chip/core revision, size/strap state, and restore every core/window selection. | Explicitly approved capture; private output must prove a nonempty tuple and record boundaries. Any unsupported core/wrapper is a clean stop. |
| 2 | Make a correct Linux DMA-model candidate | Specify the smallest Linux-side representation of Apple's `vm-offset` rebase and its failure/unwind behaviour. Verify that it cannot change other DART users. | Implement one isolated **test** mapping model, with source tests and a payload verifier. It must not claim that `0060` alone solves the rebase. Build-only review first. | None until Phase 1 identifies the exact firmware/NVRAM input. |
| 3 | Discriminate DMA mapping and establish H1B | Define logs and pass/fail criteria before any run. Review the built payload identity and boot token. | Build one model per payload; preserve telnet recovery and add no scan/association automation. Capture DART faults, endpoint MSI capability, AIC counters, port status, and mailbox state. | First firmware preinit control completion, normally `cur_etheraddr`, is the event. **Pass:** matching D2H completion plus AIC 232/slot 8 and no DART/MSI error. **Fail:** pending D2H completion with MSI enabled but no AIC event, wrong vector, or MSI error. Firmware/NVRAM/DMA setup failure is inconclusive. |
| 4 | Interface creation without RF use | Audit logs and distinguish transport success from calibration success. | Enable `BRCMFMAC_PCIE` only in the approved test payload; package the proven private assets outside Git. Stop after firmware/interface creation. | Confirm interface creation and stable control path; no scan or association. A calibration mismatch is a stop, not a fallback opportunity. |
| 5 | Normal Wi-Fi use | Review exact scope and recovery plan. | Add ordinary network policy only after the prior phase is stable and repeatable. | Separate approval for scan, association, and traffic. |

## Ownership detail

### Best suited to research

1. Decode the private NVM capture and establish the exact firmware/NVRAM
   selection inputs.
2. Review the development agent's DMA-rebase design against the traced iOS
   contract. The open fabric boundary cannot be solved with more register
   guesses.
3. Define the Phase-3 evidence protocol and classify any session as pass,
   fail, or inconclusive.

### Best suited to development

1. Write and compile the bounded NVM metadata diagnostic after its static
   contract is approved.
2. Implement the isolated DMA-rebase candidate and build test payloads.
3. Maintain payload verification, run tokens, initramfs recovery access, and
   private-asset packaging.
4. Keep `0060` out of any production/default payload unless a later DMA run
   validates the full model.

### Needs the iPad

1. NVM metadata capture (Phase 1).
2. Firmware/DMA/MSI control-completion experiment (Phase 3).
3. Interface creation, then separately any RF use (Phases 4--5).

## Decision gates

```text
private NVM identity
        |
        v
correct firmware + NVRAM + calibration policy
        |
        v
one reviewed DMA-rebase test payload
        |
        v
first D2H control completion --> AIC 232 observed? --> H1B delivery proven
        |
        v
interface creation, then separately scan/association
```

If Phase 1 cannot prove the NVM tuple or calibration policy, stop before
loading firmware. If Phase 3 cannot attribute a result because firmware did
not start or DMA faulted first, fix that earlier gate rather than calling MSI
broken.
