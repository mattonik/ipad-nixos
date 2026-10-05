# T7000/J81 PCIe MSI-domain research, 2026-10-05

## Scope and conclusion

This is a static-source review of the already working J81 PCIe bring-up.  It
does not build a payload, change a device, or claim that an interrupt was
delivered.

The recovered Stage 5E port writes are necessary *controller
initialisation*, but they do **not** give Linux a PCI MSI domain.  Therefore
the correct next implementation boundary is:

1. preserve the current, hardware-proven port-enable sequence;
2. do not add `msi-controller`, `msi-parent`, or `msi-ranges` to the T7000
   DT yet; and
3. treat MSI-domain support as a separately designed feature before enabling
   a BCM4350 function driver.

That prevents a device from receiving MSI messages whose Linux IRQ ownership
and dispatch path have not been proved.

## Established J81 topology

The preserved J81 ADT inventory records a shared PCIe MSI doorbell at
`0xbffff000`, 32 controller vectors, and an AIC vector offset of 224.  PCIe
port 1 owns an eight-vector slice beginning at vector 8.  The recovered
Apple port-enable callback consequently writes:

```
port + 0x124 = 0x00000031
port + 0x128 = 0x00080008
```

Those values and their place before PERST# deassertion are established by
the iOS callback decompilation and are part of the successful October 5 link
bring-up.  They describe controller programming only; neither record proves
the MSI address/data message format visible to the endpoint nor that an AIC
interrupt was received and acknowledged.

References: [`docs/plans/2026-09-13-j81-wifi-pcie.md`](../docs/plans/2026-09-13-j81-wifi-pcie.md)
and [`t7000-pcie-stage5-handoff.md`](t7000-pcie-stage5-handoff.md).

## What the present kernel can support

The configured kernel has `IRQ_DOMAIN`, `IRQ_DOMAIN_HIERARCHY`,
`GENERIC_MSI_IRQ`, `IRQ_MSI_LIB`, `PCI_MSI`, and the Apple AIC enabled.  The
Apple AIC creates a `DOMAIN_BUS_WIRED` hierarchy and supports allocation from
its three-cell DT interrupt specification.  Thus an AIC-parented PCI MSI
domain is a plausible Linux design; no Kconfig blocker remains.

The current T7000 node deliberately omits every MSI-domain DT property and
the host driver calls `pci_host_common_init()` without creating a domain.
`pci-host-common` sets the bridge's `msi_domain` capability flag, but it does
not manufacture a domain from that flag or from the Stage 5E register writes.

The pinned Apple T8103/T8112 DTs establish the Linux binding shape used by
the in-tree Apple driver: `msi-controller`, `msi-parent = <&pcie>`, and
`msi-ranges = <&aic AIC_IRQ N IRQ_TYPE_EDGE_RISING 32>`.  J81's historical
T7000 node already used the same form with `N = 224`; it was correctly
removed only because the matching domain did not exist.  This establishes the
DT contract for a complete implementation.  It is not authorization to add
those properties before the driver supplies the domain.

The newer generic Apple PCIe driver provides a useful *shape*, not a drop-in
implementation: it parses `msi-ranges`, finds the AIC wired parent, creates a
PCI-MSI parent domain, allocates a vector bitmap, and composes a doorbell
message using the allocated hardware vector.  Its fixed doorbell address is
`0xfffff000`, however, while J81's ADT says `0xbffff000`; its port-controller
register model is for a different Apple PCIe generation.  Copying it would
be unjustified.

## Newly corroborated older-controller reference

Corellium's open-source H9P driver is a closer *structural* reference than
the newer Apple driver.  It independently uses the following combination:

| Item | H9P reference | J81/T7000 evidence | Result |
|---|---|---|---|
| Controller-wide vector count | 32 | ADT `#msi-vectors = 32` | Exact topology match. |
| Per-port slice | 8 (`32 / 4`) | port 1 `msi-vector-base = 8` | Exact topology match. |
| Doorbell address | default `0xbffff000` | ADT `msi-address = 0xbffff000` | Exact address match. |
| Vector data | allocated global hardware vector | Not directly recovered from T7000 iOS code | Strong hypothesis only. |
| Port status/mask registers | `+0x100` W1C status, `+0x104` mask | T7000 iOS handler reads and clears `+0x100`; current J81 sequence uses the same offsets | Status role is corroborated; bit definitions are not. |
| Per-port MSI setup | `+0x124 = 0x31`, `+0x128 = base | base << 16` | Recovered Apple callback writes precisely those J81 values | Exact setup match. |

