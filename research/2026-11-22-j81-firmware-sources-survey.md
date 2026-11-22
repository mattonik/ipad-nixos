# Survey: public sources about GPU firmware relevant to J81 (2026-11-22)

Question: is there anything in OrchardLinux or other public git repos that helps load and boot the J81 (A8X, Rogue + META MTP219) GPU firmware? Claims below are from reading pages and repos; none verified on J81.

**OrchardLinux/gpu (local clone, main at a426e00)**
- `a10/`: a working Apple A10 (T8010, iPad 6) GPU: CORE_ID 0x011b0602 (legacy format) and CORE_REVISION 0x000d0a00; Apple GFX firmware runs on an RTKit ARM32 coprocessor; compute works end to end; Hyprland via Zink and a Mesa fork with an Apple "G9P" Vulkan backend. Guide: `a10/bringup/README.md` ("A10 first, A9 and later next"; lists what is unknown for A9). Fender notes: `a10/FENDER.md` (88 KB). Driver plan: `a10/DRIVER.md` (Apple variant of drm/imagination, powervr UAPI, Rogue MMU with 16 KiB pages, Apple pwr_ops). `a10/REFERENCE.md`: Rogue fixed-function (PDS, CDM, page tables, RGX_CR_*), Apple shader ISA on A10.
- **Useful for J81:** same Rogue register and MMU concepts; the upper half of CORE_ID, 0x011b, is the same as on the A10, so it is a common Apple/Rogue ID field (resolves our open question); Fender (GPC) concept and state-1 request; firmware extraction from a kernelcache (`tools/a10/tools/extract-firmware.sh`, offset-based); the "Apple firmware variant of powervr" driver shape; Mesa fork `OrchardLinux/mesa`.
- **Not reusable as-is:** the A10 firmware is an RTKit IOP image with its own init data; J81 runs a META LDR image with Apple's older interface. The A10 shader core is Apple's ISA; whether the A8X's is stock Rogue (so upstream Mesa pco for 6XT might apply) is unknown.
- Other org repos: orchard (kernel layers, devices), mesa (PowerVR driver fork), linux, m1n1, packages; nothing for A8/A9 firmware found.

**Imagination's open-source side**
- Mainline `drivers/gpu/drm/imagination` supports META, MIPS, RISC-V firmware processors and Series 6XT (GX6250, GX6650 4.46.6.62) with Imagination's own firmware (freedesktop gitlab firmware repo); its firmware interface is the newer IMG one, not Apple's. Used here only for register/boot reference (snapshot in the research packets).
- Imagination Rogue DDK kernel-module mirrors (MIT): https://fuchsia.googlesource.com/third_party/imgtec-pvr-rgx-km/ (rgx_fwif_km.h, rgx_fwif_alignchecks.h, rgxinit.c, rgxfwload.h, hwdefs), the older Android tree https://android.googlesource.com/kernel/x86_64/+/606832966f458025cc2860316dfa201f3b9a3738/drivers/staging/imgtec/rogue/ and vendor img-rogue 1.x trees. These are the best candidates to decode Apple's init blocks (Apple's META interface descends from the DDK of the same era; unverified). Handed to the research agent as packet `2026-11-22-j81-research-ldr-tool-fwif-sources` (T2).
- poulsback.in: SGX535 (Intel GMA500) driver, not related.
- jeroentrappers n61 (A8) g4p driver was reviewed in an earlier packet.
