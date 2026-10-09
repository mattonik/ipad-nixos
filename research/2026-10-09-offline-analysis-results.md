# Wi-Fi H1B offline analysis results (2026-10-09)

Static-only follow-up to the H1B handoff. No build, device access, or private
asset is included here.

## 1. DART: Apple startup/recovery is not Linux reset

The earlier iOS 8.1 trace around `AppleS5L8960XDART::_dartRecoverFromPowerdown`
(`0xffffff80026c5d40`) is the useful comparison. For the J81 `dart-apcie1`
properties, Apple performs this order:

1. write `error-reflector >> 12` to DART `+0x24` (`0x0020ffff` for the
   captured property);
2. restore the cached translation/configuration state, including TCR
   (`+0x0c`), `fetch-config` (`+0x30`), `diag-config` (`+0x20`), and the
   auxiliary `+0x1000` configuration;
3. clear and poll the TLB operation.

The normal Linux `apple_dart_hw_reset()` path starts by reading DART `+0x00`
and does not perform the Apple write-first recovery sequence. The Linux
driver does otherwise program the expected TCR/TTBR tables and invalidate
operations. `vm-offset`/`vm-size` are allocator/page-index inputs, not a
second hardware doorbell map. The endpoint remains mapped to stream 0 by the
existing RID mapping; stream 1 is the null table.

This makes the Apple recovery ordering a credible *test hypothesis*, but it
does not prove that it explains the H1B reset: the observed pre-reset DART
error state stayed unchanged and no translation fault was logged.

## 2. PCIe controller: no extra DMA transaction was found

The existing Apple `AppleT7000PCIe`/`AppleEmbeddedPCIE` trace, including the
post-link path and shared/port windows, contains no discovered inbound ATU,
DMA-engine, or bus-master programming that is absent from the current Linux
controller setup. The recovered writes are link/port tunables, interrupt/MSI
delivery, and the documented mailbox/core accesses. MSI success only proves
the port's MSI delivery path; it does not prove endpoint DMA routing.

Therefore the PCIe-controller hypothesis remains open, but static work has
not identified a safe single register to add. Do not invent a write to the
unidentified port `+0x168`.

## 3. Linux RX posting path: one mapping path plus ring/doorbell writes

In the patched H1B source (`msgbuf.c`, `brcmf_msgbuf_rxbuf_data_post`): each
buffer is allocated, passed through `dma_map_single(..., DMA_FROM_DEVICE)`,
and its returned 64-bit address is copied into the RXPOST descriptor. The
common-ring code only reserves, zeroes/fills, and commits descriptors. The
ring callback writes the producer index and `brcmf_pcie_ring_mb_ring_bell`
writes `1` to `h2d_mailbox_0` (`PCIe2 +0x140`). There is no explicit
`dma_sync_*`, physical-address cache flush, IOMMU API call, or second MMIO
doorbell in this path. `dma_unmap_single` occurs only on allocation failure,
completion, or teardown.

This narrows the reset trigger to one of: DART mapping/translation, the
firmware consuming the first RXPOST descriptor, or a device-side power/PHY
transition caused by that consumption. It is not a hidden Linux cache or
extra-register operation.

## 4. Firmware-side analysis status

The visible C2 image is a ROM-based `splitrx` build. The PCIe msgbuf event
dispatcher and ring names are in the RAM patch, but the code that consumes
RXPOST entries and forms PCIe DMA transactions is in the chip ROM. The
available static image therefore cannot establish the exact first RX DMA
address formation or whether radio power starts at that point. This remains
blocked on the private ROM/live-RAM Ghidra workspace; no conclusion is drawn
from absence of code in the RAM patch.

## 5. Reset-cause analysis status

The iOS kernelcache confirms separate watchdog drivers (`AppleARMWatchDogTimer`
and `AppleS5L8960XWatchDogTimer`) and the `AppleD2207PMU` driver, but the
stripped 8.1 kernelcache strings do not expose a named reset-reason/fault
register map. The D2207 kext strings identify GPIO/LDO/ADC/watchdog services,
not a portable event-register name or bit table. Consequently, no read-only
offset is safe to add based on this pass alone; guessing PMU or PMGR offsets
would repeat the earlier unsafe-register mistake.

The high-value next static step is targeted disassembly of the watchdog/PMU
boot and interrupt handlers (or a symbol-bearing matching kext), looking for
the first I2C register reads and SoC reset-status MMIO reads. Until that is
found, reset classification requires a deliberately narrow, evidence-backed
read list—not a register sweep.

## Ranked next actions

1. Run the already assembled `D13-feed0` payload: it separates “any RXPOST
   buffer causes reset” from “only the first control/ring transaction causes
   reset”, without a build.
2. Run `D13-rxpost1`: one mapped RX buffer distinguishes mapping/first-DMA
   effects from a bulk-posting or descriptor-count effect.
3. If either survives, add progress markers around the first few RXPOST
   descriptors and capture DART error state before/after each mapping.
4. If both reset, use the Apple DART write-first recovery sequence only as an
   isolated, boot-argument-gated coding-agent experiment; it is not justified
   as a permanent change yet.
5. Continue reset-cause disassembly before adding any PMU/PMGR read command.

