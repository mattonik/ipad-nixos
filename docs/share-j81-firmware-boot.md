# Share texts: Discord and X chat (ready to paste; not posted by me). Updated after run 65 (alive reached).

## Discord

**iPad Air 2 (J81 / A8X): Apple's GPU firmware boots to its alive event under Linux** 🧵

Update to my earlier note. On the iPad Air 2 I can power the GPU, replay Apple's start sequence (Fender ConfigRAM), and boot Apple's own META firmware from a memory image I build on the host. It runs its whole init, loads its code, builds its tables and **posts its "alive" event with the PC of its idle loop**. I only saw the event after one SLC flush: my page-table entries for the firmware's memory were valid-only, so its writes sat in the GPU's write-back cache while my host read uncached DRAM. Orchard's A8/A9 driver maps those pages with SLC bypass + PM/META protect; that is the next change. No job submitted, no frame rendered yet.

**Thanks** to the Orchard A8/A9 notes for the comparison that pointed at this. **Correction:** my earlier "Fender override store hangs the bus" finding was a bug in my module (window mapped too small, I wrote stray memory); it was never a hardware hang. Please disregard those claims. (The firmware code is MiniM, which nobody can decode publicly; that is no longer needed for boot.)

- Report + tools (PR): https://github.com/OrchardLinux/gpu/pull/10
- Notes, runbook, full run log: https://github.com/mattonik/ipad-nixos/blob/main/docs/j81-gpu-firmware-boot.md
- Runbook: https://github.com/mattonik/ipad-nixos/blob/main/docs/j81-f3a-runbook.md

One device, Linux 7.3.0-rc1 on Orchard's `apple-4k` pin. No Apple data is published; the tools read from your own kernelcache. Written with AI assistance (Claude), checked on the hardware.

## X chat

iPad Air 2 (J81/A8X): Apple's GPU firmware now boots to its "alive" event under Linux. It runs its whole init, loads its code and posts alive with its idle-loop PC; I only saw it after one SLC flush (my firmware pages were not mapped with SLC bypass, so its writes sat in the GPU cache). Next: Apple's page-table flags, perf table, then a first job. Correction: my earlier "Fender hang" claim was a bug in my module, not hardware. Report/PR: https://github.com/OrchardLinux/gpu/pull/10 Notes + runbook: https://github.com/mattonik/ipad-nixos/blob/main/docs/j81-gpu-firmware-boot.md
