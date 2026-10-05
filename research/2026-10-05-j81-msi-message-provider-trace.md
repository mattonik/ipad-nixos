# iOS 8.1 `AppleEmbeddedPCIE`: where the MSI message address comes from

Date: 2026-10-05. Static research on the pinned iPad5,3 12B410 kernelcache (`__PRELINK_TEXT`
imported flat at `0xffffff8002593000`); no hardware. Prompted by the `+0x168 == 0` result
(design note section 14): is `0xbffff000` passed straight into endpoint MSI composition, or does
the controller need a T7000-specific setup first?

## Answer

**It is passed straight through.** The controller object just returns the ADT `msi-address`
value as the endpoint's MSI address. No controller register holds or supplies it, which is why
iOS never writes `+0x168` and why it reads 0 on hardware.

## The data flow (function entries are kernelcache addresses)

1. `FUN_ffffff8002beb264` (`AppleEmbeddedPCIE::start`) reads `msi-address` (8 bytes) into the
   controller object at `+0xc8`, `msi-crypto-address` into `+0xd0`, `#msi-vectors` into `+0xd8`,
   `msi-vector-offset` into `+0xdc`, and builds the MSI child controller (below) at `+0xe0`.
2. `FUN_ffffff8002bec704` is the controller's platform-function handler (found only by
   brute-force ADR scan; Ghidra had no function there). For the function name
   `GetMessagedInterruptAddress` it fills the caller's message structure with:
   - address = controller `+0xc8` (`msi-address`), **or** `+0xd0` (`msi-crypto-address`) when the
     requesting device has the property `crypto-queue-msi` (and panics if that address is 0);
   - data = the vector number the caller passed in (`param_6`).
   For `GetMessagedInterruptController` it returns the MSI child controller at `+0xe0`.
3. `ApplePCIEMSIController` (`FUN_ffffff8002bea53c` init, `FUN_ffffff8002bea6a8` allocate,
   `FUN_ffffff8002bea8e4` handler) is a plain vector table: `numVectors` slots indexed by
   `aicVector - msi-vector-offset`. It never touches `msi-address`.
4. Each port allocates its vectors from its own range allocator initialised with
   `(msi-vector-base, #msi-vectors)` (decompile around the `+0x188/+0x18c` port fields). The
   vector numbers handed out, and therefore the message data, are **absolute** (port 1: 8..15),
   the same `base | base<<16` window the port-tail MSI write programs.

## What this settles and what it does not

- Our `0057` composition (address `0xbffff000`, data = absolute slot 8..15, parent AIC
  `224 + slot`) is exactly Apple's. The H1A readback matches it.
- Reading 1 of the design note (`+0x168` is the doorbell register) is now unlikely on T7000:
  nothing in the driver stores the address in any controller register, in either the `msi-address`
  or the crypto path.
- Still open (hardware question, not answerable from this code): how the controller/fabric
  recognises a write to `0xbffff000`. Either the decode is fixed in hardware (reading 2), or some
  earlier stage sets it up (firmware/iBoot or a register in a window iOS writes through code we
  have not traced, reading 3). The static evidence only shows it is not programmed by the PCIe
  kext's own MSI path.
- The earlier note's possible reading about `msi-crypto-address` is closed: it is used only for
  devices tagged `crypto-queue-msi` (not the Wi-Fi endpoint).

## Suggested next steps

1. Treat `+0x168` as not the T7000 doorbell register; do not write it.
2. The remaining unknown is the fabric/DART side (design U1). A delivery test needs a real
   endpoint MSI (firmware gate); no cheaper experiment exists.
3. If someone wants more static evidence first: look for code that maps or whitelists the
   address `0xbffff000` in the DART/IOMMU-side kexts (`AppleS5L8960XDART`), which is where an
   inbound-write exception would live.

Method note: the strings `crypto-queue-msi` / `requesting crpto msi` showed no Ghidra xrefs with
`-noanalysis`; these kexts reference strings with `ADR`, not `ADRP`. `tools/ghidra/find_adr_refs.py`
plus `MakeFuncDecomp.java` recover such code.
