# Review: 0058 T7000 MSI allocation self-test

Reviewed 2026-10-05, read-only.  This records the boundary of the test
payload added by commit `98ee5b1` and the prerequisite I recommend before a
hardware run.  It does not authorize a device run.

## Evidence reviewed

* Commit `6fc2639` records the H0 boot of the 0057 domain payload.  It shows
  domain construction before host enumeration, an active link, and normal
  enumeration of the BCM4350 (`14e4:43a3`).
* Raw H0 command sessions are retained under
  `artifacts/live/sessions/20261005T120039Z-5ca669d54aec4c959e2c0ed8ab0511fc/`
  and `artifacts/live/sessions/20261005T120048Z-1ee56219740a47a3bdb4e9262f8fc341/`.
  Their manifests identify source commit `6598e8324d72b14b1809e98b8bd4d2e7a8c74dad`
  and the host payload SHA-256
  `a8c2078758aab1a3a911f74c11302f52bff3b70dddbe61faaf0d3c8b92433809`.
  They explicitly do not claim to prove the payload identity already running
  on the device.
* Commit `1bdadad` records that the new 0058 payload builds and its offline
  `--msi-selftest` verifier passes.  No 0058 hardware run has occurred.

## What H1 would actually do

The ordinary J81 boot path performs the existing PMU `0x0403` read-modify-
write.  In addition, 0058 calls `pci_alloc_irq_vectors()` for the BCM4350.
PCI core therefore writes that endpoint's MSI capability: MSI address,
message data, and enable bit.  It then requests/frees the resulting Linux
IRQ and frees the vectors, which disables MSI again.

This is a bounded and intended configuration-space mutation, but it is more
than a single PMU-byte write.  An H1 approval should name both operations.
The test does not start endpoint firmware, enable bus mastering, perform a
doorbell write, or deliberately cause a device MSI.

## What it establishes

On success, 0058 can establish that the kernel can allocate one PCI MSI
vector and compose an enabled endpoint MSI message with:

* address `0x00000000_bffff000`;
* data in the J81 port-1 range `8..15`; and
* a requestable Linux IRQ.

`fired=0` is expected: no endpoint event is generated.

## Gap to close before the run

`t7000_msi_selftest_chain()` prints the parent IRQ chain but the final
`PASS` condition checks only the endpoint capability values and successful
`request_irq()`.  A malformed parent mapping could therefore still report
`PASS` if the data happens to lie in `8..15`.

The next builder should make this a strict assertion, without changing
hardware scope:

1. Capture the relevant `irq_data` levels while walking the chain.
2. Require the controller-vector hwirq to equal the MSI data and the AIC
   parent hwirq to equal `224 + data`.
3. Include the post-`pci_free_irq_vectors()` readback (MSI enable clear) in a
   distinct teardown PASS/FAIL line.

Avoid coupling this check to IRQ-domain names: numeric hwirqs are the stable
contract under test.

## Interpretation and next research gates

Call this test **H1A: configuration-path validation**, not delivery
validation.  Even a complete pass does not establish:

* DART translation of an actual doorbell transaction;
* electrical AIC edge-versus-level behavior; or
* PCIe port-event interrupt handling.

Those require a separately designed **H1B: delivery-path** experiment, with
its own explicit approval because it must cause a real endpoint-originated
MSI.  Keep the proposed read-only `+0x168` register dump as a separate
diagnostic run: it may refine the register model but cannot close H1A's IRQ
mapping gap or demonstrate delivery.

For any subsequent hardware run, archive the raw console/session transcript
and a manifest containing the source commit, absolute payload store path,
payload size, SHA-256, and the exact command used to load it.  Record the
on-device boot banner/payload hash too if the loader provides one; that is
what upgrades host-side build identity to device-side identity evidence.
