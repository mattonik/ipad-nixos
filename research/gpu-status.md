# J81 GPU research status

**Status: bring-up in progress; no GPU acceleration is available.** The target
is the iPad Air 2 (J81, A8X/T7001), whose GPU is identified by this project as
Imagination GXA6850 (Rogue/G4G generation).

For the stock 19H394 path from the core-ID read to running META firmware (LDR image, Fender-proxied start sequence, Rogue MMU, IRQ 138 doorbell, firmware interface) and the proposed read/write steps, see [j81-meta-boot/RESULT.md](j81-meta-boot/RESULT.md) (2026-11-22, offline).

For the reproducible LDR layout tool, the Fender ConfigRAM correction (it is a write-only replay list at `+0x10000`, not a mailbox), the comparison with the public Imagination driver and the revised first-boot steps, see [j81-ldr-tool-fwif/RESULT.md](j81-ldr-tool-fwif/RESULT.md) (2026-11-22, offline).

For the comparison with Orchard's A8 GPU driver (OrchardLinux/orchard PR #196): J81 combines the A8 boot path with the A9 firmware-interface layout, PMGR `+0x5004` bit 30 is the GPU PLL-lock bit, and the revised first-boot steps, see [j81-orchard-a8-gpu/RESULT.md](j81-orchard-a8-gpu/RESULT.md) (2026-11-22, offline).

