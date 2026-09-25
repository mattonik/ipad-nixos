# J81 internal storage: ANS1 bring-up evidence audit

**Audit date:** 2026-09-25

**Scope:** offline analysis only; no payload was built, no hardware was touched,
and no command was sent to the iPad during this audit.

## Conclusion

J81 does not expose its internal NAND as raw flash, an MTD device, a standard
NVMe controller, or a PCIe endpoint. It has Apple's first-generation ANS
storage processor (called **ANS1** or **ASP** in the available code). The
application processor exchanges proprietary 4 KiB logical-block commands with
firmware running on that coprocessor. RTKit provides the management channel,
an AKF v1 mailbox carries notifications, and a shared DMA command buffer holds
the requests and scatter/gather lists.

The only Linux implementation for this hardware remains the experimental
Hoolock `ans1` work. Mainline's `nvme-apple` driver supports the later ANS2
design and is not a driver for J81. The local project has already reconciled
the ANS1 work into an isolated payload and hardened it against writes. A
recorded 2026-09-13 test on this J81 reached the real firmware, registered all
ten exposed namespaces read-only, and completed one 4 KiB user-area read to
`/dev/null` without an error.

No separately described DART sits in the observed J81 ANS path. The captured
Apple Device Tree (ADT), the experimental Linux binding, and its driver all
lack an ANS IOMMU/DART attachment. This is narrower than saying that the
storage processor has no internal address translation or protection. What the
evidence establishes is that Linux does not need to configure an external
DART before using this inherited ANS1 firmware instance.

The safest repeat probe is therefore the existing two-stage procedure in the
isolated, write-hardened RAM-root payload: inspect probe logs and verify
`ro=1` on every namespace first; only if all checks pass, recheck the user-area
flag and read exactly one aligned 4096-byte block to `/dev/null`. Do not use the
unmodified Hoolock branch for this, because that source sends `WRITE_UNLOCK`
unconditionally during probe.

## Evidence standard

This report uses three labels:

- **Confirmed:** directly present in the captured J81 ADT, source code,
  disassembly/decompilation, or the project's recorded hardware transcript.
- **Inference:** the most likely explanation supported by several confirmed
  facts, but not directly demonstrated.
- **Unknown:** evidence is insufficient; a later experiment or more reverse
  engineering is required.

The private capture inspected here is
`artifacts/adt/20260908T082112Z-j81.adt` (357,402 bytes, SHA-256
`cf743765e66a1a5b45cbf4e18c0e5ae21454bb1cb678b66e7007e2db04f5b6c2`).
It stays ignored and is not reproduced in this report. Per-device identifiers,
calibration data, and firmware contents are omitted.

## Confirmed controller and protocol

| Layer | Confirmed J81 behavior | Evidence |
|---|---|---|
| Hardware block | `/arm-io/ans` identifies as `iop,s5l8960x`, with an `iop-ans-nub` RTBuddy child | Captured J81 ADT |
| Firmware ownership | The ANS child is marked `pre-loaded`, `running`, `power-managed`, and `no-shutdown` | Captured J81 ADT |
| AP transport | RTKit management plus a 64-bit AKF mailbox and a shared DMA command buffer | Hoolock binding and `drivers/block/asp.c` in [patch 0015](../kernel/patches/0015-ans1-storage-driver-and-core-support.patch) |
| Storage protocol | Proprietary ASP commands, not NVMe commands | Hoolock ASP driver and the iOS `ASPSupportNodes` implementation |
| Logical block | 4096 bytes | `ASP_LBA_SHIFT = 12` and `ASP_LBA_SIZE = 4096` in the ASP driver |
| Request storage | 16 tags, each 16,320 bytes; 261,120-byte coherent queue | ASP driver constants and queue allocation |
| DMA description | Request SGL entries contain 4 KiB page numbers derived from DMA addresses; the driver requests a 40-bit DMA mask | ASP driver |
| Public disks | One user area plus LLB, firmware, util-DM, DM, control-bits, effaceable, NVRAM, sysconfig, and panic-log auxiliary areas | ASP command table, iOS class names, and recorded Linux enumeration |

