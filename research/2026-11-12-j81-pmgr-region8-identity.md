# J81 PMGR region 8: CPU performance-control evidence

Offline analysis of the local 19H394 kernelcache, prior live iOS registry
snapshot, and the upstream Linux A8 device tree and CPU-frequency driver.
No device access, MMIO operation or new boot.

## Names in the 19H394 PMGR template

The 19H394 `__PLK_DATA_CONST` template at `0xfffffff006fcebf8` is copied
into the PMGR object at `+0xa58` by the inspected constructor. It has
`0x50`-byte region records. The first pointer in record 0 resolves to the
string `PMGR`; the first pointer in record 8 resolves to `ACC_PWRCTL`.
The static records' remaining words are initially zero; these names are
evidence of intended roles, not the initialized runtime mapping bases.

The existing T7001 PMGR trace shows the region-8 path reading `+0x50`
bits `[5:3]` and using 64-bit accesses at `+0x20` with bit 25 and bits
`[24:22]` when requesting a state. The public Linux
[T7000 device tree](https://github.com/torvalds/linux/blob/master/arch/arm64/boot/dts/apple/t7000.dtsi)
identifies physical `0x202220000` as a CPU cluster performance controller;
the [CPU-frequency driver](https://github.com/torvalds/linux/blob/master/drivers/cpufreq/apple-soc-cpufreq.c)
uses the same status and command offsets and fields for that controller.
The previously captured live iPadOS J81 PMGR provider exposes a resource
at `0x202220000` as well as the PMGR aperture at `0x20e000000`.

Together, the names, matching access pattern and physical resource are
strong evidence that region 8 corresponds to the CPU performance-control
block and region 0 to PMGR. They do **not** directly show which physical
address the active 19H394 PMGR object installed in each region-table entry,
or prove that its mapping has no alias. The reference Linux tree is T7000;
the register behavior is a cross-chip comparison, not proof about every
J81 runtime state.

## Effect on the page-5 hypothesis

The 64-bit writer calls through the T7001 linkage thunk use region 8. The
fixed callers touch low offsets consistent with CPU performance control;
the inspected variable-offset path is constrained below `0x1000`. The
observed page-5 word is at region-0 offset `0x5004`. This substantially
reduces the priority of a new DFU cycle to trace those specific T7001
64-bit calls. It does not rule out a different caller, an alias, another
store width, firmware, or hardware setting bit 30. It does not identify why
the Linux GPU core read failed.

To establish the region-to-physical mapping directly, trace initialization
of the region entries or compare their descriptors on a live device;
avoid adding a device boot just to reconfirm the region names. A useful
next GPU experiment still needs a specific prerequisite that iPadOS has
and Linux lacks, with a result that changes what to test next.

Evidence: 19H394 local kernel SHA-256
`c3507666766775dc854d5bcf6c375e6651ac8b2d1adb13d06331c60deb6a0008`,
private `ios15pmgr-ctor.c`, `ios15t7001pmgr.c`, and
`ios-registry-runtime-20261111/pmgr.plist`, plus
[the 64-bit caller follow-up](2026-11-12-j81-store64-callers-followup.md).
