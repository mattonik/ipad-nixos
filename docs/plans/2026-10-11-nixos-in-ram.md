# NixOS in RAM on the iPad Air 2: from the postmarketOS debug initramfs to a real NixOS userland

Status: design plus a feasibility measurement started 2026-10-11 (flake output `nixosConfigurations.ipad-air2-ram`, `nixos/ipad-air2-ram.nix`). Nothing here has run on the iPad yet.

## Why
Every boot so far runs the postmarketOS *debug initramfs* (busybox, a boot hook, telnet/SSH recovery, our charging, Wi-Fi and dashboard scripts). It is a test harness, not an operating system, and the project is called ipad-nixos. With Wi-Fi, charging, USB networking, the tablet dashboard and SSH
now working, the next milestone toward a usable tethered tablet is a real NixOS userland: declarative services, a package set, `nix` tooling on the host side, and a base for touch, audio and a UI later.

## Constraints (all measured or documented)
- **No persistent storage.** The internal NAND is deliberately read-only (ANS1 observation-only). Everything lives in RAM: **2 GB**, shared with the kernel and the Wi-Fi/DMA buffers.
- **Every boot is a checkm8 cycle** (DFU, `palera1n`, `load_m1n1.py`): the whole payload is uploaded over USB each time, so payload size is upload time (17.5 MB payload today). A bigger payload (hundreds of MB) needs a measured upload time and a check of PongoOS's size limit before committing to it.
- **The kernel is the Hoolock J81 one** (7.3-rc1, cross-built, `m1n1-hoolock-wifi`), monolithic for the board drivers; it is not a NixOS kernel. The payload carries kernel + DTB + initramfs; NixOS must supply only the userland.
- **Kernel features present** (checked in the production `.config`, 2026-10-11): cgroups, namespaces (PID, NET, USER), devtmpfs (+ automount), tmpfs with POSIX ACL and xattrs, inotify, fhandle, signalfd, timerfd, epoll, seccomp, BPF syscall, AUTOFS, configfs + USB ECM gadget, ext4, loop, initrd with zstd/xz/gzip.
  **Missing:** `SQUASHFS` (+`SQUASHFS_ZSTD`/`XZ`), `EROFS_FS`, `OVERLAY_FS` (and `CGROUP_BPF`, `FUSE_FS`, which systemd/NixOS can live without). Without a compressed read-only store the closure would have to be unpacked fully into RAM.
- **Private assets stay private:** the BCM4350 firmware/NVRAM and the Wi-Fi credentials are never in the Nix store or Git; they arrive through the private payload overlay exactly as today (`boot/assemble_private_wifi_payload.py`).

## Options
| | A. NixOS netboot-style initrd (squashfs store in the initramfs) | B. Tiny initramfs + root fetched over the network | C. Root on internal storage |
|---|---|---|---|
| Idea | initramfs carries a squashfs Nix store; stage-1 mounts it, overlays a tmpfs, switches root to NixOS | the current small initramfs fetches a squashfs/tarball from the Mac over USB ECM or Wi-Fi, then `switch_root` | persistent NixOS on the NAND |
| Payload size | closure compressed (see measurements) | stays ~17 MB | n/a |
| Boot dependence on the host | none after upload | needs the host server up | none |
| Iteration cost | rebuild + re-upload per change (every boot is a DFU cycle anyway) | change the served rootfs without rebuilding the payload | n/a |
| Kernel needs | squashfs, overlayfs (small config change) | squashfs or a big tmpfs; networking in stage 1 | NAND write support: **blocked by policy** |
| Risk | upload time/size limit; NixOS stage-1 on a monolithic kernel | more moving parts at boot | high; explicitly out of scope |

**Recommendation: A first**, because it is self-contained (the iPad boots NixOS with only USB attached, the same flow as every boot today), then reconsider B if the payload turns out too large to upload comfortably. C is excluded.

## Plan
1. **Measure** (started): minimal NixOS closure size and its squashfs size (`system.build.toplevel`, `system.build.squashfsStore` of `nixosConfigurations.ipad-air2-ram`). Also time and check the limit of uploading a payload of that size through PongoOS.
2. **Kernel config additions** in the production kernel (one rebuild, bundled with the other pending kernel work: the gauge retry, toggle clean-up): `CONFIG_SQUASHFS=y`, `SQUASHFS_ZSTD=y`, `SQUASHFS_XZ=y`, `OVERLAY_FS=y`, optionally `EROFS_FS=y`, `CGROUP_BPF=y`.
3. **NixOS configuration** (`nixos/ipad-air2-ram.nix`): netboot module for the RAM root; OpenSSH key-only (the repo's public `boot/ssh/authorized_keys`); the existing pieces as NixOS modules/systemd units:
   - USB gadget networking (ECM at 172.16.42.1, DHCP for the Mac) as a oneshot service replacing the postmarketOS `setup_usb_network`;
   - Wi-Fi: `wpa_supplicant` (our config from a private file copied from the initramfs at stage 1), `hardware.wirelessRegulatoryDatabase = true`, DHCP via `systemd-networkd` or `dhcpcd`;
   - charging policy (`boot/charging-policy.sh`) as a service, including the gauge re-probe;
   - the tablet dashboard on tty1 (replacing the getty) with the 16x32 console font;
   - firmware: the private BCM4350 files placed under `/lib/firmware` from the private overlay before the driver probes.
4. **Stage-1 secrets and firmware:** extra cpio overlays appended to the initrd by the assembler already work for the busybox initramfs; for NixOS stage-1, copy `/lib/firmware` and the private config into the real root in a `postMountCommands` hook (the netboot initrd switches root, so anything left in the initramfs root disappears).
5. **Assemble and test:** a payload = Hoolock Image + DTB + NixOS netboot initrd (+ private overlay); one DFU run; success = SSH login over USB, Wi-Fi up, dashboard on screen, charging policy running.
6. **Then:** declarative touch/audio/UI work becomes ordinary NixOS module work.

## Open questions
- Upload size/time limit of PongoOS for a payload of 100-300 MB (not yet measured).
- Whether NixOS stage-1 (scripted or systemd) works with a monolithic kernel that was not built by nixpkgs (`boot.kernelPackages`, module tree, `system.requiredKernelConfig`): the netboot initrd normally embeds the NixOS kernel's modules; we ship our own kernel, so stage-1 must not insist on loading modules.
- RAM budget: squashfs pages are decompressed on demand, the tmpfs overlay and tmpfs `/run`, `/tmp` grow with use: set sensible tmpfs limits so DMA/Wi-Fi buffers keep their memory.

## Feasibility measurement
(filled in when the build finishes)
