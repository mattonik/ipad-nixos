# T7000 PCIe delivery-path pre-study

Date: 2026-10-05.  Static research only: no payload was built and no device
was accessed.  This study separates the remaining questions that are often
grouped under "MSI" but are in fact three independent paths.

## Conclusion

The next useful device experiment is a **read-only dump of port-1 `+0x168`**
after the established controller initialisation.  It is a prerequisite for
interpreting a future *delivery* result, but not for H1A's allocation/config
test.

Do not use `brcmfmac` merely to manufacture a test interrupt.  A real
BCM4350-generated MSI requires a full endpoint bring-up with firmware/NVRAM,
bus mastering, DMA-ring setup, and BAR accesses.  That is a Wi-Fi integration
experiment, not a narrowly scoped interrupt test.

## 1. Doorbell routing (`+0x168`) remains the delivery gate

The in-tree Apple PCIe driver labels offset `+0x168` `PORT_MSIADDR` and
writes its doorbell address there before enabling controller MSI.  Its comment
also says the doorbell must be excluded from the IOVA range.  This is a useful
cross-generation semantic reference, but not authority to write J81's
register: the recovered iOS 8.1 J81 path never writes this offset.

J81 has an ADT `msi-address` of `0xbffff000`; patch `0055` now reserves that
same page in the appropriate DART domain, and the endpoint MSI messages
composed by `0057` use it.  What remains unknown is whether J81 firmware
already programmed or hard-wired `PORT_MSIADDR` to that value.  A post-init
read of `+0x168` distinguishes the two relevant cases:

| Readback | Meaning | Consequence |
| --- | --- | --- |
| `0xbffff000` | Strong evidence that endpoint message address and controller route agree | A later delivery test has one less unknown. |
| Any other value or zero | The configuration-path H1A result remains valid, but no endpoint MSI delivery claim is interpretable | Stop before a delivery test; research firmware/default semantics rather than guessing a write. |

The dump must have no accompanying write, no new unmask, and no endpoint
driver.  Capture it in the raw run transcript and manifest alongside the
payload identity.

## 2. Port events are not PCI MSI

The modern Apple driver independently documents `+0x100` as port interrupt
status and `+0x104` as its mask.  Its per-port **wired** parent IRQ is handled
by reading status and dispatching set bits to a 32-entry port-event domain.
It installs handlers only for `LINK_UP` and `LINK_DOWN`; it configures the
MSI doorbell and the PCI-MSI hierarchy separately.

This agrees with the recovered J81 tail: `+0x104 = 0xff70afff` unmasks the
interesting link/error bits, including `LINK_UP`, `LINK_DOWN`, `MSI_ERR`, and
`MSI_BAD_DATA`; `+0x100` is W1C status.  It does **not** mean the port status
register acknowledges PCI endpoint MSI.  The endpoint's MSI parents are the
independent AIC lines 224..255, while port 1's wired event lines are below
that range.

Therefore the future port-event task is its own bounded feature:

1. recover the exact J81 port-to-wired-AIC parent mapping from iOS/ADT;
2. create a port-event domain and chained wired handler;
3. dispatch/ack only port-status bits; and
4. initially request only link-up/down, retaining other error bits as logged
   diagnostics until their recovery policy is sourced.

It must not be mixed into the H1A MSI allocation self-test.

## 3. Why `brcmfmac` is not a minimal MSI trigger

In upstream `brcmfmac/pcie.c`, the PCIe attach first enables the device and
sets it bus master, maps BARs, discovers chip resources, uploads firmware and
NVRAM, allocates DMA rings and scratch buffers, and only then calls
`pci_enable_msi()` followed by `request_threaded_irq()`.  Its interrupt
handler consumes endpoint mailbox/doorbell state and DMA completion data.

Consequently a real firing IRQ is valuable eventual evidence for the full
chain (endpoint -> controller doorbell -> DART/AIC -> Linux), but it also
introduces firmware provenance, DMA/IOMMU correctness, calibration, and radio
state.  It is not an appropriate substitute for the current reversible
configuration-path self-test.

## Recommended order

1. Tighten `0058` so H1A asserts its numerical IRQ parent chain and reports
   teardown status (already identified in the self-test review).
2. Keep H1A restricted to allocation/configuration; do not infer delivery
   from it.
3. Run a standalone, read-only `+0x168` diagnostic when separately approved.
4. Finish source recovery for the J81 wired port-event parent before adding
   any event handler.
5. Design a separately approved Wi-Fi attach/delivery experiment only after
   firmware/NVRAM provenance and DART DMA conditions are ready.

## Sources

* [Linux Apple PCIe host driver](https://github.com/torvalds/linux/blob/master/drivers/pci/controller/pcie-apple.c): `PORT_INTSTAT`, `PORT_INTMSK`,
  `PORT_MSIADDR`, port-event handler, MSI configuration, and parent-domain
  structure.
* [Linux brcmfmac PCIe transport](https://github.com/torvalds/linux/blob/master/drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c): BCM4350
  firmware mapping, resource acquisition, MSI request, and mailbox interrupt
  flow.
* Local evidence: `research/2026-10-05-t7000-msi-domain-design.md`,
  `research/2026-10-05-msi-selftest-review.md`, and the `0055`--`0058`
  patches.
