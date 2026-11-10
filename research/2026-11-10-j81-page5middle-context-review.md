# J81 intermediate probe: static context and preservation review

Offline review, no hardware access. This is a review of the experimental
[probe](probes/j81-page5middle/README.md), not an independent review or a
claim of hardware safety.

The earlier inspected 19H422-associated AGX startup path calls the clock and
power providers, then reaches the GPC read and poll at `0xfffffff00668399c`–
`0xfffffff0066839a0`; the hook replaces the conditional branch. The power
provider call has returned before the poll, so this direct call site is not
inside that provider call. The local sequence does not establish whether an
outer caller holds a lock or whether an interrupt or other thread can affect
this state. Exact KPF signatures and UUID guard the 19H394 target.

Static analysis of the 19H422-associated AppleT7001PMGR instance constructor
installs vtable `0xfffffff006fe5e28`; its `+0x980` entry is
`0xfffffff006bd0478`. The successful path checks instance and offset bounds,
uses `bd0258` and `bc75e4` for region metadata, then performs a 32-bit load
from the mapped region and returns. No lock acquisition or command-gate call
is visible on this successful path or in those two helpers. Error paths call
panic helpers. The 120-byte read-method span and the 88- and 64-byte helper
bodies each have one byte-identical match in the 19H394 kernel. This supports
the non-blocking direct-read interpretation **if** the captured object's
runtime vtable is this class and its mapping is valid. Neither condition nor
the external lock context has been measured. MMIO itself may stall or have
side effects.

The saved assembly first preserves the original GPC busy branch. On the clear
path it allocates 0x340 bytes, saves/restores x0–x30, q0–q31, NZCV, FPCR and
FPSR, and restores the stack before the original success continuation. The
one-shot PMGR read occurs only with a matching nonzero thread, a saved PMGR
context, IRQs enabled and a clear busy bit. Its result is published before a
ready flag and printed only at the later identity hook. A static layout check
and native ARM64 simulations cover matched save/restore locations, branches,
flags on skips and one-shot behavior. The simulations do not prove that the
kernel stack has enough headroom, that FP/SIMD accesses are enabled in this
context, that the captured object remains alive, or that all registers remain
unchanged across the real call. The extra stack and SIMD use are materially
larger than the original poll hook. IRQ-enabled alone is not a lock test.

This review does not establish readiness for a device run. Before a hardware run, review the
kernel FP/SIMD context and stack headroom, verify the runtime object/mapping
if possible, and consider reducing the hook to the minimum ABI-required save
set or using an explicitly reviewed alternative. A stalled middle read may
prevent both its buffered result and later logs from being recorded.

Private static output: `artifacts/live/private/gpu-offline/j81-page5middle-review/`.

## Reduced-middle variant

A subsequent [reduced variant](probes/j81-page5min/README.md) saves general
registers and NZCV in 0x140 rather than 0x340 bytes and uses no SIMD or FP
instructions at the middle hook. It skips the read unless the actual method
pointer equals the known KASLR-adjusted direct-read function. This reduces
reliance on unknown dynamic method behavior; it does not establish object
lifetime, mapping validity, outer lock state, stack headroom or MMIO safety.
The older early and late hooks still use SIMD and were unchanged. Host tests
passed, including the method-mismatch skip; no device run was performed.
