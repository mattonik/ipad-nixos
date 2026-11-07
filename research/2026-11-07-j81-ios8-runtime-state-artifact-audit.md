# J81 iOS 8.1 runtime-state artifact audit

Offline inventory for whether existing files can recover the iOS 8.1 per-PFN
pmap attributes or display/MCC runtime gating state. No device access was
performed.

## Existing evidence

The repository has the original iOS 8.1 (12B410) kernelcache and decoded J81
device tree under `artifacts/live/private/gpu-offline/`. These provide static
code, static property values, and startup/configuration paths. They do not
contain a runtime kernel heap, live page tables, or an iOS 8.1 service-start
trace. `ios81-init-allocation.log`, `ios81-memory-helpers.log`, and the other
`ios81-*.log` files in that directory are Ghidra analysis logs, not captured
device boot logs.

The saved runtime IORegistry export at `artifacts/live/private/j81-ios-ioregistry.json`
is three bytes (`{}`), so it contains no usable registry entries. The
non-empty `j81-ios-syslog.txt` is a Nov. 3 iPadOS 15 session (as independently
identified by the iOS 15.8.5 live-touch capture in
`research/2026-11-03-j81-touch-geometry-and-sync.md`). It is not an iOS 8.1
boot log, and a bounded search found no `AppleMobileADBE0`, `MemCacheState`,
or MCC/display policy records in it. It cannot establish the 12B410 boot
arguments or callback outcome.

The private GPU offline directory contains an iOS 8.1 kernelcache, the
decoded `ios81-dt.bin`/`.json`, carved or disassembled kext material, and
analysis logs. The RAM captures found elsewhere in `artifacts/live/private`
are Wi-Fi firmware captures (e.g. a 1.5 MiB device RAM window), not an
application-processor RAM dump; none is a snapshot from which iOS 8.1 pmap
PTEs or provider heap fields can be recovered. The Nov. 7 live snapshot is a
Linux control boot and contains its own `/proc/iomem`, FDT, sysfs, and dmesg
inventory only.

## What offline evidence can still establish

* For the RGX map, static iOS 8.1 code plus the saved J81 DRAM bounds constrain
  the likely pmap attribute path. The existing analysis in
  `2026-11-07-j81-core-map-provenance.md` distinguishes the device-pager's
  write-combine default from the first fault's WIMG=0 range-based selection.
  This is source-derived and conditional on the saved DRAM bounds matching
  that iOS boot; it is not a runtime PTE observation.
* The saved Apple device tree proves configured DISP0/MCC properties and
  identifies the callbacks; it cannot prove whether ID112 transitioned,
  whether provider `+0x980` was set before GFX, whether `+0x98c` initialized
  successfully, or whether the queued display work completed. Those are
  allocated-object and event-history state, not static DT properties.
* The Nov. 7 Linux control snapshot can classify Linux's current mapping path
  from its RAM ranges and the pinned Linux source. It cannot recover the
  previous iOS mapping or iOS clock-provider history.

An iOS IORegistry snapshot would only help if captured on the relevant iOS
boot and if the provider publishes these private fields as properties; the
static analysis has not found such publication. Ordinary iOS boot/syslog
records are useful only if they contain explicit initialization/transition
diagnostics, which the extant iPadOS 15 syslog does not. A full AP RAM dump
could in principle preserve kernel heap and page-table state, but no such
artifact exists here, and a later boot cannot recreate the earlier state.

## Highest-value next evidence if an iOS runtime capture already exists

Before considering a new hardware session, search its files locally for:

1. An iOS 8.1 boot log or sysdiagnose from the exact boot, including boot-arg
   reporting (`-disable_mcc`) and display/MCC provider initialization errors.
2. A same-boot AP memory snapshot plus its physical-memory map and kernel
   slide, if one was already captured; this is required to interpret pmap and
   heap addresses reliably.
3. A runtime IORegistry export only as a check for published properties; a
   missing property is not evidence the internal field was false.

For display gating, a passive trace or AP memory snapshot must correspond to
the same boot and preserve the provider state/event order; static DT, a later
Linux PMGR word, or a later iOS 15 registry cannot substitute. For the pmap
question, a page-table snapshot must be tied to the exact RGX VA and physical
map generation. Without such same-boot artifacts, the unknown runtime state
is irrecoverable offline and should stay marked unknown.
