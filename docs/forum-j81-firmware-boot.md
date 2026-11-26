# Draft: forum message (not posted; the forum itself is not decided). Updated after run 65 (alive reached).

**Subject:** iPad Air 2 (J81, A8X): Apple's GPU firmware boots to its alive event under Linux

Short version: on an iPad Air 2 I can now power the GPU, replay Apple's start sequence, and boot Apple's own META firmware from a memory image I build on the host. It runs through its whole initialisation and posts its first "alive" event, with the PC of its idle loop. I only saw the event after one flush of the GPU's write-back cache (SLC): my page-table entries for the firmware's memory were valid-only, so its writes sat in the cache while my host read uncached DRAM. Orchard's A8/A9 driver maps those pages with SLC bypass and PM/META protect, and that is my next change.

**What works (measured on one device, Linux 7.3.0-rc1 on Orchard's `apple-4k` pin):**
- Fender ConfigRAM replay at the GPC 0 to 1 request, with the GFX bridge settings re-applied after every GFX power-on.
- Host-built GPU page tables and firmware heap in an 8 MiB DMA region; the META bootloader runs from it, the firmware loads its code into core memory, reads my root/state blocks, builds its tables, posts alive and idles. No META fault, no BIF fault, the SoC stays up.

**Not yet:** the correct page-table flags, the perf-state table, the POLICY block and the firmware's hardware objects (all listed in the notes, from Orchard's reference driver), and then a first job. No job has been submitted and nothing is rendered.

**Corrections to what I said before:** the "Fender override store hangs the bus" finding was a bug in my module (the Fender window was mapped too small, so I was writing stray memory). It was never a hardware hang. If you saw my earlier claims, please disregard them. Also: the MiniM code (META's compressed ISA) cannot be decoded with public tools, which I had thought was a blocker; for boot it is not.

Thanks to the Orchard A8/A9 notes: the comparison with their working driver is what pointed at the cache flags.

Notes, runbook and the run log: https://github.com/mattonik/ipad-nixos (`docs/j81-gpu-firmware-boot.md`); offline tools and the report in the OrchardLinux/gpu PR https://github.com/OrchardLinux/gpu/pull/10. No Apple data is published; the tools read from your own kernelcache. Written with AI assistance (Claude), checked on the hardware.
