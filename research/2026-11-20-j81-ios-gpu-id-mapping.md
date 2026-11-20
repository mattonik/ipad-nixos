# J81 iPadOS mapping for the successful GPU-ID read

The 19H394 runner capture for boot 846527FB-1D2B-4834-AEB8-49480323BBFD contains three page-5 samples of 0x40000000, the before-read checkpoint and GPU-ID 0x00070500 in that order. This was the research observer running in kernel context during startup. The boot therefore demonstrates a working CPU-to-GPU register transaction at that point. [Boot comparison](2026-11-19-j81-page5-high-core-stall.md)

## What the machine code establishes

In the returned module disassembly, 0x4478 branches on bit 30. At 0x4490–0x44a4 the probe calls its mapper via literal slot 0x46f0 with X0=0x201000000 and X1=0x1000. This length is the request size. The kernel rounds the mapping to its translation granule. The null-return branch skips the read. The successful path emits the before-read checkpoint and passes the returned VA + 0x20 to the helper at 0x45c4. The helper executes a naturally aligned 32-bit LDR followed by DSB SY. It performs a CPU load with a completion barrier. The three page-5 samples precede allocation of the core mapping.

The probe design identifies the mapper as the stock exported ml_io_map. The returned module independently confirms the target. Code at 0x5cb4–0x5cc4 constructs unslid 0xfffffff00728fa34, adds the runtime adjustment and saves the pointer. Code at 0x5cf0–0x5d08 supplies those eight bytes for the literal at module offset 0x46f0. In the exact decompressed 19H394 kernel the symbol at 0xfffffff00728fa34 loads 7 into W2, loads 3 into W3 and branches to 0xfffffff007288ffc. The latter preserves both arguments and its kernel-map branch forwards 3 as protection and 7 as the mapping attribute at 0xfffffff00728909c–0xfffffff0072890a4. This corresponds to read/write and VM_WIMG_IO. The module's indirect call site and the named kernel wrapper can be checked separately. The returned boot log supplies neither the resolved function pointer nor the returned virtual address. [Probe design](2026-11-14-j81-ios-boot-bisect-probe1-design.md)

## Expected memory type

The exact 19H394 executable identifies itself as xnu-8020.241.42~8. The late kernel-map path at 0xfffffff0072709e0 passes protection in X3 and WIMG in X5 for each rounded page. At 0xfffffff007270e3c–0e54 the entry path retains the upper bits of the existing attributes and replaces the low byte with the nonzero explicit WIMG. A second path at 0xfffffff007271200 branches directly to the conversion for a nonzero explicit value. Thus range metadata can affect other flags. The WIMG converter itself uses only the low byte; strong-sync metadata about TLB maintenance cannot turn that 7 into a different MAIR index here. The early VM-bootstrap branch in io_map uses a separate mapping helper. ApplePMGR startup is in the running kernel, and no log captured that internal branch.

The converter at 0xfffffff007270918 indexes the byte table at 0xfffffff0070096fd by WIMG minus two. For 7, the byte at kernel file offset 0x5702 is 4, selecting 0xfffffff007270958. That case checks whether the unsigned physical address minus the DRAM base is below the DRAM size. For the J81 GPU register aperture outside DRAM it returns 0x006000000000000c, giving leaf AttrIndx 3. For an in-DRAM address it adds 0x10, giving index 7. The stock MAIR initialization at 0xfffffff00713729c–0xfffffff0071372e0 writes 0x0c08044f00bb44ff to MAIR_EL1. Byte 3 is zero, the architectural encoding for **Device-nGnRnE**. These are the shipped kernel's selections under the stated path and physical classification. They do not require assuming the deployed build matches a public XNU tag. The successful capture contains no live leaf or MAIR readback.

Public Apple XNU 8020.140.41 independently documents the wrapper, the non-DRAM selection and MAIR encoding. [Apple mapper](https://github.com/apple-oss-distributions/xnu/blob/27b03b360a988dfd3dfdf34262bb0042026747cc/osfmk/arm64/machine_routines.c#L1439-L1444) · [Apple pmap selection](https://github.com/apple-oss-distributions/xnu/blob/27b03b360a988dfd3dfdf34262bb0042026747cc/osfmk/arm/pmap.c#L5793-L5805) · [Apple MAIR and slot definitions](https://github.com/apple-oss-distributions/xnu/blob/27b03b360a988dfd3dfdf34262bb0042026747cc/osfmk/arm64/proc_reg.h#L839-L863)

## Offline cross-check

In the private 2026-11-19-j81-ios-pregpc-miscacg-run-result packet, verify SHA256SUMS and inspect evidence/probe-module-full.dis around 0x4478, 0x4490, 0x44cc and 0x45c4. Match the ordered markers in evidence/new-boot-j81-boot-records.ndjson. On the decompressed kernel used by the PMGR audit, run:

```sh
xcrun llvm-objdump -d --start-address=0xfffffff00728fa34 --stop-address=0xfffffff00728fa40 "$KERNEL"
xcrun llvm-objdump -d --start-address=0xfffffff007270918 --stop-address=0xfffffff00727097c "$KERNEL"
od -An -tx1 -j 22274 -N 1 "$KERNEL"  # case byte at 0x5702
xcrun llvm-objdump -d --start-address=0xfffffff00713729c --stop-address=0xfffffff0071372e8 "$KERNEL"
xcrun llvm-objdump -d --start-address=0xfffffff007288ffc --stop-address=0xfffffff007289110 "$KERNEL"
```

The successful records omit the actual leaf entry, output PA, shareability and MAIR_EL1. Mapping permission and kernel privilege differ from a read-only Linux user VMA. Their presence alone gives no measurement of the transaction reaching the GPU. An archived translation record would distinguish an unexpected output address or effective memory type while avoiding another GPU-ID load.
