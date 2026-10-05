# Review: PCIe production-driver audit, MSI-domain plan, and the GPIO55 identity record

Date: 2026-10-05. A review of the research agent's three new, uncommitted items:
[`2026-10-05-pcie-production-driver-audit.md`](2026-10-05-pcie-production-driver-audit.md),
[`2026-10-05-t7000-pcie-msi-domain-research.md`](2026-10-05-t7000-pcie-msi-domain-research.md) and
[`evidence/2026-10-05-touch-display-sync-identity.md`](evidence/2026-10-05-touch-display-sync-identity.md)
(plus its transcript record). Claims were checked against the pinned kernel source tree
of the `0053` payload, the private ADT and git history; nothing here was run on the
device. Labels: **E** verified here, **I** inference, **U** unknown.

## Verdict

The audit and the MSI research are sound and the sequencing they propose is right:
clean-up first with a provable no-behaviour-change rule, MSI as a separately designed
feature, nothing near `brcmfmac` until MSI exists. Two things need fixing before the MSI
plan is builder-ready (one gap, below, is new and significant), and one factual error in
the evidence record needs correcting.

## Verified claims (E)

- **ADT MSI facts:** `msi-vector-offset = 0xe0` (224), `msi-address = 00 f0 ff bf` =
  `0xbffff000`, `#msi-vectors = 32`, port-1 `msi-vector-base = 8` with `#msi-vectors = 8`,
  `msi-parent-controller` = the AIC phandle. Matches the note exactly.
- **`pci-host-common` sets `bridge->msi_domain = true`** (`pci-host-common.c:235`), and
  `probe.c` sets `PCI_BUS_FLAGS_NO_MSI` when the bridge advertises an MSI domain but none
  resolves **and the DT has no MSI map** (`!pci_host_of_has_msi_map(parent)`). The note
  is right that the domain must exist before `pci_host_probe()`; it omits that a DT
  `msi-map` also suppresses the flag (an alternative, not a shortcut: it still needs a
  domain).
- **`brcmfmac` ignores the result of `pci_enable_msi()`** and then requests `pdev->irq`
  (`pcie.c:977-978`). With `NO_MSI` set, `pdev->irq` is 0/legacy and the IRQ request
  fails after the failed enable. Confirms "MSI is mandatory for this endpoint".
- **Link timing in the audit** (link start 0.3514 s, DLLLA 0.3574 s) matches the recorded
  kernel log; the two warnings' explanations match the independent analysis already in
  `j81-d2207-gpio-register-correction.md` (Gen1-only endpoint under a 5 GT/s-capable port;
  root-port RID `0x8` outside the `0x100` iommu-map entry).

## Gap in the MSI plan: the DART doorbell reservation points at the wrong page (E)

The pinned `apple-dart.c` reserves a **doorbell page as an `IOMMU_RESV_MSI` region for every
PCI device behind a DART** whenever `CONFIG_PCIE_APPLE` is enabled, at
`CONFIG_PCIE_APPLE_MSI_DOORBELL_ADDR`. The J81 kernel config (inherited `config_16k`)
has `CONFIG_PCIE_APPLE=y` and `CONFIG_PCIE_APPLE_MSI_DOORBELL_ADDR=0xfffff000`, the M1
value. J81's doorbell is **`0xbffff000`**. So today:

- the DART tells the IOMMU core that `0xfffff000` is reserved, **not** the real doorbell
  page, so `0xbffff000` remains ordinary allocatable IOVA space (an endpoint DMA mapping
  could land on the doorbell); and
- the in-tree driver's own comment states the requirement: the doorbell "has to be
  excluded from the IOVA range, and the DART driver has to know about it".

The MSI note does not mention this. It must be part of the design: either set the
J81 kernel's `CONFIG_PCIE_APPLE_MSI_DOORBELL_ADDR` to `0xbffff000` (acceptable for a
J81-only kernel because the M1 `pcie-apple` driver is not used), or make the reservation
per-controller from the DT. Either way it must change **before** any endpoint DMA or MSI.

Related **unknown (U)** the note should name explicitly: whether J81's DART lets the
endpoint's write to `0xbffff000` through untranslated, or the doorbell needs an IOVA
mapping (the generic `iommu_dma_prepare_msi` route). The M1 driver does not call it, and
that works on M1 because of its controller-side MSI map, which this older controller is
not known to have. This decides how the compose function must build its address.

## The first-MSI proof is entangled with the firmware gate (I)

The plan's acceptance step is "a separately authorised hardware test confirms one
delivered vector". With no firmware running, the BCM4350 does not raise MSIs, so there is
no endpoint-side trigger yet; the first real MSI will come from `brcmfmac` after firmware
boot, which is gated on private-capture/NVRAM evidence. The plan should either state that
dependency honestly or identify an endpoint-independent trigger (none is known). It
should also say what failure looks like (spurious/no interrupt) and keep the DT properties
and the domain as one atomic change, as it already does.

## Evidence record for the GPIO55 run: one factual error (E)

The identity note says the preserved preflight session was "recorded at source commit
`770b03a`, which **predates the GPIO55 implementation**", and so must not be attributed to
the display-sync run. That is wrong:

- `git merge-base --is-ancestor 7aa9227 770b03a` succeeds: the GPIO55 feature (`7aa9227`)
  is an **ancestor** of `770b03a`, so the session's source commit already contains it.
- The session's payload `/nix/store/8ssi0vk...-hoolock-touch-spi/m1n1-linux.bin` has
  SHA-256 `c320196b...b006` (re-computed here, matches), and its embedded `touch-diag`
  binary contains `--display-sync-pinmux`: it is **the payload that has the feature**.
