# J81 (iPad Air 2, A8X) GPU: Apple's META firmware boots under Linux

Status report, 26 November 2026. One device (iPad Air 2 Wi-Fi, J81, A8X/T7001, PowerVR GXA6850), Linux 7.3.0-rc1 (Hoolock `6831bc7`), iPadOS 15.8.5 (19H394) kernelcache as the reference. Everything below was measured on the device unless it is tagged *inferred* or *research*. The run-by-run log is [`research/2026-11-22-j81-gpu-f1-f2-result.md`](../research/2026-11-22-j81-gpu-f1-f2-result.md) (runs 12 to 64); the exact commands are in [`j81-f3a-runbook.md`](j81-f3a-runbook.md). Related: [`research/2026-11-26-j81-f3a-plan.md`](../research/2026-11-26-j81-f3a-plan.md).

## Result in one paragraph

Linux can now power the GPU, replay Apple's Fender ConfigRAM start sequence, and boot Apple's own META MTP219 firmware (loaded from a memory image we build) all the way to its **alive event**: the bootloader runs from our image through GPU page tables we build, the firmware loads its code into core memory, reads our root and state blocks, builds its internal tables, enables thread 0, posts the type-0 alive record (with the PC of its idle loop, `0x80009c14` in core memory) and idles. No fault, no BIF fault, the SoC stays up. For most of the work we did not see the record: our page-table entries for the heap are valid-only, so the firmware's writes sat in the SLC (a write-back cache) while our host read uncached DRAM; one SLC flush (RGX `0x3818 <- 1`) made the record visible (run 65). Still to do: give the heap pages Apple's flags (SLC bypass, PM/META protect) so no flush is needed, then the perf-state table, POLICY and the hardware objects, before any job. No job has been submitted and nothing rendered.

## The working sequence

1. **Power and identity (from earlier work):** PMGR `dwi` domain on (`apple,always-on`), GFX power cycle, GFX bridge settings 9 and 10 (66 stores, re-applied after *every* GFX power-on), GPC state request. The identity words read: `CORE_ID` `0x011b0803`, revision `0x00070500`.
2. **Fender ConfigRAM walk (F2, runs 12 to 44):** with GFX powered, `+0x10 = 0` and `+0 = 0x40000000`, store Apple's 31-word ConfigRAM list (SOFT_RESET x3 asserts, `META_BOOT 0x0bf8 <- 1`, `BIF_CAT_BASE0 0x1200 <- page catalogue`, SLC pair `0x3800`/`0x3808`, SOFT_RESET release, terminator `0xffff0000`) word by word at Fender `+0x10000` with a load-back each, store the override `+0x20000 = 0`, request GPC state 1 (`+0x1000 = 0x11`). **Fender replays the list into RGX at the 0 to 1 request**; afterwards `0xbf8` reads 1 (it reads 0 with an empty list), `0x3800` reads `0x00300001` (it was `0x00320001`).
3. **Firmware memory image (F3a):** one 8 MiB `dma_alloc_coherent` region (uncached, contiguous, physical `0x800d00000` on our boots); a 1 MiB blob built on the host is copied in; the module builds the 3-level GPU page tables (4 KiB pages) and patches the real page-catalogue address into `BIF_CAT_BASE0`. The blob holds the firmware heap at GPU VA `0xe1c0000000`: the layout-tool buffer (bootloader at META `0x40000000`, text, data, core-memory copy, boot list at `+0x200`, tail word at `+0xff8` = `{root, state}` firmware addresses), root (0x1490), state (0x2058), config (0x318), list-head blocks, rings.
4. **Config details that mattered:** the MMIO window table (config `+0x1c0`, 9 x `{phys, fwaddr, size}`): Fender 5 pages, AIC timer, AIC SW-int, RGX phys only, with the pages mapped in a second GPU page table at partition-9 VA `0xe1c4200000` (fwaddrs `0xc4200000`, `0xc4205000`, `0xc4206000`); config `+0x2f0 = 0x8000b3c8_20000000` (thread 1 `{sp, pc}` from the LDR START_THREADS record, sp in the high half). Without the window table the firmware faulted on its first Fender access (`TXCATCH1 = 0x1000`).

## What we learned, in order (and what we got wrong)

