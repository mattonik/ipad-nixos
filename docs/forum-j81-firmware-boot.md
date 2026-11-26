# Draft: forum message (not posted; the forum itself is not decided)

**Subject:** iPad Air 2 (J81, A8X): Apple's GPU firmware boots under Linux, stuck at the first handshake: does anyone have MiniM tooling?

Short version: on an iPad Air 2 I can now power the GPU, replay Apple's start sequence, and boot Apple's own META firmware from a memory image I build on the host. It runs through its whole initialisation and then idles with both threads parked, and it never posts the first "alive" event, so the handshake iPadOS completes does not. I'm stuck because the firmware is MiniM code (META's compressed 16-bit ISA) and I cannot find any public decoder.

**What works (measured on one device, Linux 7.3.0-rc1 on Orchard's `apple-4k` pin):**
- Fender ConfigRAM replay at the GPC 0 to 1 request, with the GFX bridge settings re-applied after every GFX power-on.
- Host-built GPU page tables and firmware heap in an 8 MiB DMA region; the META bootloader runs from it, programs its segments and caches, the firmware loads its code into core memory, reads my root/state blocks and builds its tables.
- No META fault, no BIF fault, the SoC stays up. Thread 0 parks in the firmware's scheduler idle loop (polling the priority-0 queue count, as far as I can tell from Apple's own debug dump).

**Corrections to what I said before:** the "Fender override store hangs the bus" finding was a bug in my module (the Fender window was mapped too small, so I was writing stray memory). It was never a hardware hang. If you saw my earlier claims, please disregard them.

**What I don't know:** what the firmware waits on before the alive record. Thread 1 is never started by the firmware (started by me it runs and also parks); the doorbell the host uses (`RGX 0xb00 <- 0x10`) changes nothing; the AIC timebase runs; no USC exception is pending. That needs the firmware code.

**The ask:** binutils 2.30 (the last release with the `metag` target) decodes classic META but not MiniM; I found no MiniM spec. If anyone has IMG's toolchain, MiniM documentation, or has decoded this ISA, I'd love to hear. Halted single-stepping through the core-register port is my fallback.

Notes, runbook and the run log: https://github.com/mattonik/ipad-nixos (`docs/j81-gpu-firmware-boot.md`), offline tools and the report in the OrchardLinux/gpu PR (link once opened). No Apple data is published; the tools read from your own kernelcache. Written with AI assistance (Claude), checked on the hardware.