H9P binds 32 parent interrupt lines, one per hardware MSI vector, as chained
handlers; it then dispatches each to a linear MSI IRQ domain.  Its compose
function sends the global domain hardware-vector number as the PCI MSI data.
That explains the otherwise unusual J81 ADT combination particularly well:
the AIC span beginning at 224 is the 32-line parent range, and port 1's
vectors are globally `8..15`, not a local `0..7` range.

### J81 port-1 allocation rule

The vector base is not cosmetic.  H9P programs each port's `+0x128` base as
`port_index * 8` in both halves of the word and composes the endpoint message
with that **global** vector number.  J81's recovered `0x00080008` is exactly
the port-1 instance of that formula.  A T7000 implementation which copied the
newer Apple driver's initially-empty 32-bit bitmap unchanged would allocate
vector 0 to the BCM4350, while this port is configured for `8..15`.

The first J81-only MSI domain must therefore retain 32 global hardware-vector
numbers but make only `8..15` allocatable.  Its mapping is:

| BCM4350 allocation | PCI MSI data | AIC parent hwirq |
|---|---:|---:|
| first through eighth port-1 vector | 8 through 15 | 232 through 239 (`224 + vector`) |

Keeping the global numbering is important: shrinking the domain to eight and
composing data `0..7` would silently undo the port-base programming.  There
is no need to claim support for the other three ports in the first feature.

The reference is not an authority for T7000 register semantics: H9P is a
different SoC, and J81's current T7000 driver has not programmed the
endpoint-facing doorbell register at `+0x168` or observed an interrupt.
Use it to choose a research-backed Linux architecture, not to import masks
or opaque initialisation writes.