The mailbox protocol sends four message types: set command-buffer address,
set tag offset, submit, and complete. Startup waits for two reserved completion
tags (`READY`, then `CMDBUF_OK`) before normal commands can run. The RTKit
application endpoint depends on the firmware protocol version: endpoint `0x5`
for early 10.x firmware, `0x6` for 10.2 and later 10.x, and `0x20` otherwise.

The command set independently corroborates the architecture. It includes
identify (`0x00`), user read (`0x10`), user write (`0x11`), flush (`0x13`),
format-related commands (`0x15`, `0x16`, `0x18`), and write unlock (`0x19`).
Separate read and write opcodes address each auxiliary area. This is a managed
flash interface: NAND geometry, ECC, bad-block handling, and the flash
translation layer remain behind ANS firmware rather than appearing as Linux
raw-NAND operations.

The iOS 8.1 J81 kernelcache provides an independent implementation. Read-only
Ghidra inspection of the `com.apple.driver.ASPSupportNodes` region found:

- classes for the user block device and the same auxiliary regions;
- an `ASP_PROTOCOL_VERSION` check and rejection of non-4K segments;
- a `SetWritable` path that constructs command `0x19`, matching Linux's
  `ASP_CMD_WRITE_UNLOCK` value;
- a `nand-readonly` boot argument and `ASPIsReadOnly` decision path;
- `nand-enable-reformat`, disabled by default in the inspected startup path;
- timeout, sleep, and power-gating handlers;
- an `ASPSEPNotifier`/`ASPNotifySEPState` path.

This confirms that read-only policy and an explicit unlock operation are part
of Apple's own interface. It also confirms that SEP state is relevant to some
ASP behavior. It does **not** establish that SEP participation is required for
every raw logical-block read: the recorded Linux probe completed one such read
without a Linux SEP storage integration.

## Boot-chain constraints

The usable path is an inherited-firmware path:

1. iBoot loads and starts the ANS RTBuddy firmware.
2. The exploit/Pongo stage and m1n1 must preserve that running instance and
   the memory containing its firmware.
3. Hoolock m1n1 reads the ANS firmware region from the ADT, reserves it in the
   Linux FDT as `ans-firmware`, and associates it with the ASP node.
4. The Linux ASP driver programs the AKF firmware remap window, starts or
   releases the coprocessor through the ANS control interface, performs the
   RTKit/AKF handshake, and installs the shared command queue.
5. Only after `READY`, command-buffer acknowledgement, and identify succeed
   does Linux register block devices.

