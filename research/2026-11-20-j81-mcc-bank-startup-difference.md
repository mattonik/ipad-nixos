# J81 startup writer for PMGR +0x22000 bit 31

**ApplePMGR requests the set before the successful observation point.** On the 19H394 J81 startup path, the parent calls instance slot +0x688 with enable=1 at 0x6bccf3c. The J81 method at 0x6c8a0c4 walks 19 region-0 words and issues a 32-bit read/modify/write. The first is physical 0x20e022000. Its request is `(old & 0x7fffffff) | 0x80000000`. The ordinary-writer capture contains the exact request 0x80000000 at that offset. A subsequent iPadOS experiment read 0x80000000 both before and after GPC. These are independent boots. The meaning of bit 31 for GPU access remains unverified. [Startup call chain](2026-11-19-j81-pmgr-start-resources.md) · [Capture and formatter limits](2026-11-17-j81-ios-g4g-ordinary-pmgr-store-capture.md)

The loop constructs its starting offset by 32-bit addition of 0xfffde000 and 0x44000. Searching the binary for a literal 0x22000 misses it. It advances in steps of 0x10 through +0x22180, skipping +0x22030 through +0x22070 and +0x22120. The older 24-byte record hypothesis resolves elsewhere. Group zero is registered with base +0x10218 at 0x6c884dc–84ec. The four lanes at 0x6bcf280 address +0x10218 through +0x10224; the following 0x40000000 argument is a polling mask. [Code: 19H394 J81 PMGR, VA suffixes with prefix 0xfffffff000000000.]

| Region-0 offset | iPadOS captured store request | Fresh Linux read | Independent iPadOS read |
|---|---:|---:|---:|
| +0x22000 | 0x80000000 | 0x00000000 | 0x80000000 |
| +0x22090 | 0x89070300 | 0x09070300 | unknown |
| +0x220a0 | 0x89040300 | 0x09040300 | unknown |
| +0x220b0 | 0x89060300 | 0x09060300 | unknown |
| +0x22130 | 0x89040300 | 0x09040300 | unknown |

**Observed:** The other fourteen requests equal the corresponding Linux words in full. All 19 match the result of applying the stock enable transform to the Linux dump. Source comparison uses the raw region-zero ordinary requests in the November 17 store-slice kernel.log and all 256 PMGR words from Linux boot 83536afb. The formatter supplies a synthetic instance tag. The capture identifies the requests; the code determines the startup caller and instance. The fresh Linux dump precedes a GFX request.

**Cross-boot limit:** Working iPadOS read +0x22000 in boot B6FF1EED with page 5 high and Fender +0 equal to 0x40000000. That boot's CORE field is CPU TVM. The separate p22 boot 88D929A0 returned GPU-ID 0x00070500 and measured adjacent words, without resampling +0x22000. No single captured row establishes a causal relation between the bank and GPU-ID.

**Next observation:** Read the five offsets in the table pre-GPC and post-GPC on both systems, preserving the unmasked words, page-5 value and boot ID. Include the actual GPU-ID result when independently available on that boot. This distinguishes a persistent five-word difference from a requested enable that already matches Linux at the time of access. The control bank is MCC/clock-related and its GPU dependence is unknown. There is no need for a write experiment to answer that comparison.
