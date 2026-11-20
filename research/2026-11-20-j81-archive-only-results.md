# 2026-11-20 archive-only mailbox results (five packets)

Hardware: none. Copies of the mailbox RESULT.md files under from-builder/*-result.

---
<!-- 2026-11-19-j81-core-aperture-research-result -->
## Core aperture, archive-only result (2026-11-20)

Hardware: none used. Offline reproductions all passed on this Apple Silicon Mac: packet SHA256SUMS (4 packets), `audit_j81_pmgr_start.py` (soc-tvm=1 group 3 rail 1 0x20e02d000; DPE row 12000 selector 8; CPU TVM 0x202220048), native TVM test (131072 ops), mask test, `audit_j81_gpu_id_access.py`, `test-stock-mapping.py`, `test_j81_fender_control.py` (64 combinations).

## 1. iPadOS boot 846527FB-1D2B-4834-AEB8-49480323BBFD
Source: `2026-11-19-j81-ios-pregpc-miscacg-run-result/evidence/*.ndjson` (5 records, all this UUID) and the full device archive `artifacts/live/private/gpu-offline/j81-pregpc-miscacg-device.logarchive` (797 MB, 19,401,670 events over 15+ boots; this boot has 232,519 events, 10,407 from `kernel`).
Searched every event of this boot for `1008`, `4008`, `201e00000`, `0x2d000`, `2d100`, `FNDR`, `fender`, `J81_BOOT`. Only the five `J81_BOOT` rows match (P0, GPC TICKS=0x3909, P1, BEFORE CORE READ, CORE=0x00070500, timestamps 20:49:29.111514 to .112283). Other matches were unrelated text (for example "LS database generation 1004 to 1008").
**Result: no real read of PMGR +0x1008 or +0x4008 for this boot exists. Coverage gap.** The recorder kernel module emits only the fields printed in P0/P1; neither word is among them.

## 2. Linux comparison rows (full words, raw read, snapshot stage)
Stock ordinary-writer requests and J96 values are NOT mixed in; Apple-requested page-1/page-4 words (0x40480348 / 0x48480348) are requests from another boot and omitted from this table.

| Boot | Snapshot | 0x1008 | 0x4008 | MiscACG | page5 +4 |
| --- | --- | --- | --- | --- | --- |
| 3555dc92 observer control | B / C | 0x80480348 / 0x80480348 | 0x88480348 / 0x88480348 | 0 / 0 | 0 / 0 |
| 49df36fd core-ID | B / B2 / C | 0x80480348 (all) | 0x88480348 (all) | 0 / 1 / 1 | 0 / 0 / 0x40000000 |
| a076f20f timed core | B / B2 | 0x80480348 (both) | 0x88480348 (both) | 0 / 1 | 0 / 0 |
| c92665fd, fcc3107e MiscACG write | B / B2 / C | 0x80480348 (all) | 0x88480348 (all) | 0 / 1 / 1 | 0 / 0 / 0x40000000 |

On every Linux boot where page 5 rose to 0x40000000 the page-1/page-4 words were unchanged, so they are not needed for the page-5 transition. The matching iPadOS readback is missing, so whether they matter for core access is untested.

## 3. Host-only dispatch trace
Not repeated: the RESEARCH.md table and the packet audit already resolve the three targets (cpu-tvm 6bccd34, soc-tvm 6bccd7c, dpe-thrtl 6bccc70). From the retained evidence the descriptors are: soc-tvm group 3 rail 1 address 0x20e02d000 request old|1, no enable poll; DPE row 12000 selector 8; CPU TVM base 0x202220000 (+0x48). No J81 captured value exists for any of them from an iPadOS boot (see the DPE/CPU and SoC TVM results).

## 4. Remaining candidate and discriminating observation
Candidate: the +0x2d000 SoC TVM control, because it is the only one with a retained Linux sample (zero, pre-page-5) and a request recipe with no poll. The cleanest observation is one added word, +0x2d000, in the existing before-GPC and after-page-5 PMGR snapshots on a Linux MiscACG boot, with the phase-matched working iPadOS readback as counterpart. Neither comparison exists yet, so the candidate is untested, not supported.

---
<!-- 2026-11-19-j81-soc-tvm-archive-result -->
## SoC TVM archive comparison (2026-11-20)

Control reproduced: soc-tvm=1 group 3 rail 1 address 0x20e02d000 request old|1, no enable poll. Native test: 131072 operations PASS. Old Linux words 0x2d000 / 0x2d100 / 0x32000 = 0 / 0 / 0.

| Item | OS / boot | Boot UUID | Raw word | Kind | Order vs MiscACG, GPC, page 5, core | Source |
| --- | --- | --- | --- | --- | --- | --- |
| +0x2d000 | Linux 2026-11-11 after-GPC1 | not recorded | 0x00000000 | read | MiscACG also 0 in same file; page5 +4 = 0 in sibling plls.log; no core attempt | `local-setup-20261118/.../gpu/pmgr-words-20261111-after-gpc1/volman.log` |
| +0x2d100 | same | not recorded | 0x00000000 | read | same | same |
| +0x2d000/+0x2d100 | iPadOS working boot 846527FB | n/a | not captured | none | n/a | five J81_BOOT rows and full device archive searched, nothing |
| +0x2d000/+0x2d100 | Linux page-5-high boots (c92665fd, fcc3107e, 49df36fd) | n/a | not captured | none | n/a | seven-word snapshots omit these addresses |

Boot-arguments: no soc-tvm override or boot-args string appears in the retained iPadOS evidence.
The two zero words come from a single Linux sample before the page-5 rise, with no UUID, so they cannot be tied to a boot; the sibling plls.log in the same directory is assumed, not shown, to be the same boot.

**Verdict: the missing-enable hypothesis is untested.** The sample is consistent with "enable not set on Linux" but there is no working iPadOS value and no Linux page-5-high sample, so it is neither supported nor contradicted at the sampled point. The preconditions for resuming dpe-thrtl tracing (a contradiction) are not met.
**Next observation (proposal only):** add only +0x2d000 to the existing before-GPC and after-page-5 snapshots (status +0x2d100 optional), keep the existing GPC/page-5 evidence, no core-ID access, no TVM write. Counterpart: the same word on the iPadOS probe at the phase before the core read.

---
<!-- 2026-11-19-j81-dpe-cpu-tvm-archive-result -->
## DPE throttle and CPU TVM archive result (2026-11-20)

Audit reproduced: DPE row 12000, selector 8, writes +0x1b0, +0x1a0, +0x150, +0x190, group 22 updates +0x190 bit 35; CPU TVM selector=8 instance 0 reg[1]=0x202220000 length 0x2000, bit target +0x48 bit 0. Mask test: 131072 input/enable pairs PASS.

Searched (exact regex from the packet plus dpe-thrtl, cpu-tvm, soc-tvm): `local-setup-20261118/ipadlinux/ipad-nixos/artifacts/live/{gpu,private/gpu-observations,private/gpu-offline,private/gpu-pair-20261109-a,sessions}` and this repository's `artifacts/live/{gpu,private}`.
Formats seen: text pmgr-word logs (`w 0x... raw=0x...`), ADT text dumps, iBoot decompiler output, ndjson/logarchive records. No contiguous raw dump of CPU-cluster resource 0x202220000 exists.

| Item | Found | Counts as observation? |
| --- | --- | --- |
| CPU TVM +0x48 bit 0 | none | no, unknown |
| DPE +0x190 bit 35 (+0x194 bit 3), +0x150, +0x1a0, +0x1b0 | none | no, unknown |
| ADT cpu-tvm=0x1, soc-tvm=0x1, dpe-thrtl=0x2ee0 | `gpu-observations/20261106T060741Z-pongo-adt.adt` | configuration, not a readback |
| iBoot decompilation `DAT_202220000 = 0x1fc10060` (`ghidra-iboot/dec_15llb_*.c`) | requested store in decompiled iBoot code | no; code, not a J81 observed value |

No boot ID, page-5 word or GPU-ID outcome can be attached to any CPU TVM/DPE value because there are none. Mark all fields unknown; no sample pairs from different boots exist to compare. Matched/differing-bit tests cannot be applied. Next hardware experiment left pending.

---
<!-- 2026-11-20-j81-core-map-archive-result -->
## GPU-ID mapping and page-5-high comparison, archive result (2026-11-20)

Reproduced: `audit_j81_gpu_id_access.py` (Linux late: mmap syscall + result check precede indexed LDR W10 and DSB LD; Linux timed: page-5 gate, final checkpoint call, LDR W2 at +0x20, DSB LD; iPadOS: page-5 gate, map call, non-null path, +0x20, LDR W0, DSB SY) and `test-stock-mapping.py` PASS (GPU aperture, four DRAM boundaries, MAIR initializer). Packet checksums verified.

## 1. Observer ELF and translation records
Searched `artifacts/live/private/j81-observer-paired-20261119-v1` (contains Pongo.bin, m1n1-linux.bin, runner-src.tar.gz, modules), repo `artifacts`, and the NAS archive roots for `vmlinux*`, `*.config`, `*build-receipt*`. **No vmlinux/ELF .notes section or build receipt survives**, only the notes hash a2dda271... measured live from /sys/kernel/notes by the preflight. The ELF SHA-256 and build ID are therefore unknown. (The builder disk images under `linux-builder-*` were not unpacked.)
No translation or exception records (VA, privilege, PA, leaf attributes, granule, MAIR byte, PC/syndrome/fault address) were retained for any of the three boots (3555dc92, 49df36fd, a076f20f). A kernel-only page-table dump could not identify the EL0 mapping in any case. Status: unknown.

## 2. Working iPadOS pre-ID reads
Boot 846527FB: full device archive searched (see the core-aperture result). Fender +0, +8, +0x1000 bit 4, +0x20000 bit 5, PMGR +0x1008 and +0x4008: **none captured.** Only P0, GPC TICKS=0x3909, P1 (F=40000000/40000000/40000000 is page 5), BEFORE CORE READ, CORE=0x00070500. P1 G=30303000 is the log-buffer field, not a hardware read. Linux +0 control was 0x40000000 in boot 49df36fd just before the attempted ID (bit 29 clear); no same-stage iPadOS word exists to compare.
Roots/formats searched: text logs and ndjson under `from-builder/*`, `local-setup-20261118/.../gpu`, `private/ios-logarchive-j81-*` (tar and gpu-recent.log), logarchives.

## 3. Correlation
| Boot | Page 5 | GPU-ID | Mapping evidence |
| --- | --- | --- | --- |
| iPadOS 846527FB | 0x40000000 x3 | 0x00070500 | code path only (disassembly audit), no runtime translation |
| Linux 49df36fd late | 0x40000000 | hung, watchdog | code path only |
| Linux a076f20f timed | 0x40000000 observed before stall | hung, watchdog | code path only |

The static audits show address, width and ordering agree (+0x20, 32-bit load); the stock arithmetic confirms the GPU boundary and MAIR byte. Nothing archived discriminates CPU translation from downstream clock/reset/Fender state. Hypothesis stays open.

## 4. Next probe
As the packet proposes: a Linux mapping-only observation of the same process VMA (return PA and leaf attributes via /proc/self/pagemap-style or a kernel module walk, expected PA 0x201000000, MAIR byte 0x00) that exits without reading the GPU. I have not prepared or run it.

---
<!-- 2026-11-20-j81-fender-bit29-result -->
## Fender +0 bit 29, archive result (2026-11-20)

Reproduced: packet checksums, `audit_j81_gpu_id_access.py`, `test_j81_fender_control.py` (event switch: type 0 calls controller slot +0x388, type 6 advances; 64 combinations of control[31:29], state enable, idle state, kick status PASS).

Searched with the packet regex (`AGX_CR_FNDR_TIMER_SLEEP_CONTROL`, `Pre-inspection fender snapshot`, `Fender State`, `201e00000`, `J81_BOOT (P1|BEFORE CORE READ|CORE=)`) in `local-setup-20261118/.../artifacts/live` (gpu, private, sessions), this repository's `artifacts/live`, and every event of the retained 797 MB device archive.

| Source | Boot | Phase | +0 word | bit 29 | Notes |
| --- | --- | --- | --- | --- | --- |
| iPadOS 846527FB | working, ID 0x00070500 | pre-ID | none captured | unknown | P1 G=30303000 comes from the log buffer, not a control read |
| Linux 49df36fd core-ID | page5 0x40000000, ID hung | after GPC poll, immediately before ID attempt | 0x40000000 | 0 | read-only gated read (`stage=after-gpc-control raw=0x40000000`) |
| Linux 2026-11-06 fender-wake | pre-MiscACG | after GPC | 0x40000000 | 0 | `gpu/fender-wake-20261106*.log`, boot id not recorded |

No firmware-event evidence (type 6 record, selected index, record +4 word, callback time) was retained, so execution of the type-6 callback cannot be shown. A Fender +0x1000 value (0x11) is performance-state control and is not used here. Requested stores with bit 29 set: none in the retained Linux runs.

**Result: bit 29 on the working iPadOS boot is unknown.** The Linux boots that stalled had bit 29 clear, but without the working boot's value the difference is untested. Archives and phases searched are listed above. Remaining measurement: one independently labelled same-boot +0 read immediately before the working ID on iPadOS, with its mapping kept separate from the logging scratch. Not run.
