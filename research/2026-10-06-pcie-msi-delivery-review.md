# J81 PCIe MSI delivery: reviewed state and remaining gate

Date: 2026-10-06. Static research only; no payload was built, booted, or
changed on hardware. This records the completed MSI research before the one
remaining APCIe-to-DART address-rebase trace.

## What is now established

The iOS 8.1 `AppleEmbeddedPCIE` path reads J81's ADT `msi-address` and
returns it directly to Apple's generic PCI MSI allocator. For the BCM4350,
the selected path uses that ordinary address; the separate crypto address is
only for nodes carrying `crypto-queue-msi`, which the saved J81 ADT does not
contain.

The generic allocator passes the per-port absolute vector number into that
provider. J81 port 1 allocates slots 8--15, so the complete native contract
is:

| MSI field | Native J81 value |
| --- | --- |
| address | `0x00000000bffff000` |
| data | allocated absolute slot, 8--15 |
| AIC parent | `224 + slot`, thus 232--239 |

This upgrades the former data-value inference: the allocator-to-provider
handoff was traced. It agrees with the H1A hardware configuration result.
The primary trace is
[`2026-10-05-j81-msi-message-provider-trace.md`](2026-10-05-j81-msi-message-provider-trace.md).

## `+0x168` is closed

The M1-named `+0x168` register is not used by the traced T7000 MSI message
path. iOS does not program it; the hardware readback of zero is therefore
compatible with correct T7000 MSI composition. Do not write it. This does not
prove the register has no unrelated T7000 meaning; it only proves it is not a
source-derived MSI-doorbell setup step.

## DART correction

The ADT `vm-offset`/`vm-size` values establish Apple's external IOVA range
`[0x80000000, 0xbffff000)`, immediately below the MSI page. But the exact
iOS DART implementation uses those values as a **software VM allocator and
PTE-index rebase**: it subtracts `vm-offset` before page-table operations.
No traced DART register programs the same range as a hardware aperture.

Consequently, patch `0060` is not deployment evidence. It may be retained as
a compile-only conservative allocator-policy proposal, but its claims must
not say that hardware enforces the window, and it does not yet reproduce
Apple's rebase. The remaining static question is whether APCIe/fabric
converts the endpoint-visible IOVA to that rebased DART space. See
[`2026-10-05-j81-dart-window-and-msi-doorbell.md`](2026-10-05-j81-dart-window-and-msi-doorbell.md),
whose hardware-fixed wording is superseded by this correction.

## Rejected shortcut

A firmware-free BCM4350 `sbtopcimailbox` host write is not a valid MSI test.
Available BCM4350-era sources document it as a backplane-to-PCIe source but
do not prove that a host BAR write has the same side effect, produces MSI
rather than legacy INTx, or has a safe reset/acknowledgement sequence. Do not
poke it.

## Eventual H1B delivery observation

Once exact firmware/NVRAM identity and the DMA-address model are proven, the
first `brcmfmac` preinit control completion is the smallest production-path
event. It occurs before scan, association, or interface registration. A pass
requires a correlated D2H completion, endpoint MSI address/data, AIC slot 232
(for initial slot 8), and no DART fault or controller MSI error. A firmware
timeout without a pending endpoint completion is inconclusive, not an MSI
failure.

## Evidence identity

* kernelcache: `19c277d60e0a1185b1e4a1b72cda4f1f550c0b0bf670791542234a6dbbcc28bf`
* extracted PRELINK text: `322bd7e33a6410caa520aae1282ca14e8791c4d2bd2af3b991ae1bb4a0f5c108`
* saved J81 ADT: `cf743765e66a1a5b45cbf4e18c0e5ae21454bb1cb678b66e7007e2db04f5b6c2`

## APCIe-to-DART rebase: static result

That trace is now complete. Apple allocates mapper-apcie1 IOVAs in rebased
page space, adds `vm-offset >> 12` (`0x80000`) before returning an address to
the PCIe endpoint, and subtracts it again for every DART mapping, unmapping,
and lookup. Therefore endpoint-visible `0x80000000` maps to DART PTE page 0
in Apple's software model.

No traced `AppleEmbeddedPCIE`/`AppleT7000PCIe` code programs an outbound,
inbound, or ATU base; it only performs resource, power, PHY, and link setup.
The DART setup programs page tables and control state but no IOVA-base or
aperture register. The unresolved boundary is consequently the transaction
as presented by the T7000 APCIe fabric to the DART: fixed hardware decode,
inherited boot-stage state, or undocumented DART address interpretation.

This makes the `0060` limitation concrete: it restricts Linux allocation but
does **not** reproduce Apple's PTE rebase. Do not deploy it. In particular,
an unmodified Linux mapping for external IOVA `0x80000000` would occupy raw
DART page `0x80000`, not Apple's page 0.

## Next and stop condition

Static research has reached its evidence boundary. The smallest discriminating
future observation is a bounded DMA-translation comparison that distinguishes
the page-0 and page-`0x80000` models, after the BCM4350 firmware/NVRAM gate.
Do not continue with guessed controller registers, broad address dumps, or
an MSI delivery test until that DMA model is established.
