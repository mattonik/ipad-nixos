# J81 GPU driver roadmap: from identity read to something visible (2026-11-22)

Honest state: Linux can power the GPU, open its bus and read BVNC 7.5.8.3 (7.5 = G4G A1). Nothing runs ON the GPU yet. Anything visual (a triangle, a compute result) needs the GPU firmware processor running, which needs: firmware image in memory, GPU MMU/address-space setup, a reset/release of the firmware core, and a first host-firmware handshake. Packet 5 (post-ID bring-up research) is still open and covers exactly this.

Tangible steps now, in order:
1. One in-kernel driver `j81-gpu` that does the whole recipe itself at boot (today it is a userspace-staged one-shot with separate tools and a module), exposes `gpu/bvnc`, state and the identity words in sysfs, and shows "GPU: BVNC 7.5.8.3, powered" on the iPad dashboard. Removes the one-shot-per-boot staging and is the base for everything after.
2. Read-only RGX register survey (clock gating, soft reset, META/firmware core status, interrupt status) with crumb markers; each new read documented before it runs. Gives the map the research needs.
3. When packet 5 arrives: firmware copy and memory layout, then the META reset/release test with the 20 s watchdog.
4. First handshake, then a trivial firmware-driven action; only after that any visual test.
