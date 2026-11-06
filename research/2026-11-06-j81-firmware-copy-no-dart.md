# J81 firmware copy path has no DART operation

Decompiling `0xffffff800329fbe8` (`ios81-fw-copy.c`) shows the AGX LDR
consumer walking records from the packed image. For type-0 records it selects
one of four parsed view ranges, computes `image_offset - view_start + view_base`,
then copies bytes through the host mapped pointer returned by the preparation
object and compares them byte-for-byte. Type-4 records clear a host range;
type-5 records append metadata.

There are no GPU MMIO writes, DART table writes, stream IDs, or DMA descriptors
in this routine. The preparation object is therefore a CPU-visible transport
buffer; the four `+0x210` registrations are address-view metadata consumed by
the accelerator object, not proof that the LDR copy uses a GPU IOVA.

This does not prove that later command submission bypasses translation, but it
removes the firmware loader as a candidate for discovering the missing DART
aperture. The next static target is the first post-LDR boot/doorbell routine.
