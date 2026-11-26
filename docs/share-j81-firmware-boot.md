# Share texts: Discord and X chat (ready to paste; not posted by me)

## Discord

**iPad Air 2 (J81 / A8X): Apple's GPU firmware now boots under Linux, stuck at the first handshake** 🧵

On the iPad Air 2 I can now power the GPU, replay Apple's start sequence (Fender ConfigRAM), and boot Apple's own META firmware from a memory image I build on the host. It runs through its whole init, loads its code, builds its tables, and then idles with both threads parked. It never posts the first "alive" event, so the handshake iPadOS completes doesn't. No job submitted, no frame rendered yet.

**Where it stops:** the firmware is MiniM code (META's compressed 16-bit ISA) and I can't find any public decoder. binutils 2.30 (last with `metag`) only does classic META. If you have IMG's toolchain, MiniM docs, or have decoded this ISA, please shout. 🙏

**Also a correction:** my earlier "Fender override store hangs the bus" finding was a bug in my module (the window was mapped too small, I was writing stray memory). It was never a hardware hang. Please disregard those claims.

- Report + tools (PR): https://github.com/OrchardLinux/gpu/pull/10
- Notes, runbook, full run log (runs 12 to 64): https://github.com/mattonik/ipad-nixos/blob/main/docs/j81-gpu-firmware-boot.md
- Runbook with the exact steps: https://github.com/mattonik/ipad-nixos/blob/main/docs/j81-f3a-runbook.md

One device, Linux 7.3.0-rc1 on Orchard's `apple-4k` pin. No Apple data is published; the tools read from your own kernelcache. Written with AI assistance (Claude), checked on the hardware.

## X chat

iPad Air 2 (J81/A8X): Apple's GPU firmware now boots under Linux. It runs its whole init, loads its code, builds its tables, then idles with both threads parked; the first "alive" event never comes, so the handshake iPadOS completes doesn't. Blocker: the firmware is MiniM (META's compressed ISA) and there's no public decoder. Anyone with MiniM docs or IMG's toolchain? Also a correction: my earlier "Fender hang" claim was a bug in my module, not hardware. Report/PR: https://github.com/OrchardLinux/gpu/pull/10 Notes + runbook: https://github.com/mattonik/ipad-nixos/blob/main/docs/j81-gpu-firmware-boot.md