Primary source: [Corellium `pcie-hx.c` (sandcastle-5.4)](https://raw.githubusercontent.com/corellium/linux-sandcastle/sandcastle-5.4/drivers/pci/controller/pcie-hx.c).

## Required research before hardware use of an MSI implementation

The builder should not infer these missing facts from the current successful
enumeration:

- T7000's interrupt status/mask bit definitions and its handler's dispatch
  behaviour for *port events*.  The recovered `+0x100` read-and-W1C role is
  not a reason to acknowledge endpoint MSI there: the 32 MSI parents are a
  separate AIC range.  H9P's masks must not be copied as T7000 facts.
- Hardware confirmation that one delivered BCM4350 MSI reaches its expected
  AIC parent.  The J81 ADT's 32-vector offset and the H9P topology make the
  one-to-one `224 + global_vector` mapping a strong design conclusion, but
  no T7000 MSI has yet been observed.
- The exact lifetime/error-unwind relationship between a T7000 domain, its
  32 AIC parent IRQs, and the ECAM host bridge.

The iOS PCIe interrupt-handler callback and its controller event-source
enable path are the best next reverse-engineering targets.  The modern Apple
driver is a Linux API reference only.

## Review gate for a future MSI patch

Before hardware testing, static review should be able to point to all of the
following:

1. a T7000-specific source-derived mapping from J81 ADT data to the 32
   Linux MSI hardware vectors and AIC parent fwspec;
2. bounded allocation/free of the one initial PCI MSI vector, strictly from
   the port-1 `8..15` range;
3. a compose-message function with source-derived `0xbffff000` address and
   data encoding;
4. masked/acknowledged delivery and teardown paths for every allocated
   vector; and
5. DT properties introduced together with the working domain, never as an
   orphan declaration.

Until then, BCM4350 discovery is valuable evidence of link and configuration
space access, not evidence that Wi-Fi can safely bind or use interrupts.

## BCM4350 driver gate

The pinned `brcmfmac` source matches the observed endpoint exactly:
`BRCM_PCIE_4350_DEVICE_ID` is `0x43a3`, and the PCI table includes it.  The
current Nix configuration enables the `BRCMFMAC` core as a module but does
not set `BRCMFMAC_PCIE`; the latter is a separate, non-default Kconfig option
which supplies `pcie.o` and selects the MessageBuffer protocol.

More importantly, the PCIe attach path calls `pci_enable_msi()` and then
requests `pdev->irq`; it does not check that MSI enable succeeded before the
IRQ request.  Treat a valid MSI domain as mandatory rather than attempting a
legacy-INTx fallback.  Firmware/NVRAM selection remains a separate,
private-capture-gated issue and must not be folded into host-MSI work.

This is not merely a missing optional feature in the current host.  The
shared `pci-host-common` helper sets `bridge->msi_domain = true`; during root
bus creation, PCI core sets `PCI_BUS_FLAGS_NO_MSI` when that advertised host
domain cannot be resolved.  `pci_enable_msi()` will then reject the endpoint
before `brcmfmac` reaches its unchecked IRQ request.  A valid domain must be
attached to the host bridge **before** `pci_host_probe()` enumerates the
endpoint, so that the descendant PCI bus inherits it instead of the
`NO_MSI` flag.

The preserved October 5 endpoint configuration dump gives a useful bounded
first target.  Its standard capability chain reaches MSI at offset `0x58`:
the little-endian control word is `0x0088` (MSI disabled before binding,
64-bit address capable, Multiple Message Capable value 4, i.e. up to 16
messages).  `brcmfmac` uses the legacy `pci_enable_msi()` helper, which
requests **one** MSI.  Consequently the first host feature needs only one
allocated vector from port 1's global `8..15` slice; it does not need MSI-X,
multi-message allocation, or a BCM4350 firmware change.

This observation is from the original private record:
[`commands.jsonl`](../artifacts/live/sessions/20261005T071724Z-ead7dd92ea6547a3899274b82f174a8d/commands.jsonl),
the `od ... 0000:01:00.0/config` command.  It proves endpoint capability
presence, not successful MSI delivery.

## Safe builder boundary, if a compile-only preparation is desired

A builder may prepare a review-only patch that adds no DT MSI properties and
does not enable an endpoint driver.  It may factor the domain state and
cleanup paths behind `CONFIG_PCIE_APPLE_T7000`, using the pinned kernel's
`msi_create_parent_irq_domain()` API and AIC wired-domain fwspec handling.
It must leave the domain unregistered until the remaining
hardware-specific facts above are established.

Do not write `+0x168`, install chained handlers, restore
`msi-controller`/`msi-parent`/`msi-ranges`, or route BCM4350 interrupts in
such a preparation patch.  Those actions cross the research boundary into an
unvalidated hardware feature.

For the eventual complete patch, create/discover the PCI-MSI domain before
calling `pci_host_common_init()`/`pci_host_probe()`.  The root-bus setup
otherwise inherits `PCI_BUS_FLAGS_NO_MSI`, which cannot be repaired after
the BCM4350 has already been enumerated.

## Research-backed implementation contract

This is a narrow J81/port-1 design for review; it is not a request for a
hardware run.

1. Restore the three established DT properties as one atomic change:
   `msi-controller`, self `msi-parent`, and
   `msi-ranges = <&aic AIC_IRQ 224 IRQ_TYPE_EDGE_RISING 32>`.
2. Before the existing common-host initialisation, create a PCI-MSI parent
   domain rooted at the PCIe device fwnode, with the AIC wired domain obtained
   from that `msi-ranges` fwspec.  The pinned in-tree `pcie-apple.c` is the
   API/lifetime template, not a register-programming template.
3. Give the domain 32 global hardware-vector slots, but reserve every slot
   except `8..15`.  Allocate power-of-two blocks only from that range.
4. Compose MSI as address `0x00000000bffff000` and data equal to the global
   slot (`8..15`).  Parent allocation consequently starts at AIC 232 for the
   first usable slot.
5. Attach/discover that domain before `pci_host_common_init()` so PCI core
   does not mark the bus `NO_MSI`.
6. Do not write new controller registers for the first domain: specifically
   no guessed `+0x168`, no H9P port-event masks, and no `+0x100` endpoint-MSI
   acknowledgement.  The existing recovered port bring-up remains unchanged.

Keep `BRCMFMAC_PCIE` disabled during the host-domain-only review/build.  Once
the host feature has passed review and a separately authorised hardware test
confirms one delivered vector, enabling the existing PCIe transport is a
small Kconfig change; firmware/NVRAM remains an independent evidence gate.