The relevant m1n1 handoff is Hoolock commit
[`9d53672`](https://github.com/HoolockLinux/m1n1/commit/9d53672dbf5f41577aaa182284f68d06614e2dcf),
which explicitly says the firmware was loaded by iBoot but was not mapped into
the coprocessor's physical address space. The board DT side of the experimental
kernel consumes that loader-filled reserved-memory region.

There is no firmware loader or known clean recovery path in the Linux driver.
Its crash handler states that recovery requires a reboot, and timeout recovery
is disabled because the preceding boot stage supplied the firmware. These are
hard bring-up constraints:

- ANS cannot be treated as a self-contained Linux-probed peripheral after a
  cold reset.
- A firmware crash ends the experiment; retrying commands in place is not a
  demonstrated recovery mechanism.
- The firmware reservation must remain `no-map` and must never overlap Linux
  allocations.
- Boot-chain changes must preserve the firmware handoff before storage is
  retested.

## DART, power, clock, and security dependencies

### Confirmed

| Dependency | What is established |
|---|---|
| DART/IOMMU | The J81 ANS ADT node has no `iommu-parent`; the Linux ANS1 node has no `iommus`; the binding and driver contain no DART, SART, NVMMU, or IOMMU control. DMA uses the normal platform DMA API. No separately described storage DART is part of this path. |
| ANS power/reset | Both the ASP device and AKF mailbox reference the T7001 PMGR `ps_ans` power domain; the ASP node also uses it as reset control. The experimental DT marks `ps_ans` always-on. |
| Captured gates/clocks | The ADT ANS node records two clock IDs (`0x135`, `0x136`), two clock-gate values (`0x16`, `0x35`), power gate `0x16`, and power-state register offset `0x318`. |
| NAND rail | Apple's driver resolves a `function-vcc_ldo` platform function, logs `ASPSetNANDRailPower`, and carries charge/discharge timing properties. One diagnostic string identifies LDO4. This is a real rail-control dependency distinct from the ANS logic domain. |
| Runtime power behavior | Apple's driver has explicit enter/exit power-gating paths and tracks asleep/power-gated states. The Linux port does not reproduce the complete Apple power policy. |
| SEP | Apple's driver receives SEP-state notifications. The Linux observation-only test nevertheless proved that one no-encryption/raw 4 KiB block read can complete without a Linux SEP storage path. |

The mainline ANS2 architecture is materially different. Its binding requires
NVMe and NVMMU register regions, a SART, and ANS/APCIE power domains; the
driver programs an embedded per-command NVMMU. Those dependencies appear in
[mainline `nvme-apple`](https://github.com/torvalds/linux/blob/master/drivers/nvme/host/apple.c)
and its
[DT binding](https://github.com/torvalds/linux/blob/master/Documentation/devicetree/bindings/nvme/apple,nvme-ans.yaml),
whose compatibles start with later ANS2 SoCs and do not include T7001. They
must not be projected backward onto J81.

### Inferences and unknowns

- **Inference:** the PMGR `ps_ans` domain plus inherited iBoot state covers
  enough clock and rail setup for the demonstrated probe. That follows from
  the successful hardware run, not from a complete reconstruction of the
  sequence.
- **Unknown:** the separate meanings of ADT clock IDs `0x135`/`0x136` and gate
  value `0x35`, and whether Linux should eventually model each one explicitly.
- **Unknown:** the exact LDO4 voltage, polarity, flags, and safe
  charge/discharge sequence. The Apple driver proves a rail-control contract
  exists but the current evidence does not justify changing it.
- **Unknown:** whether ANS1 contains an internal translation or protection
  mechanism that is invisible to the AP device tree. The absence of an
  external DART attachment does not answer that hardware question.
- **Unknown:** safe suspend, resume, runtime power-down, or reprobe after a
  partial failure. Keeping the domain on is the evidence-backed bring-up
  choice.
- **Inference:** usable access to encrypted iOS file data will require more
  than raw block reads, likely including SEP/keybag state. This audit confirms
  transport only; it does not demonstrate filesystem mounting or decryption.

## Linux support status

| Implementation | Status for J81 |
|---|---|
| Mainline `drivers/nvme/host/apple.c` | **Not applicable.** It is an ANS2 NVMe driver and has no T7001 compatible. |
| Hoolock Linux `ans1` branch | **Experimental/WIP.** The branch still resolved to `ed8528f482a526371e59711645794c91fafb2b42` on 2026-09-25. It supplies the ASP block driver, T7001 nodes, old RTKit support, and 64-bit AKF mailbox support. |
| Hoolock A8 status page | **WIP.** The project's [A8 feature matrix](https://github.com/HoolockLinux/docs/blob/master/features/A8.md) does not classify internal storage as ready for general testing or use. |
| This repository's isolated ANS1 payload | **Hardware-proven for narrow read-only observation.** It layers [patch 0012](../kernel/patches/0012-ans1-asp-observation-only.patch) over the port, removes write unlock, rejects all write/driver-out/flush requests centrally, marks every disk read-only, and softens fatal assertions. |

The raw Hoolock source is unsafe for observation-only work because probe sends
`ASP_CMD_WRITE_UNLOCK` before disk registration. Marking only auxiliary disks
read-only does not neutralize that controller command, and the original source
does not mark the user area read-only. The local hardening is therefore a
required safety boundary, not an optional UI precaution.

The project's [recorded hardware result](../docs/plans/2026-09-13-j81-ans1-observation-only.md)
at commit `5915c17d993b38e8e9655c34e97b3796124f9f37` confirms:

- genuine RTKit/ANS firmware activity from `apple-asp 208040000.block`;
- all ten `/sys/block/asp0n1` through `asp0n10` devices reported `ro=1`;
- the user-area size was 250,000,000 512-byte sectors (128 GB decimal);
- no `WRITE_UNLOCK` appeared in the captured kernel log;
- one 4096-byte read from `/dev/asp0n1` to `/dev/null` completed;
- no I/O error or crash indicator appeared, and the system remained stable
  during the three-minute observation window.

The test deliberately did not retain or inspect the returned bytes. It proves
one narrow read path, not bulk-read reliability, data correctness, filesystem
support, decryption, write safety outside the hardened payload, or power-cycle
recovery.

## Safest first read-only probe

For a future repeat, use only the existing isolated
`m1n1-hoolock-ans1-test` RAM-root payload with the observation-only patch and
the m1n1 firmware handoff. Do not mount a filesystem, run a partition repair,
request flushes, use an unmodified `ans1` kernel, or test a write path.

### Stage 0: passive enumeration

Use the console's **Storage (ANS1): probe status + ro flags** action. It reads
logs and sysfs only. Continue only when all of these are true:

1. ASP reaches its ready/identify path without a timeout.
2. All ten expected `asp0n1` through `asp0n10` block devices exist.
3. Every corresponding sysfs `ro` attribute is exactly `1`.
4. The log contains no `WRITE_UNLOCK`, kernel oops/panic, ASP timeout, RTKit
   crash, or warning from a softened fatal assertion.

Stop and power-cycle back to the known control payload if any condition fails.
Do not try to recover or reprobe ANS in the same boot.

### Stage 1: one-block sink read

Only after Stage 0 passes, use **Storage (ANS1): safe single-block read test**.
The implementation in [`boot/ipad_console.py`](../boot/ipad_console.py)
rechecks `/sys/block/asp0n1/ro` immediately before access, refuses unless it is
`1`, and then performs exactly:

```text
dd if=/dev/asp0n1 of=/dev/null bs=4096 count=1
```

The console applies a 10-second host-side command timeout and inspects the
latest kernel messages afterward. `/dev/null` keeps media contents out of the
host transcript. The block size matches the protocol's logical block size and
the count prevents accidental sequential reads.

This exact two-stage procedure already passed once. It remains the safest
repeat probe because it reuses a reviewed safety boundary and asks the least
possible new question of the hardware. Further work should stay offline until
there is a specific unanswered question that cannot be resolved from the ADT,
the Apple driver, or the captured successful transcript.

## Source inventory

Primary local evidence:

- private captured J81 ADT named above (read only; not committed);
- [ANS1 driver and DT integration](../kernel/patches/0015-ans1-storage-driver-and-core-support.patch);
- [observation-only hardening](../kernel/patches/0012-ans1-asp-observation-only.patch);
- [recorded J81 probe and safety procedure](../docs/plans/2026-09-13-j81-ans1-observation-only.md);
- [console status and single-block actions](../boot/ipad_console.py);
- existing read-only Ghidra project for the iOS 8.1 J81 kernelcache,
  specifically the `ASPSupportNodes` kext range.

Authoritative upstream sources:

- [Hoolock ANS1 ASP driver](https://github.com/HoolockLinux/linux/blob/ans1/drivers/block/asp.c)
- [Hoolock ANS1 DT binding](https://github.com/HoolockLinux/linux/blob/ans1/Documentation/devicetree/bindings/block/apple,s5l8960x-ans.yaml)
- [Hoolock m1n1 ANS firmware handoff](https://github.com/HoolockLinux/m1n1/commit/9d53672dbf5f41577aaa182284f68d06614e2dcf)
- [mainline Apple ANS2 NVMe driver](https://github.com/torvalds/linux/blob/master/drivers/nvme/host/apple.c)
- [mainline Apple ANS2 DT binding](https://github.com/torvalds/linux/blob/master/Documentation/devicetree/bindings/nvme/apple,nvme-ans.yaml)
- [Hoolock A8 feature status](https://github.com/HoolockLinux/docs/blob/master/features/A8.md)
