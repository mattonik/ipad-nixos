# J81 (iPad Air 2, A8X) GPU: Apple's META firmware boots under Linux

Status report, 26 November 2026. One device (iPad Air 2 Wi-Fi, J81, A8X/T7001, PowerVR GXA6850), Linux 7.3.0-rc1 (Hoolock `6831bc7`), iPadOS 15.8.5 (19H394) kernelcache as the reference. Everything below was measured on the device unless it is tagged *inferred* or *research*. The run-by-run log is [`research/2026-11-22-j81-gpu-f1-f2-result.md`](../research/2026-11-22-j81-gpu-f1-f2-result.md) (runs 12 to 64); the exact commands are in [`j81-f3a-runbook.md`](j81-f3a-runbook.md). Related: [`research/2026-11-26-j81-f3a-plan.md`](../research/2026-11-26-j81-f3a-plan.md).

## Result in one paragraph

Linux can now power the GPU, replay Apple's Fender ConfigRAM start sequence, and boot Apple's own META MTP219 firmware (loaded from a memory image we build) all the way through the firmware's initialisation: the bootloader runs from our image through GPU page tables we build, the firmware loads its code into core memory, reads our root and state blocks, builds its internal tables, enables thread 0 and parks it in its scheduler idle loop. No fault, no BIF fault, the SoC stays up. **What does not happen yet:** the firmware never posts its first ("alive") event record, so the host handshake that iPadOS completes does not complete. Thread 1 is never started by the firmware; started by us it runs and also parks. The firmware is MiniM code (compressed 16-bit instruction set) for which no public decoder exists, so what both threads wait on is unknown. This is where the work stops for now.

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

## What the firmware has done, per the heap diff (121 words)

Early in boot (within 2 s, then nothing for at least 6 s): it read our tail word and stored root and state addresses in its globals (block at META `0x10013c00`), initialised 16-entry context lists in the 0x22000-area and the 0x8e0/0x990/0x8c0-byte list-head blocks (counters 1 to 0xf at 0x30-byte stride, self-pointers, counts `0x10`/`0xffff`), set a few scalars and a core-memory table at `0x8000a000` (flag, a pointer, nine USC exception-slot register offsets `0xe200..0xe240`, stride 8). It never wrote the event ring, the log buffers or the state block.

## What the firmware is doing now

- Thread 0: parked at PC `0x10000358` (a small loop at about `0x10000340` to `0x100003a0`, reached from the routine at `0x10000260`), polling the priority-0 `enqueued_commands` counter of the firmware scheduler block (the `0x8e0`-byte block at heap `+0x29000`, `+0x78c`). `T0ENABLE 0x0201c031`, no catch registers, `TXSTATUS` toggles `0x00020000`..`0x00020809`.
- Thread 1: dead until we start it, then parked at `0x200004b8`.
- Fender interrupt status `+0x14` reads `0x00000002` after the walk; we clear it with a write of 7 (no effect observed).
- No USC exception pending (RGX `0xe100`/`0xe200` slots read invalid). The BIF fault register is 0 throughout.

## Open question

What does the firmware wait on before posting the type-0 event record (the record carries the PC of the "waiting for BG kick" idle loop; Apple's host sets `fw+0xb35` from the interrupt path and `waitForFWAlive` returns)? On iOS the host gives it nothing beyond the release, the 0 to 1 request and the AIC unmask for lines `0x86`/`0x87`/`0x8a`. Candidates not excluded: something thread 1 does at a point it never reaches because it is not started by the firmware; a config or state field left at zero (config `+0x30`, `+0x38..+0x1b7`, `+0x1b8`, `+0x290..+0x29b`, `+0x2f8`, root `+0x490..`); an AIC interrupt (we did not unmask lines `0x86`/`0x87`/`0x8a`, which should not matter because the record is written to memory first); the first real command. All of these need the firmware code to settle.

## What would unblock it

1. **A MiniM decoder** (none public; binutils 2.30, the last release with the `metag` target, has classic META only: `opcodes/metag-dis.c` contains no MiniM; a built copy is on the NAS under `tools/metag-binutils-2.30/` for classic code). Options: reverse the compressed encoding from the image with the register snapshots as anchors (days), or find someone with IMG's toolchain.
2. Halted single-stepping of thread 0 through the core-register port (not tried): would give a PC trace and register effects per instruction.
3. Systematic field probing (config/state fields), low expected value.

## Safety and hazards (what bit us, and what is still risky)

- Never access a Fender or RGX register outside the mapped window. Map what you touch (the module's first mapping was too small; the RGX mapping covers only `0x4000`, higher registers need their own mapping).
- In GPC state 0 a Fender access right after another one hung the bus (spacing of 1 ms between accesses); RGX is read only in state 1 after a 0 to 1 transition.
- No single module step longer than about 2 s; the host supervisor feeds the watchdog once per stage.
- Writes that start things are one-shot and run last: thread 1 start (`f3t1start`), thread 0 halt (`f3halt`), the MTS kick (`f3kick`). Each run is one boot; there is no stop path.
- No Apple firmware or kernelcache content in public repositories: the firmware image (LDR), kernelcaches, captures and the layout tool's output (`fw-buffer.bin`, the blobs) stay private. The 66 GFX bridge settings the module replays are already in this repository (`kernel/j81-gpu/gfx-bridge-plan.h`, generated by `gen_bridge_header.py`); the OrchardLinux/gpu report does not carry them.

## Tooling

See the runbook. In short: `kernel/j81-gpu/` (module h47: step interface under `/sys/devices/j81-gpu/step`, status line), `boot/j81_gpu_run.py` and `boot/j81-gpu-run` (host runner and on-device wrapper, one `--write` per step, `--f3a-blob`), `boot/gpu-watchdog-supervisor` (feeds the watchdog per stage), `tools/j81_meta_ldr_layout.py` (offline LDR parser and layout builder, Apple's loader rules), `boot/j81_f3a_build.py` (position-independent blob builder), `tools/metag-objdump` (classic-META disassembler wrapper, copies the NAS build to a local cache because the SMB mount does not allow executing).

## Research requests (to the builder-side research agent, via the NAS mailbox)

Requests 7 to 17 were written between 25 and 26 November 2026; each result is copied under `research/2026-11-2x-j81-requestNN-*`. Highlights: 12 (the walk runs at 0 to 1, the release is not needed), 13 (the override "hang" is a mapping bug), 14 (config fields, MMIO window table, T0STATUS decode, `+0x2f0`), 15 (partial, no MiniM tooling; slave-port write protocol), 16 (partial; the `0x8000a000` structure is a USC exception slot list), 17 (the idle loop is the scheduler poll; ring layout correct; the kick value `0x10`).

## Credits and method

Written with AI assistance (Claude), checked on hardware; the research agent's statements are tagged where they were inferred. Based on Orchard's A8/A10 notes and the J81 groundwork in OrchardLinux/gpu.
