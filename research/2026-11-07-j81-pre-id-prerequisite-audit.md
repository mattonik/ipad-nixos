# J81 RGX read hang: remaining pre-identity prerequisites

Offline audit of the 12B410 caller and existing Linux captures. No iPad,
firmware execution, builds, or new MMIO experiments were used.

## What the completed sequence establishes

Test4 reached PMGR state `0x3ff`, applied all 66 selector 9/10 stores,
observed GPC state `1` and control `0x40000000`, and then stalled at the
first RGX identity load (`0x201000020`). The matching Apple caller
`FUN_ffffff80032935a0` performs the provider calls, GPC setup, optional
bit-4 poll and 10-us delay before dispatching identity. The exact G4G vtable
resolves identity to `FUN_ffffff80032933cc` → `FUN_ffffff800328de68`, whose
first mapped-window load is `+0x20`, followed by `+0x18`. There is no hidden
pre-read callback in that identity dispatch.

The test therefore rules out “PMGR state, full bridge tables and the tested
GPC state/control writes are sufficient.” It does not isolate whether the
block is a missing clock/provider side effect, a mapping/access difference,
or a core-internal readiness condition.

## Ranked remaining checks

1. **Linux versus Apple RGX CPU mapping (mechanism differs; PTE type may not).**
   Apple maps `sgx` resource index 0 (`0x201000000`) through
   `mapDeviceMemoryWithIndex(0)` and dereferences the returned CPU virtual
   address. Test4 instead uses `/dev/mem` at that physical address. Existing
   kernelcache/source tracing says Apple's default physical descriptor mode
   resolves to IOKit write-combine at the pager level, while the initial
   device-pager fault passes WIMG 0 and the out-of-DRAM address selects
   AttrIndx 3 (MAIR byte `0x00`). The pinned Linux `/dev/mem` policy selects
   noncached/device protection for non-RAM PFNs, which is broadly consistent,
   but the test4 live PTE, Apple live PTE, and alias policy were not captured.
   The mapping mechanisms and address-space lifetimes definitely differ, but
   this is not yet a proven device-memory-type difference. On ARM64, Linux's
   `MT_DEVICE_nGnRnE` is encoded by MAIR attribute byte `0x00`; Apple's
   recovered initial-fault path selects AttrIndx 3, also byte `0x00` in its
   recovered MAIR_EL1 value. If both source-derived paths describe the actual
   installed PTEs, they select the same Device-nGnRnE transaction type even
   though the AttrIndx numbers differ (Linux normally uses index 0; Apple uses
   index 3 here). This weakens the cacheability mismatch hypothesis. It does
   not prove equal shareability/access bits, absence of aliases, or that no
   later Apple redirect/protection pass changed the mapping. See
   `2026-11-07-j81-core-map-provenance.md` and
   `2026-11-07-j81-devmem-protection-observability.md`.

2. **Apple per-device provider clock transition and state accounting.**
   The original caller invokes provider `+0x560(1,0)` and `+0x568(1,&local,0)`
   before GPC setup. The provider binding resolves these to clock and power
   wrappers with gate ID 124. The clock path may transition PMGR index 100,
   apply selectors 9/10, and increment SoC-busy accounting, but only on a
   reference/tracked-state edge. Test4 reproduced final register values by a
   Linux PMGR cycle and direct stores; it did not reproduce Apple controller
   state or callback history. The power callback is a software
   `WAS_PWRGATED[124]` consume/report operation, not a pre-read power-on
   write. Callback return codes are ignored by the caller. This leaves a
   plausible control-flow/state difference, but no evidence it causes the
   hang. See `2026-11-07-j81-gpc-provider-object-binding.md`,
   `2026-11-07-j81-gfx-clock-reference-startup-audit.md`, and
   `2026-11-07-j81-pre-id-provider-return-gate.md`.

3. **Optional GPC poll and delay fidelity.** Apple sets state `0x11`, polls
   bit 4 clear unless `no-gpc` is present, delays 10 us, then reads RGX.
   J81 has no `no-gpc`; Linux reached state 1 and matching control, but its
   host-mediated test sequence does not establish Apple's precise polling
   and delay interval immediately before the read. The captures do not
   establish that the interval was too short, and this is weaker than the
   mapping/provider discrepancies. The later firmware-object hold routine is
   not the target of the pre-ID accelerator vtable call and is not shown on
   this path. See `2026-11-07-j81-gpc-hold-before-id-boundary.md`.

## Excluded or lower-priority hypotheses

* **DART translation:** the identity access is a CPU mapping of the `sgx`
  resource, not a GPU DMA transaction. The saved J81 `sgx` node has no GPU
  IOMMU parent/SID binding. DART is not an evidenced prerequisite for this
  CPU load.
* **GPC hold/state-zero cleanup:** Apple's state-zero and conditional provider
  release happen only after the identity method returns. The firmware hold
  sequence belongs to a separate object/vtable and is not statically placed
  before this read.
* **A further explicit RGX core setup write:** the recovered Apple pre-ID
  path contains no such write between provider calls/GPC setup and the ID
  matcher. This does not rule out effects hidden inside the unresolved
  provider callbacks or hardware-internal sequencing.
* **Display/MCC:** it remains a conditional part of SoC-busy accounting, but
  its gates/callbacks are already extensively traced. Runtime gates and
  callback results remain unknown; no evidence supports elevating it above
  the map/provider gaps.

## Recommended offline priority and limits

The source-level protection policies now appear to converge on MAIR byte
`0x00` for the initial non-RAM mappings, so further cache-mode speculation is
lower priority. An offline-only comparison should verify the exact pinned
Linux arm64 `pgprot_noncached()` definition and its selected MAIR slot against
the recovered Apple descriptor bits; this can settle the architecture-level
memory type without touching the device. Existing test4 evidence lacks a
same-boot `/proc/iomem` snapshot, so it cannot prove that its PFN took the
non-RAM branch. A future map-only observation can safely record `/proc/iomem`,
the runtime FDT memory ranges, `/proc/self/maps`, and the `pagemap` PFN for a
read-only `/dev/mem` mapping without dereferencing the GPU. That would verify
PFN classification/presence, not AttrIndx or shareability. `smaps` and
`pagemap` do not expose ARM64 memory attributes; this kernel configuration
does not enable `PTDUMP_DEBUGFS`. Direct PTE evidence would need an explicit
kernel-side diagnostic and is not justified as a next step. In parallel,
inspect the exact iOS 8.1 provider runtime class/callback side effects and
whether static consumers can establish the PMGR clock edge before G4G. Do not
infer that matching readbacks mean the Apple software transition ran. No
existing evidence supports another RGX read or a new register sequence as a
safe discriminator.

Evidence anchors: `artifacts/live/private/gpu-offline/ios81-agx-disasm.txt`
(`32935a0`, `32933cc`, `328de68`); `boot/gpu-core-revision-once.c`;
`research/2026-11-07-j81-core-revision-after-clock-test4.md`;
`research/2026-11-07-j81-core-map-provenance.md`; and the provider/callback
notes cited above.
