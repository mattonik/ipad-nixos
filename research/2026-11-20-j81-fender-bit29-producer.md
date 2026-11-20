# Fender sleep-control bit 29 on J81

The successful 19H394 iPadOS observer explicitly writes **0x40000000** to Fender +0 (physical 0x201e00000). That value requests bit 30 and leaves bit 29 clear. The observer then polls **Fender +0x1000** until its low five bits equal 1, tests **PMGR 0x20e005004** bit 30, and proceeds to the GPU-ID load. There is no bit-29 software gate in that path. The working boot returned 0x00070500. The physical value of bit 29 at that instant remains unknown.

## Two ways the stock driver writes this register

The 19H394 debug dump reads register +0 at kernel VA suffix 0x669bc00 and prints it under the name **AGX_CR_FNDR_TIMER_SLEEP_CONTROL**. The pre-inspection dump at 0x669c1dc also reads it. Neither string names bit 29 individually.

| Path | Input to the 32-bit store at Fender +0 | Scope |
|---|---|---|
| Stock method 0x669c224, virtual slot +0x58 | Immediate 0x40000000 | Reads the word back into WZR, discarding the value. |
| Stock method 0x669c3c8, virtual slot +0x68 | Entire W1 argument | Also discards the readback. The generic setter does not mask bit 29. |
| Working observer 0x4308–4314 | Immediate 0x40000000 | Calls its store helper. Its later ID path has no call to the stock setter or paired-bit guard. |

One concrete caller of the generic setter is the type-6 branch of 0x6693ea8. At 0x6693f04–3f18 it selects a 44-byte record using the index pointed to by controller+0x338 and loads its word at +4 into W20. The record array is reached through controller+0x358. This path first invokes the literal setter at 0x6693f28. It polls and programs RGX/META registers before forwarding the saved word through slot +0x68 at 0x6694220–4230. Stock code elsewhere identifies this array in a diagnostic as outstanding firmware events. The active record and its author are absent from the successful boot evidence. A set bit in that record would request a set bit at the register; acceptance or persistence requires readback. The event path already uses the RGX aperture and supplies no evidence of an initial unlock. The older A8X driver also handles type 6 in a recovery path. [Earlier event dispatch](2026-11-07-j81-g4g-event-dispatch.md)

There is a further reachability constraint. The event loop at 0x668cac4 indexes a signed-offset switch table at 0x668cffc. Entry 0 leads to the call through controller slot +0x388 at 0x668caf0. Entry 6 leads directly to the index advance at 0x668caa0. The controller vtable contains the handler at +0x388, but a type-6 record in this particular ring loop does **not** dispatch its type-6 branch. A different caller, a runtime payload and timing evidence would be needed to identify that branch as an actual producer. The retained firmware loader metadata describes image loading, not the contents of the running ring. [Firmware image cross-check](2026-11-11-j81-ldr-crosscheck.md)

## Why the stock checks disagree

The factory installs **0xfffffff006f2fee8** at 0x669b008–669b010. Using that address point resolves a mistaken call target in the November 17 trace. Code addresses above and below omit the high prefix 0xfffffff000000000.

* Slot +0xa0 (0x669c4a8) requires control bits 29 and 30 both set, waits for the busy bit at +0x1000 to clear, then calls slot +0x18. That slot is the state getter at 0x6698f24. It returns zero when the object's enable byte is clear, otherwise the low nibble of +0x1000. The guard requires a zero getter result and zero at Fender +8. The override handshake at +0x20000 is a separate method in slot +0x60.
* The enclosing predicate at 0x669c444 also has a fallback. When the paired-bit guard fails and the state getter returns zero, it accepts control bits [31:30] equal to binary 01, irrespective of bit 29.
* Another controller predicate at 0x6692828 requires an in-range state, then uses slot +0x78 to extract bit 29 from the control getter. This predicate rejects a set bit. These methods test different conditions. None appears in the working observer's branch from the GPC poll to GPU-ID.

## What the captures can settle

On the late Linux boot (49df36fd), an actual control read returned 0x40000000 with page 5 high and the GPU-ID attempt produced no result. On the working iPadOS boot (846527FB), the observer reused X23 for stack-backed log formatting at 0x437c. Its read at 0x43f0–43f8 used this log pointer. The P1 field G=30303000 cannot supply a control readback. The three P1 F words are genuine page-5 samples. The older successful DCE69446 log also prints the same G value. [Three-boot comparison](2026-11-20-j81-gpu-id-capture-comparison.md)

Prioritize an independent, same-boot iPadOS readback of **AGX_CR_FNDR_TIMER_SLEEP_CONTROL** between the successful GPC poll and the GPU-ID load. A clear sample immediately before a returned ID would weigh against a continuously asserted prerequisite; a set sample would establish coexistence and make an earlier readback the next discriminator. Either permits transient changes between samples. A later pre-inspection dump or type-6 event can inform the writer investigation separately. Neither can establish what the hardware required for the first ID.


## Offline test

Run `python3 tools/test_j81_fender_control.py /path/to/decompressed/19H394/kernel` on Apple Silicon macOS with clang. The test pins the kernel digest, checks the dispatcher and vtable, then executes the stock setter, getter and predicate instructions on a host RAM fixture. All 64 combinations of control bits [31:29], getter enable, idle performance state 0/1 and kick status 0/1 passed. This validates the CPU-side word and branch logic. The fixture cannot model MMIO acceptance, asynchronous transitions or the timing of a working device.
