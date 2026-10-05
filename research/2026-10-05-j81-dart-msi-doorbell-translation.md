# J81 DART and PCIe MSI-doorbell translation contract

Status: research handoff; this note contains no payload build or hardware run.

## Result

The existing `IOMMU_RESV_MSI` change is the correct Linux-side representation
of the J81 PCIe MSI doorbell.  It reserves `0xbffff000` as a hardware MSI
region, and generic IOMMU-DMA retains an identical IOVA and physical address
for that region.  It should not be replaced with a guessed normal IOVA mapping
or an arbitrary DART PTE.

This proves an allocator/address-model property only.  It does **not** prove
that a real J81 endpoint write reaches APCIe, bypasses or traverses DART in the
expected way, or creates an AIC interrupt.

## Exact code-path findings

In pinned Hoolock source `6831bc701a6ce059e71e5aaa9488c9195bea6927`:

* `IOMMU_RESV_MSI` is documented as a hardware MSI region that is
  untranslated.
* IOMMU-DMA reserves all non-software-MSI regions from ordinary IOVA
  allocation.
* For a hardware MSI region it records an MSI page with `phys = start` and
  `iova = start`.
* The normal MSI-page lookup consequently finds the existing page for
  `0xbffff000`; it does not allocate an unrelated IOVA or create a normal DMA
  mapping for that address.

Those generic semantics are visible in [the IOMMU interface](https://github.com/torvalds/linux/blob/master/include/linux/iommu.h)
and [IOMMU-DMA implementation](https://github.com/torvalds/linux/blob/master/drivers/iommu/dma-iommu.c).

Project patch `0055` supplies that region from the DART reserved-region hook,
using the J81 ADT's `apple,msi-doorbell = <0 0xbffff000>`.  The earlier hardware
record showed it as `0xbffff000...bfffffff msi`, replacing the pre-patch
fallback `0xfffff000`.  Patch `0057` independently composes that same address
into PCI MSI messages.  The two layers therefore agree on the only currently
evidenced address.

Apple DART's ordinary translated domain still uses IO page tables.  Patch 0055
does not introduce a special `0xbffff000` PTE, and none should be invented
without evidence.  The reserved region expresses the expected hardware MSI
exception rather than proving where the fabric consumes the write.

## Required next diagnostic: read APCIe +0x168

Before any actual endpoint-delivery attempt, add a standalone read-only
diagnostic which records APCIe offset `+0x168` after the established normal
controller initialization.  Current upstream labels this register
`PORT_MSIADDR` and programs its controller doorbell; the iOS 8 J81 path did
not write it in the recovered trace.  The read has high discriminating value:

* `0xbffff000` makes a later endpoint delivery experiment substantially more
  interpretable;
* zero or another address stops the delivery plan for further research;
* no write to `+0x168` is authorized by this diagnostic.

The log must include the controller base, exact offset, width, value, payload
run identity, and raw boot transcript reference.  A one-off print without
those bindings is not sufficient evidence.

## Delivery experiment acceptance contract (later)

A future H2 test can claim PCIe MSI delivery only if a single retained run
shows all of the following:

1. the exact uploaded payload identity is bound to an on-device boot token;
2. `+0x168` and endpoint MSI config show the expected message address and a
   data value in the BCM4350 allocation (8--15);
3. the IRQ hierarchy resolves numerically as PCI slot `n` -> AIC `224+n`;
4. a real, controlled endpoint event causes the expected leaf IRQ and AIC
   observation;
5. DART fault/error state and APCIe port status are captured before and after;
6. teardown disables endpoint MSI and leaves no unexpected DART or port error.

H1/H1A allocation self-tests meet none of item 4 and must remain labelled
configuration-path tests.  They set up and tear down endpoint MSI state but
do not cause an endpoint-originated doorbell write.

## Open questions

The actual fabric point at which the hardware MSI write is consumed (before
or after DART), the interrupt electrical semantics observed by AIC, and port
error-event handling are all unresolved.  Nothing in a successful IOVA
reservation or `pci_alloc_irq_vectors()` call answers them.
