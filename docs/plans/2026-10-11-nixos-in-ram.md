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

**Recommendation (revised after the measurements below): a hybrid, "B-prime".** Keep the small initramfs as stage 1; after USB networking is up it **fetches a squashfs of the NixOS system from the Mac over the USB link into RAM**, loop-mounts it, adds a tmpfs overlay and `switch_root`s into the NixOS stage 2.
Reason: the payload stays ~17 MB (PongoOS upload is the slow channel), while the USB Ethernet link is fast (11 MB/s measured), so the multi-hundred-MB root does not have to ride through PongoOS. A change to the NixOS system needs only a rebuild and a new file on the Mac's HTTP server plus the normal boot cycle, no payload re-assembly.
Option A (everything in the initrd) remains possible for a self-contained image; C is excluded.

## Plan
1. **Measure** (done, below).
2. **Kernel config additions** in the production kernel (one rebuild, bundled with the other pending kernel work: the gauge retry, toggle clean-up, optionally the UART 3 Mbaud change): `CONFIG_SQUASHFS=y`, `SQUASHFS_ZSTD=y`, `SQUASHFS_XZ=y`, `OVERLAY_FS=y`, optionally `EROFS_FS=y`, `CGROUP_BPF=y`.
3. **NixOS configuration** (`nixos/ipad-air2-ram.nix`): a RAM-resident system whose toplevel `init` is the stage-2 entry; OpenSSH key-only (`boot/ssh/authorized_keys`); our existing pieces as systemd units:
   - USB gadget networking is already up from stage 1 (keep the interface configuration, 172.16.42.1, DHCP for the Mac);
   - Wi-Fi: `wpa_supplicant` with a private config copied from the initramfs, `hardware.wirelessRegulatoryDatabase = true`, DHCP via `systemd-networkd`;
   - charging policy (`boot/charging-policy.sh`) as a service, including the gauge re-probe;
   - the tablet dashboard on tty1 (replacing the getty) with the 16x32 console font;
   - firmware: the private BCM4350 files stay in `/lib/firmware`, copied into the new root before the switch.
4. **Stage-1 hook** (in the public base initramfs): after `setup_usb_network`, if a kernel argument `j81.nixos=http://172.16.42.2:8000/` is present: wait for the server, `wget` `root.squashfs` into a tmpfs, `losetup`/`mount -t squashfs`, overlay (lowerdir = squashfs, upperdir = tmpfs), bind-mount `/nix/store`, copy the private overlay files, then `exec switch_root /newroot $(cat /newroot/toplevel-path)/init`. **On any failure it falls back to today's telnet/SSH recovery shell**, so the current debugging flow is never lost.
5. **Host side:** a build script that builds the toplevel, makes the squashfs (`mksquashfs ... -comp zstd`), and serves it (`python3 -m http.server --bind 172.16.42.2`); the private overlay and credentials stay in the private payload as today.
6. **Assemble and test:** one DFU run; success = NixOS stage 2 reached, SSH login over USB, Wi-Fi up, dashboard on screen, charging policy running.
7. **Then:** declarative touch/audio/UI work becomes ordinary NixOS module work.

## Open questions
- Upload size/time limit of PongoOS for a payload of 100-300 MB (not yet measured).
- Whether NixOS stage-1 (scripted or systemd) works with a monolithic kernel that was not built by nixpkgs (`boot.kernelPackages`, module tree, `system.requiredKernelConfig`): the netboot initrd normally embeds the NixOS kernel's modules; we ship our own kernel, so stage-1 must not insist on loading modules.
- RAM budget: squashfs pages are decompressed on demand, the tmpfs overlay and tmpfs `/run`, `/tmp` grow with use: set sensible tmpfs limits so DMA/Wi-Fi buffers keep their memory.

## Feasibility measurements (2026-10-11)
- **Closure of the minimal NixOS (`nixosConfigurations.ipad-air2-ram`, aarch64-linux, built on the aarch64 builder):** first variant 968 MiB, trimmed variant 937 MiB, of which the stock NixOS kernel (187 MiB), its modules (114 MiB) and initrd (11 MiB) are not shipped (the Hoolock J81 kernel comes from the payload): **~626 MiB userland**. Biggest remaining parts: systemd 70 MiB (+27 minimal), perl 57 MiB, glibc 40 MiB, ICU 38 MiB, boost 16 MiB, glib 16 MiB, util-linux ~38 MiB, hwdb 13 MiB, coreutils 12 MiB.
  perl comes from the user-management/activation scripts (replace with `services.userborn`), boost/ICU from the `nix` package that the netboot module's `postBootCommands` uses (`nix-store --load-db`; unnecessary here and removable). Removing those should bring the userland to roughly 450 MiB.
- **Squashfs of the first variant: 291 MiB** (zstd/xz class compression, ratio ~3.3x incl. the 300 MiB kernel); the userland alone should be roughly 150-200 MiB.
- **Transfer speed:** USB Ethernet (usb0, high-speed ECM) to the running iPad: **100 MB in 9 s (~11 MB/s)**; so ~200 MB takes ~20 s. Wi-Fi measured earlier at ~228 Mbit/s down (5 GHz) is an alternative channel. PongoOS upload speed for the 17 MB payload has not been timed yet (to be timed on the next load).
- **RAM:** the iPad reports 1927 MiB total and ~1850 MiB free on a production-style boot; a ~200 MB squashfs file in tmpfs plus a modest writable overlay fits comfortably.

## Status 2026-10-12: stage-1 hand-off built and dry-run on the iPad

- **Trimmed system:** `nixos/ipad-air2-ram.nix` no longer imports the netboot module and has no kernel, initrd or bootloader (the J81 kernel comes from the m1n1 payload). Closure 563 MB (403 paths; was 983 MB with the NixOS kernel), squashfs `packages.aarch64-linux.ipad-air2-ram-rootfs` 125 MB (zstd level 19, was 299 MB). Perl (59 MB) is still in it (activation scripts).
- **Stage-1 hand-off:** `boot/nixos-handoff.sh` (functions sourced by PID 1; `switch_root` needs PID 1 and the debug hooks run as children, so the `nixosHandoff` payload option ships a modified `/init`: the original plus one block right after the hook loop, and the debug hook returns to `/init` when `j81.nixos=` is on the command line). Fetches `root.squashfs` and `toplevel` from `boot/nixos_ram_serve.py` on the Mac (only those two files), loop-mounts, overlays the store, copies the private `/lib/firmware`, `/root/.ssh`, `/etc/wpa_supplicant.conf` from the initramfs, kills the stage-1 daemons and switches root. Any failure leaves the telnet/SSH recovery loop.
- **Live dry run on the running iPad (T7):** 125 MB downloaded in 11 s, squashfs mounted (404 store paths), overlay mounted, copies done, clean unmount. In a chroot on the live iPad `iw` 6.17, the store busybox and **systemd 259** run on the Hoolock kernel; the stage-2 init script is present. Busybox `losetup` has no `--show` (fixed).
- **Payload:** `m1n1-hoolock-wifi-nixos` (same kernel as m1n1-hoolock-wifi, bootarg `j81.nixos=http://172.16.42.2:8000/`), assembled privately with `boot/assemble_private_wifi_payload.py` (no extra bootarg needed). First real boot: start `boot/nixos_ram_serve.py` (retries until the Mac's USB address exists), then `boot/run_m1n1_debug.sh <payload>`.