For why the Fender `+0x20000 = 0` store (`VCM_PERF_STATE_OVERRIDE`) hangs with a non-empty ConfigRAM list: Apple's GFX power cycle ([j81-fender-store-hang/RESULT.md](j81-fender-store-hang/RESULT.md), run 24) and the sleep-timer timing idea ([j81-fender-store-hang-2/RESULT.md](j81-fender-store-hang-2/RESULT.md), runs 25b and 26) did not stop the hang. The `AUTO_PM_EN` (PS bit 28) lead from [j81-fender-store-hang-3/RESULT.md](j81-fender-store-hang-3/RESULT.md) is dropped: Linux's genpd power-on already makes Apple's bit-28 store, and the bit reads back 0 on GFX (runs 27, 27b, 27c). Dropping W1/W2a did not help (run 29). Re-applying the GFX bridge settings 9/10 after the power-on, as Apple does ([j81-fender-store-hang-4/RESULT.md](j81-fender-store-hang-4/RESULT.md)), made a no-op entry pass (run 30), but `0x3808 ← 1` still hangs (run 31). Apple only ever writes `0x3808 ← 1` right after `SLC_CTRL_MISC 0x3800 ← 0x00035500_00300001` (address-decode mode `0x32 → 0x30`), on an SLC that has just been reset ([j81-fender-store-hang-5/RESULT.md](j81-fender-store-hang-5/RESULT.md)). Runs 32–36: the walk does write RGX (META_BOOT `0x0bf8 ← 1` reads back 1, run 33), and current-value writes pass. SLC mode writes and SOFT_RESET asserts still hang. Apple sets no extra clock, DVFM or hold before the stream. The leading reading is the stopped GPU clock in state 0 (0 Hz). See [j81-fender-store-hang-6/RESULT.md](j81-fender-store-hang-6/RESULT.md). Run 37: a GARTEN-only assert also hangs. Runs 38/39: with no override store at all, the walk still ran at the 0→1 transition (META_BOOT reads 1), and a release in state 1 followed by RGX reads hung (h12). In Apple's code every release is followed at once by a state request, and Apple never reads RGX after one. See [j81-fender-store-hang-7/RESULT.md](j81-fender-store-hang-7/RESULT.md). Runs 40–42: the full stock list (resets, SLC pair, META_BOOT) applies at 0→1 with no release. **Correction:** the runner maps only `0x11000` of the Fender window (`GPC_SIZE`), so every `gpc_regs + 0x20000` override access misses Fender. That voids the "override store/read hangs" results and the `+0x5004` conclusion until the mapping is fixed (`≥ 0x21000`). See [j81-fender-store-hang-8/RESULT.md](j81-fender-store-hang-8/RESULT.md) (2026-11-26, offline; B0 (read-only `/proc/vmallocinfo` check), B1 (Apple's order with the fixed mapping) and F3a (first firmware run) proposed).

For the first firmware boot (F3a, runs 45–49): META thread 0 starts by itself and then halts on a general memory fault (T0STATUS `0x005e0008`, BIF fault 0); the firmware wrote nothing. Two decoded gaps in our image: config `+0x2f0` must hold thread 1's start `{pc 0x20000000, sp 0x8000b3c8}`, and the MMIO window table (Fender, AIC timer, AIC SW-int, RGX) must be filled and mapped at GPU VA `0xe1c4200000`. See [j81-f3a-first-boot-1/RESULT.md](j81-f3a-first-boot-1/RESULT.md) (2026-11-26, offline; M1 (read the META catch registers), C1 (`+0x2f0`), C2 (window table) proposed). Runs 50–58: with `+0x2f0` and the windows filled, thread 0 runs without faults and writes 121 words. Then it polls with no writes and posts no alive record. The firmware text is MiniM, for which no public decoder exists. Leads are a stopped AIC timebase (window 1 = ADT `aic-timebase`, reads 0) and a firmware-built list of USC slot registers (`0xe200..0xe240`). See [j81-f3a-alive-1/RESULT.md](j81-f3a-alive-1/RESULT.md) and [j81-f3a-minim-1/RESULT.md](j81-f3a-minim-1/RESULT.md) (2026-11-27, offline, partial; T1 (timebase read), U1 (USC slots) and H1 (halted register snapshot) proposed). Run 60 (halted snapshot): thread 0 sits at PC `0x10000358` in the firmware scheduler's idle loop, polling the priority-0 `enqueued_commands` count (scheduler block `+0x78c`). The event-ring layout matches Apple's (root `+0x20`/`+0x24`), and Apple sends no kick before alive. Thread 1 has never started. See [j81-f3a-idle-1/RESULT.md](j81-f3a-idle-1/RESULT.md) (2026-11-27, offline; R1 (thread 1 state) and K1 (one `0xb00 = 0x10` kick) proposed). Compared with Orchard's A8/A9 driver, our image lacks four things. Firmware pages should bypass the SLC and carry PM/META protect (PTE bits 3 and 62; ours are valid-only, so the alive record may sit in the SLC). The POLICY block is filled on the boot path. The config perf table is `+0x29c` = 4, `+0x2a0` = 16, `+0x2a4..` = MHz. The four hardware objects belong at `0x8_00000000`. See [j81-f3a-orchard-reference-1/RESULT.md](j81-f3a-orchard-reference-1/RESULT.md) (2026-11-27, offline; E0 (IRQ-138 bit read and SLC flush) first, then E1-E4). Runs 65–67: with SLC bypass and PM/META protect on the firmware pages, the firmware reaches its alive event on J81. For the first command, the ring protocol is confirmed in Apple's own `submitDeviceControl`: 20-byte entries, the producer at control `+0x10`, the kick `0xb00 = 0x10`. Apple names the command types; 3 is DeviceSetGARTPhysical (the slot load) and 8 is PerfCtrSamplerCommitCounterList (with state `+0x1020 = 0`, an empty first command). The event ring must be drained. See [j81-f3a-first-command-1/RESULT.md](j81-f3a-first-command-1/RESULT.md) (2026-11-27, offline; C1 (type 8, empty) then C2 (slot 1 load) proposed). Run 69: the type-8 command was ignored, although the host side matched Apple's `submitDeviceControl` write for write; Apple's host writes nothing else to wake the firmware (no META SW interrupt, AIC, MTS setup or thread start). One alive record against Orchard's ~290/s suggests the scheduler is not running; the kick is likely lost in MTS state the firmware programs itself (DM0 masked in SCHEDULE_ENABLE, or associated with the unstarted thread 1). See [j81-f3a-first-command-2/RESULT.md](j81-f3a-first-command-2/RESULT.md) (2026-11-27, offline; M1 (read-only MTS registers 0xb30-0xbc8 around the kick) first, then M2, M3). Run 70: the firmware programmed the MTS DM association, interrupt enables and garten fence but left SCHEDULE_ENABLE (`0xbc8`) at 0, and the kick was not counted. Apple's host never touches `0xbc8` (only `0xb00`), so the enable is the firmware's. Correction: Fender `+0x14 = 7` is TIMER_POWER_INT_STATUS (an acknowledge), not a wake. One host input differs from iOS: CONTROL `+0x20` (idle power off) is 1 on iOS and 0 in our blob. See [j81-f3a-mts-schedule-1/RESULT.md](j81-f3a-mts-schedule-1/RESULT.md) (2026-11-27, offline; N1 (read-only Fender/MTS reads around the kick), N2 (`0xbc8 = 0x1`), N3 (CONTROL `+0x20 = 1`) proposed). Decoded with Orchard's MiniM expander (provisional): the firmware never touches `0xbc8` either, so it is not the gate. Thread 0 sleeps on a META trigger (TXMASK `0x21`; trigger 0 = its timer, an MTS task wakes it via vector `0x04820700`), reads RGX `0xb10` for the DM, and runs the device-control ring first only if a gate on root `+0x70` (POLICY) and root `+0x74` (a `0x28` object) passes. One alive record per boot is normal; RGX is at META `0x02000000`. See [j81-f3a-idle-loop-decode-1/RESULT.md](j81-f3a-idle-loop-decode-1/RESULT.md) (2026-11-27, offline; P1 (read-only RGX `0xb08`/`0xb10`/`0xb20` around the kick), P2 (root gate pointers), P3 (kick `0xb00 = 0x00`) proposed). Run 74: the kick reaches the MTS (`0xb10` = `0x10`, held) but the consumer stays 0. The firmware's trigger setup is complete (vector `0x04820700 = 5`, TXMASK `0x21`, line 0 cleared at `0x04820010` before each sleep) and blob f passes the DM0 gate, so thread 0 most likely never receives trigger 5. Thread 1 is not needed for DM0 (the firmware starts it itself). See [j81-f3a-meta-trigger-1/RESULT.md](j81-f3a-meta-trigger-1/RESULT.md) (2026-11-27, offline; L1 (`0xb08 = 2` liveness marker), P3 (`0xb00 = 0x00`), K2 proposed). Slave-port stall (MSLVCTRL1 `0x06000040`: request accepted, READY clear): Apple's host never reads META through the slave port while the firmware runs (only TXENABLE writes after the firmware's type-6 park event, and failure dumps); reads worked while the pre-E1 firmware was busy and stall since it sleeps in TXSTAT, so a sleeping META most likely does not service them. Best liveness signal without the slave port: MSLVIRQSTATUS `0xac8` bit 2 (clear with `0xfffffffb`). See [j81-f3a-slave-port-1/RESULT.md](j81-f3a-slave-port-1/RESULT.md) (2026-11-27, offline; S1 (poll READY 30 s), S2 (`0xac8` around the kick), S3, P3, P4 proposed). Apple's J81 Fender ConfigRAM list is our 31-word list word for word (three SOFT_RESET asserts, META_BOOT, BIF_CAT_BASE0, the SLC pair, the release, the terminator); request 24's '12 computed entries' were unrelated vtable calls. No entry touches the MTS or META's interrupt path, so the trigger problem is not in ConfigRAM. See [j81-f3a-configram-1/RESULT.md](j81-f3a-configram-1/RESULT.md) (2026-11-27, offline; F1 (Fender `+0x10 = 0` parity), N3, S2 proposed). The firmware arms its own TXTIMER at init (TXDIVTIME = 1, period from config `+0x2a8`, the state-1 MHz), so 30 s without a tick means META's clock is not running after it goes idle (inferred); that one cause explains the missing timer tick, MTS wake and slave-port service. Likeliest: automatic clock gating (MISC_ACG on, garten idle under META, Fender snoop bit clear). See [j81-f3a-a9-diff-1/RESULT.md](j81-f3a-a9-diff-1/RESULT.md) (2026-11-27, offline; C1 (read-only PS_GFX/PLL/CLK_STATUS/Fender after alive) first, then C2, C3). Run 79: PMGR not gated, CLK_STATUS `0x00600000` = SIDEKICK and BIF_SIDEKICK running (META's domain clocked), and TXCLKCTRL stays at its DEFON reset (nobody writes it). The 30 s silence is by design: an idle firmware masks its own timer (TXMASK `0x20`) and waits for MTS line 0 alone; request 26's 'clock stopped' is withdrawn. The firmware self-kicks with non-counted `0xb00 = 0/1/2`. See [j81-f3a-meta-clock-1/RESULT.md](j81-f3a-meta-clock-1/RESULT.md) (2026-11-27, offline; W1 (pending slave-port read as wake detector + `0xb00 = 0x00`), W2, R, W3 proposed). Run 80: no kick value (counted or non-counted) wakes thread 0. Synthesis: RGX EVENT_STATUS `0x130` = `0x200` after alive is upstream's MMU_PAGE_FAULT, never cleared by the firmware's handler; we only ever read fault bank 0 (`0x12b0`), and Orchard's A8 maps a zero page at GPU VA 0 that we do not. Top hypothesis: an MMU fault right after alive stalls the firmware. See [j81-f3a-synthesis-1/RESULT.md](j81-f3a-synthesis-1/RESULT.md) (2026-11-27, offline; X1 (read-only fault census: banks 0/1/TEXAS, BIF_MMU_STATUS, `0xb50`/`0xb54`) first, then X2 (zero page at VA 0)). Runs 81/82: the fault is in bank 1, a single META thread-0 instruction fetch at mapped VA `0xe1c000df80`, latched from META's release; the MMU is not stalled and the firmware reaches alive after it, so it is probably a boot-time race, not the stall. META uses CAT_BASE0 (`0x1200` is right; reading 0 is likely a filtered host view). New fact: the pending event never became an MTS interrupt task either (`0xb98`/`0xbb0` = 0), so neither interrupt nor background work reaches META. See [j81-f3a-bif-fault-1/RESULT.md](j81-f3a-bif-fault-1/RESULT.md) (2026-11-27, offline; E1 (EVENT_CLEAR `0x138 = 0x200`, then kick with the detector), E2, E3 proposed). Run 87: the firmware now consumes device-control commands 8 and 3 (governor pins and MMU_ROOT[0] were the missing inputs). For the first compute job: the CL lane (root `+0x10/+0x14`) takes a 20-byte entry `{2, channel fwaddr, end}`, as Apple's `submitCLChannel` writes it, and the doorbell is `0xb00 = 0x12`; the channel page, record and microsequence follow Orchard's A9 path (our firmware has the A9 object sizes). See [j81-f3a-compute-job-1/RESULT.md](j81-f3a-compute-job-1/RESULT.md) (2026-11-27, offline; J0 (CL plumbing, no job) first, then J1 (empty job)). Run 88: J0 consumed (CL lane, channel page, `0x12` doorbell work). The 19H394 compute record is the A9's (size `0x290`) plus a cluster mask at `W+0x18` (`0xff`) and a per-cluster array at `W+0x78`; the terminate word `W+0x244` comes from user space (try `0x00900004`, then `0x00a00004`); the microsequence uses the A9's opcodes (`0x32`, `0x80000018`, `0x101`, `0x18`, `0x33`). See [j81-f3a-compute-decode-1/RESULT.md](j81-f3a-compute-decode-1/RESULT.md) (2026-11-27, offline; J1 (empty job) with exact values, then J1b/J1c, J2). Empty-job payloads (from Mesa and Orchard's kernel): the control stream is one word `0x80000000` (STREAM_TERMINATE), the PDS program a single HALT `0xd3000000` (Orchard's choice, not Mesa's fence-terminate program); the descriptor words decode as CR_CDM_*_PDS1 (unified 5 or 4, data size 2). Mirror Orchard's slot-1 layout: zero page at VA 0, data page at VA `0x200000` (stream at +0, HALT at +0x1000). See [j81-f3a-job-payload-1/RESULT.md](j81-f3a-job-payload-1/RESULT.md) (2026-11-27, offline; J1 with exact values, then J1b, J1d). Run 91: J1, the empty compute job, completes (both stamps 1, no fault). For a kernel (J2): the A8 runs Apple's USC ISA (A10/G9P family), but per Orchard's A8 iPadOS 15 capture its CDM records are plain 7-word Rogue (`{0x2106, PDS data, PDS code, 0, 0, 0, 0x40000000}`), the empty kernel is the A10's (`0100 0140 0000`, `c000` padding, `8000`) and the PDS words are known; offsets are relative to the PDS/USC base heap, which J1 did not test. The A8 store kernel bytes are not published. See [j81-f3a-compute-kernel-1/RESULT.md](j81-f3a-compute-kernel-1/RESULT.md) (2026-11-27, offline; bisect J2a (PDS-only), J2a', J2b (empty kernel), J2c (store kernel)). The A8 store kernel for J2c (65 words, `0x82` bytes): the A10 store stores nothing on the A8, so it uses the A8-only address-pair store `2510 0504 8100 4020` after two common-store moves of the binding into r0:r1; the stream adds Orchard's A8 end of pass (empty USC task `0x4`, fenced DOUTC `0x7`). See [j81-f3a-store-kernel-1/RESULT.md](j81-f3a-store-kernel-1/RESULT.md) (2026-11-27, offline; word table with per-word confidence).

## What has been observed

- A three-boundary iPadOS 15.8.5 (`19H394`) planned-panic series now pins
  PMGR page-5 `+0x4` bit 30 to the stock GPC `0x11` request/poll interval:
  it was `0` after AGX's clock/power callbacks and after the preceding GPC
  `0x40000000` store, then `0x40000000` after the request's busy poll. The
  earlier Linux sequence reached poll state `1` but sampled `0`; thus writing
  bit 30 is not justified and the missing condition is upstream of the Linux
  GPC state machine. See the [current boundary result](2026-11-16-j81-agx-postpower-page5-result.md).

- A bare-PongoOS replay of the same PMGR/66-bridge/GPC sequence also reached
  GPC state `1` with page-5 `+0x4 = 0` in three direct reads. Its subsequent
  first RGX revision read at `0x201000020` did not return, matching Linux's
  non-response. Linux-only userspace, `/dev/mem`, or normal handoff is thus
  insufficient as an explanation; see the [PongoOS core-read result](2026-11-16-j81-pongo-core-read-result.md).

- The proposed [next paired Linux observation](2026-11-10-j81-next-build-agent-handoff.md)
  tests whether page-5 bit 30 is briefly set closer to the successful GPC
  poll. It is a test plan, not a demonstrated GPU-ready condition.

- A fresh Linux GPC run reached state `1` on poll 5, then sampled page-5
  `0x20e005004` as `0` in the same process. The sysfs read returned 34.5 µs
  after a timestamp taken after that poll; time before the timestamp was not
  measured. The watchdog disarmed ([result](2026-11-10-j81-linux-gpc-page5-timed-probe.md#corrected-hardware-result)).

- An iPadOS five-point capture found page-5 offset `0x5004` was `0` after
  the conditional GPC control-write site and `0x40000000` after the state poll.
  The interval includes the `0x11` state request; causation and the bit's
  meaning remain unknown ([capture](2026-11-10-j81-page5-capture-results.md#gpc-control-boundary-transition-after-control-sample)).

- An iPadOS four-point capture observed PMGR-method offset `0x5004` as `0`
  immediately after the power-provider return and `0x40000000` after GPC
  polling. The operation responsible and the bit's meaning remain unknown
  ([capture](2026-11-10-j81-page5-capture-results.md#power-provider-boundary-change-observed-during-gpc-interval)).

- A three-point iPadOS boot captured PMGR-method offset `0x5004` as `0`
  after the GFX clock-provider return and `0x40000000` both after the GPC
  poll and after identity. The transition's cause and relationship to Linux
  GPU readiness remain unknown ([capture](2026-11-10-j81-page5-capture-results.md#reduced-middle-probe-change-observed-by-the-gpc-poll)).

- Offline tracing resolved a candidate iOS 15 power-gate callback that reads
  PMGR bits 8/9 into an output flag. Its runtime class is unverified; see
  the [callback analysis](2026-11-10-j81-ios15-power-gate-callback.md).

- A paired iPadOS boot observed PMGR page-5 offset `0x5004` change from
  `0` after the GFX provider returned to `0x40000000` after GPU identity.
  A separate Linux post-GPC sample was `0`. The bit's role and the cause of
  the iOS change remain unknown; see the [paired capture](2026-11-10-j81-page5-capture-results.md#paired-ios-4-timing-on-one-boot).

- A guarded PMGR power cycle completed, and the PMGR state subsequently read
  as `0x3ff` (state 15).
- A staged sequence of 66 bridge-table store operations reached its software
  checkpoints. Two bridge words were read back:
  `0x201f00018 = 0x80010004` and `0x201f0001c = 0x00010001`. The first address
  overlaps one table target; the second is outside the table's 66 targets.
- GPC initialization reported state 1. The first direct RGX core-ID read did
  not complete. Its cause is unknown; the read does not establish whether the
  GPU is ready or whether the address is correct.
- A separately guarded, watchdog-supervised MCC read completed on a later
  Linux RAM boot: `0x200000830 = 0x00000000`. This raw value matches none of
  the conditional iOS 8.1 low-five-bit/bit-8 write patterns for selectors 0,
  3, or 4;
  it does not establish MCC initialization, hardware mode, or prior iOS
  callback history. See the [MCC read result](2026-11-08-j81-mcc-read-result.md).
- A same-boot read before and after guarded GFX power-on found all 34
  sampled performance-page words unchanged; the selected GPU clock remains
  unknown ([paired capture](2026-11-09-j81-gfx-perf-paired-capture.md)). The
  Fender state getter reads the low nibble of a GPC register when enabled;
  this does not establish the selected GFX frequency-table entry
  ([state-interface trace](2026-11-09-j81-gpc-state-vs-gfx-perf-selector.md)).
- A later same-process timed GPC/revision experiment timed out after its
  pre-poll checkpoint. It cannot distinguish a GPC-poll stall from a later
  core-read stall ([v2 result](2026-11-09-j81-timed-gpc-revision-v2-result.md)).
- A subsequent timed run confirmed GPC state `1` after five polls and
  emitted its pre-revision checkpoint, but produced no revision result;
  the delay and clock call after that checkpoint leave the exact stall site
  unconfirmed ([campaign result](2026-11-09-j81-campaign-timed-result.md)).
- A fresh host-paced campaign again reached GPC state `1`, acknowledged
  the `0x201000020` revision-read checkpoint, and received no result
  ([paced result](2026-11-09-j81-campaign-paced-result.md)).
- A temporarily instrumented iPadOS 15.8.5 boot returned both original RGX
  identity reads and reported GPU firmware startup; the first equivalent
  Linux read did not return ([iOS identity](2026-11-09-j81-ios1585-gpu-identity-capture.md)).
- On a later iOS boot, all 66 GFX bridge writer requests matched Linux
  test4's checkpointed addresses and values in order, subject to the
  documented selector mappings ([capture](2026-11-10-j81-ios-corrected-bridge-result.md)).
  An earlier probe's empty result was due to an incorrect instance filter.
  Another 27 writer calls belonged to different threads from the GFX
  provider and match display, USB and ISP tables
  ([thread capture](2026-11-10-j81-writer-thread-result.md)).
- Linux GPU firmware execution, job submission, and rendering have not been
  demonstrated.

Working iOS's existing PMGR poll read returned `0x3ff` and its existing GPC
poll returned `1`, matching the corresponding Linux samples across different
boots ([poll result](2026-11-10-j81-ios-linux-poll-result.md)). This narrows
the measured gap without establishing equivalence of the full hardware state.

A subsequent page-5 comparison found `0x20e005004 = 0x40000000` in iOS
after GPU identity, but `0` on Linux both before and after its GFX/GPC-only
control. Samples of the adjacent `+0` and `+8` words matched. These are
separate boots and the bit's meaning and causal role are unknown; see the
[capture results](2026-11-10-j81-page5-capture-results.md).
Another iOS boot sampled that `+4` word as `0` before GPC/identity, so the
post-identity difference must be checked at both points in the same boot.

A later bare-PongoOS replay independently completed the PMGR/bridge/GPC
sequence, reached GPC state 1, and read page-5 `+4` as zero three times
([no-core result](2026-11-16-j81-pongo-gpc-page5-result.md)). Its guarded
first RGX revision read then did not return ([core-read result](2026-11-16-j81-pongo-core-read-result.md)). This rules out a Linux-only execution path
as the explanation for the current core-read stall. Further blind PMGR, GPC,
or direct-core variations are not evidence-led. The remaining measured gap is
ApplePMGR's full transition/dependency path, beyond the 66 bridge requests;
the next discriminator is a passive ordinary-PMGR writer capture during that
already proven GFX window ([review](2026-11-16-j81-pmgr-transition-gap.md)).

These are observations from specific J81 test boots, not a general device
support claim. Checkpoints after stores show software progress, not register
readback. Thus 65 table targets remain unverified by readback.

## Evidence and reproduction

The tracked [test4 capture analysis](2026-11-07-j81-test4-raw-readback-boundary.md)
explains the distinction between checkpoints and target readback. The
[core-hang analysis](2026-11-06-j81-gpu-core-hang-analysis.md) records the
unknown cause and the stop boundary. The capture helpers are in
[`boot/`](../boot/) and the small host-side test suite can be run with
`python3 tools/check_offline.py`.

Raw live-device captures are not included in this repository, so the numeric
observations above cannot be independently reproduced from a clean checkout
alone. No private Apple firmware, extracted firmware payload, serial number,
or device-specific credential is published here. Hardware experiments can
hang the device or terminate USB networking; do not treat this page as a
procedure to repeat the stalled RGX read.

## What related work establishes

- [Public ecosystem update](2026-11-07-public-gpu-ecosystem-update.md):
  Orchard's experimental J81/J82 device data, Project Cascadia's older A5 SGX
  implementation, and Mesa's public PowerVR status. None provides a working
  A8X GXA6850 driver.
- [Cascadia methods comparison](2026-11-07-cascadia-gpu-methods-for-j81.md):
  readiness tracing and Apple/Linux comparison methods that may inform
  investigation; SGX addresses, firmware, and command formats do not transfer
  to A8X.
- [A11 GPU-WIP comparison](2026-11-08-a11-gpu-wip-comparison.md): static
  A11/AGX research and its limits; A11 addresses and firmware do not apply to
  J81.

## Remaining boundary

The iOS 15 G4G probe was traced up to the identity read. Its only pre-ID
clock/power calls are one provider clock enable and one power enable, the same
as iOS 8.1 ([pre-ID clock/power trace](2026-11-08-j81-ios15-g4g-pre-id-clock-power.md)).
The iOS 15 PMGR callback is now traced through the generic per-device state
compare and state-transition helper; the dependency builder also maintains
per-device counts. The PMGR busy-edge codes `0x2700c001/2` turned out to be
kdebug trace points with no hardware effect
([trace-code note](2026-11-08-j81-pmgr-2700c00x-are-trace-codes.md)).
On iOS 15 the GFX clock gate goes to ApplePMGR's generic state path and its
state helper. The separate AppleT7000 special-action handler does not bind on
J81, but this does not exclude other bridge paths
([clock gate to PMGR state](2026-11-08-j81-ios15-clock-gate-to-pmgr-state.md)).
GFX's captured dependency record has no parent IDs or related-device object;
the increasing-state branch calls a bridge setup for selectors 9 and 10 after
the state change. Its pair-table writer and the earlier non-increasing branch
were previously conflated; the [corrected instruction trace](2026-11-09-j81-pmgr-clock-reset-path-correction.md)
describes the conditions and remaining uncertainty.
The effective Linux FDT on the inspected boot has no bridge-settings,
bridge-reg-index, or state-config properties, so it cannot answer what those
properties held in Apple's ADT or whether iOS PMGR populated `bcc56c` records
for GFX ([Linux FDT property check](2026-11-08-j81-linux-fdt-pmgr-properties.md)).
The later [`bcc56c` analysis](2026-11-08-j81-ios15-bcc56c-timing-accounting.md)
resolved its optional selector-1 action to PMGR counter reads. The alternate
pointer's mapping and whether a GFX record invokes the action remain unknown.
GFX is in an iOS 15 SoC-tuner set linked to MCC and display policy; its
runtime activation and effect on GPU reachability have not been established
([SoC-tuner note](2026-11-08-j81-ios15-soc-tuner-device-sets.md)).

Test4's planned bridge stores match the captured pair tables and the
conditional mode-0 Apple pair writer,
and its GPC operations match the inspected pre-ID sequence. Its software
checkpoints are not readback of all entries. Apple waits 10 µs after the GPC
poll; the identity-read transcript does not timestamp the actual test4
interval. Linux and XNU mapping attributes have not been compared directly
([test4 comparison](2026-11-08-j81-test4-vs-apple-pre-id-sequence.md)).

Both 8.1 and 15.8.8 LLB images contain GFX perf-control writes. A helper
hid the 15.8.8 writes from the original address scan; they can produce values
matching the later Linux capture. That is static evidence, not proof of the
last writer or of which instructions ran in the Linux boot. The selected
GPU performance state remains unknown ([bootloader analysis](2026-11-09-j81-iboot-15.8.8-first-scan.md),
[helper inventory](2026-11-09-j81-llb-indirect-pmgr-helper.md)).

The next work is to understand the A8X-specific power, reset, wake, and
ownership sequence before any further core access. Similarities to A5 SGX or
A10/A11 AGX are research leads only. There is no verified A8X initialization
recipe or rendering path yet.