- The preflight (`plan`, `status`, `spi-check`) and the experiment were the same boot: the
  user ran the experiment over SSH minutes later, with no reboot between.

So the host-side payload identity for the run is established by **continuity** (same boot,
recorded preflight with the exact store path and hash), not unknown. What remains true:
the experiment command itself was run by the user in a terminal and pasted, not captured
by `SessionEvidence`; and a host hash still does not prove what the tablet booted. The
note's forward-looking requirement (record every hardware run, add an on-device build
identifier) is good and should be adopted.

## Assessment of the implementation plan

1. **Clean-driver series (builder-ready now).** Agreed, with one addition: enforce
   "no change to the recovered writes" **mechanically**. Add a host test that extracts the
   ordered sequence of MMIO writes, masks, values and delays from the `0053` source and the
   cleaned source and asserts they are identical (a write-sequence fingerprint), plus the
   existing source-level assertions that `+0x88` is never a decision input. A reviewer's
   promise is weaker than a failing test.
2. **MSI domain.** Fix the doorbell reservation and the DART-translation unknown first,
   then the research contract (J81-only, 32 global slots with `8..15` allocatable, data
   equal to the global slot, AIC `224 + slot`, domain before `pci_host_probe()`).
   Compile-only preparation is fine; no hardware step is justified yet.
3. **Out of scope until MSI exists:** `BRCMFMAC_PCIE`, firmware/NVRAM, Bluetooth.
4. **Retraining-quirk exemption:** correctly deferred. It is a few milliseconds of harmless
   work; do not add code to avoid it.

## Follow-up 2026-10-05: DART doorbell reservation, baseline measured and fix built

**Baseline on hardware (clean payload, `0054`, read-only):** the endpoint's IOMMU group
reports `reserved_regions = 0x00000000fffff000 0x00000000ffffffff msi`. That is the M1-family
doorbell from the inherited `CONFIG_PCIE_APPLE_MSI_DOORBELL_ADDR`, not J81's `0xbffff000`,
confirming on the device what the source review found: the real J81 doorbell page is
ordinary allocatable IOVA space today.

**Fix (patch `0055`, per-controller):** the Apple DART now reads `apple,msi-doorbell` (a
64-bit address) from the host bridge's controller node and reserves that page, falling back to
the global Kconfig value when the property is absent so other users are unchanged. The J81 DT
declares `apple,msi-doorbell = <0x0 0xbffff000>` on the PCIe node; the binding documents it
(and the example, which `0052` left unterminated, is repaired).

**Built and verified on the host:** payload `m1n1-hoolock-pcie-j81-doorbell` builds; the
verifier's `--doorbell` mode passes (checksums, composition, the PMIC phandle, no Bluetooth or
I2C tools, only clean-up log strings, `apple,msi-doorbell = 0x0 0xbffff000` on the PCIe node
and nowhere else, the property lookup present in the kernel). Against the clean payload, only
`Image.gz` and `t7001-j81.dtb` differ; Pongo, m1n1, initramfs and bootargs are byte-identical.

**Prediction for the hardware test (read-only):** the same IOMMU group should now list
`0x00000000bffff000 0x00000000bffffffff msi` instead of the `0xfffff000` line, with link,
enumeration and config space unchanged. Whether J81's DART lets an endpoint write to the
doorbell untranslated is still **unknown** and is not testable until an endpoint raises an MSI.

## Hardware result 2026-10-05: per-controller DART doorbell (`0055`) takes effect

Payload `m1n1-hoolock-pcie-j81-doorbell` (`0052`-`0055`, build verified above), cold boot with
the user's go-ahead (its only PMU write is the board-gated `0x0403` assert); recorded session
(private), read-only checks over telnet.

| | clean payload (`0054`) | doorbell payload (`0055`) |
| --- | --- | --- |
| endpoint IOMMU group 0 `reserved_regions` | `0x00000000fffff000 0x00000000ffffffff msi` | **`0x00000000bffff000 0x00000000bfffffff msi`** |

- The DART now reserves **J81's own doorbell page** for the BCM4350's group, exactly as
  predicted; the M1 page `0xfffff000` is no longer reserved. The device tree on the running
  tablet carries the property (`/proc/device-tree/soc/pcie@610000000/apple,msi-doorbell` =
  `00 00 00 00 bf ff f0 00`), so the value came from the controller node, not Kconfig.
- Nothing else changed: `REG_ON 0x0403 0x09 -> 0x0b` at 0.1346 s, `link active=1
  lnksta=0x3011` at 0.3494 s, root port `106b:1002` and endpoint `14e4:43a3` (rev `0x05`) enumerate
  at 0.351 s / 0.358 s, root port `LnkCap 0x00733812` / `LnkSta 0x7011` / `LnkCtl2 0x0001`,
  endpoint `LnkSta 0x1011`. Same benign `retraining failed` and `iommu-map id 0x8` lines; no
  error, AER, DART fault, oops or WARNING lines. `lspci` lists both devices.
- Still **unknown** (not testable without an endpoint that raises an MSI): whether J81's DART
  passes a write to `0xbffff000` through untranslated or needs an IOVA mapping, i.e. how the
  future MSI compose function must form the message address.

This closes the DART-doorbell gap identified in the review as far as it can be closed without
an MSI domain. The remaining MSI-domain design points (32 global slots with only `8..15`
allocatable, data equal to the slot, AIC parent `224 + slot`, domain created before
`pci_host_probe()`) are unchanged.
