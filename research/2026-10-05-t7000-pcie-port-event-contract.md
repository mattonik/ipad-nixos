# T7000/J81 PCIe port-event topology and handler contract

Status: research handoff; no hardware action was taken for this note.

## Conclusion

The J81 WLAN endpoint is behind APCIe port 1.  Its PCIe-port event interrupt is
independent from its MSI vectors:

| Purpose | Controller input | Linux trigger type | Evidence |
| --- | --- | --- | --- |
| Port 1 event parent | AIC hwirq 215 | level high | J81 ADT `apcie.interrupts[1]`; project DT skeleton |
| BCM4350 MSI slots | AIC hwirq 232--239 | edge rising | port 1 MSI base 8 + APCIe MSI base 224 |

The port-event handler must therefore be a separate, later feature.  It must
not be routed through the PCI MSI domain and is not a prerequisite for the
current MSI allocation self-test.

## Evidence chain

The preserved J81 ADT at
`artifacts/adt/20260908T082112Z-j81.adt` describes the APCIe node with:

* `interrupts = <212 215 218 221>`;
* `msi-vector-offset = 0xe0` (AIC 224);
* `msi-address = 0xbffff000`;
* child `pci-bridge1.apcie-port = 1` and `msi-vector-base = 8`;
* the BCM4350 endpoint below that child.

The existing J81 DT skeleton preserves the corresponding types: four
level-high port parents and a 32-vector, edge-rising MSI window beginning at
AIC 224.  Thus the port-1 parent is input index 1, AIC 215, while the WLAN MSI
range is 224 + 8 through 224 + 15.  These are different interrupt paths.

The current upstream Apple PCIe controller is useful as a *structural* guide,
not as authority for every T7000 register detail: it gives each PCIe port a
32-event child domain, masks/unmasks in `PORT_INTMSK`, acknowledges non-INTx
events through `PORT_INTSTAT`, and dispatches those events below the per-port
parent interrupt.  See [the upstream driver](https://github.com/torvalds/linux/blob/master/drivers/pci/controller/pcie-apple.c).

Earlier recovered iOS 8 initialization, recorded in
`research/2026-10-05-t7000-msi-domain-design.md`, programs `0xff70afff` at
APCIe offset `+0x104`.  Cross-family mapping identifies `+0x100` as port-event
status and `+0x104` as its mask.  The reliable initial event candidates are
LINK_UP (bit 12) and LINK_DOWN (bit 14); MSI_ERR, MSI_BAD_DATA and completion
timeout should remain diagnostic-only until a real endpoint delivery test
exists.

## Minimal implementation boundary (future builder work)

Do this only after a specifically authorized register-write experiment; it is
not part of an MSI self-test.

1. Obtain only port 1's parent (`platform_get_irq(..., 1)`), which must
   resolve to AIC 215.  Assert that mapping during probe.
2. Create a separate 32-entry linear child IRQ domain for port-event bits.
   Its non-INTx children use edge semantics; it must not reuse or alter the
   existing MSI domain.
3. In the chained parent handler, read `+0x100` once and dispatch only set
   children in the port-event domain.  Never interpret it as an MSI bitmap.
4. Acknowledge an individual non-INTx child by W1C of its bit at `+0x100`.
   Mask/unmask its individual bit at `+0x104`.  Do not bulk-clear status and
   do not modify unowned bits.
5. Start with link-up/link-down observation.  Keep error-event policy and
   recovery out of the first implementation.

Required offline checks: port 1 must resolve to parent 215; no MSI setup or
teardown path may write `+0x100` or `+0x104`; acknowledge/mask accesses must
be limited to the selected bit; and removal must release the child domain
before its parent IRQ.

## What this does not establish

Static evidence does not prove that a J81 port event will arrive under the
current payload, that a particular event is edge-versus-level at the AIC input
in every boot state, or that its error events are safely recoverable.  Those
are later hardware questions.  This note only fixes the topology and the
separation required to answer them without contaminating the MSI experiment.