| When | Finding | Status |
|---|---|---|
| runs 1-9 (22-24 Nov) | The "F1 bus hang" was a tooling bug: the watchdog supervisor read stage lines into a 512-byte buffer and stopped feeding the watchdog on longer lines | fixed (module status capped at 480 bytes) |
| runs 12-39 | A non-empty ConfigRAM list only passes the override store after Apple's GFX power cycle with the **bridge settings re-applied after the power-on** (`h3pb`); earlier runs never did that | stands |
| runs 12-39, 43 | "The override store `+0x20000` hangs the bus." **Wrong.** The module mapped the Fender window with size `0x11000`, so every `+0x20000` access landed 0xf000 past the mapping, in stray kernel memory. With `GPC_SIZE 0x21000` the real release works in state 0 with Apple's full list (run 44) | corrected (request 13) |
| runs 20-23, 25 | "Reading `+0x20000` or PMGR `+0x5004` hangs." Same mapping bug, not proven for `+0x5004` | void |
| runs 38/39 | "RGX reads after a state-1 release hang." Same bug | void |
| run 47 | "The machine dies when META runs." It was our own supervisor watchdog biting during one 10 s poll step (no stage line for 10 s). Rule: no step longer than about 2 s | corrected (run 48) |
| run 43/44 | `0xbf8 = 1` after a walk is the META_BOOT entry applied by Fender; with an empty list it stays 0 | baseline closed |
| runs 40-42 | The walk applies resets, SLC_CTRL_MISC and META_BOOT at the 0 to 1 request even without the override release; `0x3808 <- 1` always reads 0 afterwards (a trigger bit, never read by Apple) | stands |
| run 50 | META's bootloader ran from our image: SEG0/1/3 programmed, I/D caches on, `TXPRIVEXT = 0x80` (MINIM_EN) | measured |
| run 51-52 | `+0x2f0` tried with the halves swapped: no effect (wrong order; Apple's order is sp high, pc low) | corrected (request 14) |
| run 53 | `TXCATCH1 = 0x1000` = Fender `+0x1000` with an empty window table | measured |
| run 54 | With the window table: thread 0 enabled, no fault, code in core memory, 121 heap words written | measured |
| run 55-56 | Firmware init completes, heap then frozen; the AIC timebase **runs** (counter at page offset `0x20`; my earlier zero reads were offsets 0/4) | stopped-clock theory falsified |
| runs 57-58 | The racy `0x80009c74` and `0x1002xxxx` PC samples were bad reads of a running thread; the PC page it showed in core memory held unwritten SRAM | explained by run 60 |
| run 60 | Halted snapshot (`TXENABLE <- 0xfffffffe`): PC `0x10000358` stable, PCX `0x10000454`; D1.5 points at the scheduler's `enqueued_commands[0]` | measured |
| run 61-64 | Thread 1 never ran; started by us (PC `0x20000000`, SP `0x8000b3c8`, then `T1ENABLE | 1`) it runs to PC `0x200004b8` and parks; neither the MTS kick (`RGX 0xb00 <- 0x10` after Fender `+0x14 <- 7`) nor a running thread 1 produces an event | measured |
| run 65 | **One SLC flush (RGX `0x3818 <- 1`) shows the alive record**: event write index 1, type 0, idle PC `0x80009c14`, `0x8000a2c8`; the heap diff goes from 121 to 323 words. The firmware had booted to alive long before; its writes sat in the write-back SLC because our heap PTEs are valid-only (Orchard's A8/A9 driver maps firmware pages with SLC bypass + PM/META protect) | measured (request 18 E0) |

## What the firmware has done, per the heap diff (121 words, 323 after an SLC flush)

(The 121 words are what had left the SLC; after the flush the diff grows to 323 words and includes the alive record in the event ring, run 65.) Early in boot (within 2 s): it read our tail word and stored root and state addresses in its globals (block at META `0x10013c00`), initialised 16-entry context lists in the 0x22000-area and the 0x8e0/0x990/0x8c0-byte list-head blocks (counters 1 to 0xf at 0x30-byte stride, self-pointers, counts `0x10`/`0xffff`), set a few scalars and a core-memory table at `0x8000a000` (flag, a pointer, nine USC exception-slot register offsets `0xe200..0xe240`, stride 8). It never wrote the event ring, the log buffers or the state block.

## What the firmware is doing now

- Thread 0: idle loop in core memory at about `0x80009c14` to `0x80009c74` (the reported "waiting for BG kick" PC is `0x80009c14`); earlier halted snapshots put the PC at `0x10000358`, a seg0 loop that polls the priority-0 `enqueued_commands` counter of the scheduler block (heap `+0x29000`, `+0x78c`): both are parts of the scheduler idle path. `T0ENABLE 0x0201c031`, no catch registers.
- Thread 1: never started by the firmware, and not needed (Orchard's A9 path does not start it either); started by us it parks at `0x200004b8`.
- The MTS kick (`RGX 0xb00 <- 0x10`) changes nothing with empty queues, as expected.
- Fender interrupt status `+0x14` reads `0x00000002` after the walk; no USC exception pending; BIF fault 0 throughout. The AIC timebase runs (counter at page offset `0x20`).

## Remaining work (from request 18, Orchard's A8/A9 reference driver)

1. **E1, page-table flags:** heap, root and shared pages `valid | bit 3 (SLC bypass) | bit 62 (PM/META protect)`; MMIO window pages `valid | bit 3`. Expected: the alive record appears without any flush.
2. **E2, the perf-state table** in config `+0x29c..+0x2e3` (counts 4 and 16, a 16-entry MHz list: 365, 450, 500, 550, 182, 225, 250, 275, rest 0) which our captured ADT leaves empty; Apple's kext refuses to start without it.
3. **E3, POLICY** (the `0x938` block, filled on Apple's boot path): `+0x10 = 1.0f`, `+0x28 = 0x1_00000001`, `+0x38 = 100`, `+0x6fc = +0x7cc = 400`, `+0x8f8` = timestamp.
4. **E4, the four hardware objects** at `0x8_00000000 + {0, 0x4000, 0x8000, 0x10000}` (colour-conversion table, BRN44455 workaround, the border-colour table which is kext data to be extracted locally, a fence buffer), named in config `+0x30`, `+0x1b8`, `+0x2f8` and the `fw+0x218` block.
5. Then the first real command (Orchard's A9 path: ring entry plus the MTS kick `0x10` TA, `0x11` 3D, `0x12` compute), after Apple's stop procedure is understood.

Still unexplained: why slave-port reads of core memory at `0x80009c40..0x80009cc0` returned noise while the thread idles near `0x80009c74`; the name and role of scheduler `+0x778`; MiniM remains undecodable (no public decoder), which is no longer a blocker for boot.

## Safety and hazards (what bit us, and what is still risky)

- The SLC is write-back for GPU pages with valid-only PTEs: the CPU (uncached DRAM view) does not see the firmware's writes until the SLC is flushed (`RGX 0x3818 <- 1`, poll `0x3898 & 0xff == 0xff`) or the pages are mapped with SLC bypass (bit 3).
- Never access a Fender or RGX register outside the mapped window. Map what you touch (the module's first mapping was too small; the RGX mapping covers only `0x4000`, higher registers need their own mapping).
- In GPC state 0 a Fender access right after another one hung the bus (spacing of 1 ms between accesses); RGX is read only in state 1 after a 0 to 1 transition.
- No single module step longer than about 2 s; the host supervisor feeds the watchdog once per stage.
- Writes that start things are one-shot and run last: thread 1 start (`f3t1start`), thread 0 halt (`f3halt`), the MTS kick (`f3kick`). Each run is one boot; there is no stop path.
- No Apple firmware or kernelcache content in public repositories: the firmware image (LDR), kernelcaches, captures and the layout tool's output (`fw-buffer.bin`, the blobs) stay private. The 66 GFX bridge settings the module replays are already in this repository (`kernel/j81-gpu/gfx-bridge-plan.h`, generated by `gen_bridge_header.py`); the OrchardLinux/gpu report does not carry them.

## Tooling

See the runbook. In short: `kernel/j81-gpu/` (module h47: step interface under `/sys/devices/j81-gpu/step`, status line), `boot/j81_gpu_run.py` and `boot/j81-gpu-run` (host runner and on-device wrapper, one `--write` per step, `--f3a-blob`), `boot/gpu-watchdog-supervisor` (feeds the watchdog per stage), `tools/j81_meta_ldr_layout.py` (offline LDR parser and layout builder, Apple's loader rules), `boot/j81_f3a_build.py` (position-independent blob builder), `tools/metag-objdump` (classic-META disassembler wrapper, copies the NAS build to a local cache because the SMB mount does not allow executing).

## Research requests (to the builder-side research agent, via the NAS mailbox)

Requests 7 to 17 were written between 25 and 26 November 2026; each result is copied under `research/2026-11-2x-j81-requestNN-*`. Highlights: 12 (the walk runs at 0 to 1, the release is not needed), 13 (the override "hang" is a mapping bug), 14 (config fields, MMIO window table, T0STATUS decode, `+0x2f0`), 15 (partial, no MiniM tooling; slave-port write protocol), 16 (partial; the `0x8000a000` structure is a USC exception slot list), 17 (the idle loop is the scheduler poll; ring layout correct; the kick value `0x10`), 18 (Orchard's A8/A9 reference driver: PTE flags with SLC bypass and PM/META protect, POLICY, perf table, hardware objects; led to the SLC flush test that found the alive record).

## Credits and method

Written with AI assistance (Claude), checked on hardware; the research agent's statements are tagged where they were inferred. Based on Orchard's A8/A10 notes and the J81 groundwork in OrchardLinux/gpu.
