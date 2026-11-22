# Lead: Orchard PR #196 / brkosebay "a8-gpu-tester-kit-4" (A8 GPU running under Linux)

Source: public GitHub pages read 2026-11-22 (release brkosebay/hardware a8-gpu-tester-kit-4, OrchardLinux/orchard PR #196).
Third-party claims, read via a fetch agent, NOT verified by us; nothing downloaded or run.

Claims:
- A8 (iPod touch 6, n102, GX6450, BVNC reported 3.10.4.5) runs Apple's GPU firmware (extracted from the iPod touch 6 iOS 12.4 IPSW by tools/extract-fw.py) under a PATCHED mainline powervr driver: A8 is a variant of the existing S8003 (A9) chip file (kernel patches 0063-0073 under kernel/patches/drivers/gpu/, pvr_apple.c / pvr_apple_chip.h).
- Boot and power up/down "in Apple's order" (patch 0067); Fender, power-manager and GPU-bridge registers described in devices/t7000/0011 (t7000.dtsi); doorbell, parameter-manager pool, region-header ring in the HWRT data set.
- Tested only on iPod touch 6: probe, compute and TA/3D jobs, Vulkan 1.2 via Mesa powervr (OrchardLinux/mesa#18, branch pvr/g5p), GLES 3.1 via Zink, soak 514k jobs. iPad mini 4 (J96/J97), iPhone 6/6+ untested. Our iPad Air 2 (J81, A8X, G4G) is not listed.
- PR open; kernel from the branch "built but not yet flown". Related: #203 (firmware in recipes), #204 (display pipe).

Why it matters: contradicts our researcher's working assumption that Apple's firmware interface is not upstream's (packet 8 RESULT, T2). This is a patched upstream driver with an Apple-firmware path, i.e. a concrete source for the init blocks, rings, doorbell and Fender handling. Caveat: A8 vs A8X, different GPU core config.
To do: read the patches (0063-0073), t7000.dtsi GPU/Fender nodes and extract-fw.py; compare with packet 8's Fender ConfigRAM and boot-list findings; hand to the research agent.
