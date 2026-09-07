# iPad NixOS

## Goal

Boot NixOS on old iPads (2011-2017, A5–A11 chips) via checkm8 bootrom exploit, turning e-waste into usable Linux machines.

## Status (2026-09-07): Linux boots to an interactive shell

The `bootm` → m1n1 route (`docs/software-only-control.md`) got a real
hardware run on 2026-09-07 and, after four precisely-diagnosed bugs found
and fixed live across the session, **reached a live, interactive
postmarketOS `/ #` shell prompt on this exact iPad Air 2** -- the project's
primary goal, achieved in full. Bugs fixed in order: a missing newline in
the payload parser; a device-tree CPU-topology format mismatch; a misnamed
framebuffer node; and, decisively, a power-domain auto-shutdown
(`genpd_power_off_unused()`, a `late_initcall()` in Apple's PMGR driver)
that was killing the display's `disp0`/`dp` power domains right after
driver probing finished, fixed with `pd_ignore_unused clk_ignore_unused` on
the kernel command line. (An earlier theory blamed the bundled postmarketOS
Xperia Z5 debug initramfs hiding its own output -- ruled out once its own
unconditional startup marker never appeared on screen even after testing at
120fps, which is what led to finding the real, kernel-level cause instead.)

**Update, Round 6**: USB gadget enumeration is confirmed working on
hardware. `m1n1-control` now uses the *historical* kernel's own DTB (it
has the real `usbdev@20c100000`/`apple,t7000-usb` node mainline lacks),
patched with CPU-cell, framebuffer, and `cpu-release-addr` fixes (Rounds
3-5 below). On real hardware this boots Linux completely: `g_ether` binds
to the real USB controller, and the Mac sees a live USB device
(`0525:a4a2`, confirmed via `pyusb`/`ioreg`) with postmarketOS's
`172.16.42.1:23` telnet startup reported on screen. Remote interaction
has not yet been demonstrated.

**Current USB handoff, after Round 7 (2026-09-07):** disabling
`CONFIG_USB_ETH_EEM` lets macOS bind `AppleUSBCDCECMData` and create `en10`.
The host still receives zero packets, including after a verified direct
Mac-to-iPad connection. ARP is incomplete; ping and TCP port 23 time out.
The old assertion that this proves a DWC2 bulk-transfer bug was too strong:
we have not measured device-side RX/TX or USB completions. Forced-off DMA
explains the warning but does not validate PIO operation on T7001.

The user authorized display diagnostics and further USB research.
`m1n1-usb-diagnostic` is implemented, built and archive-verified; it preserves
the working kernel/DTB/bootloaders and overlays only the debug-shell hook.
It has **not yet been uploaded or tested on hardware**. The user was asked
to enter DFU and run PongoOS in their terminal because sudo needs a password.
Next: upload the diagnostic payload once `05ac:4141` appears, photograph its
three pages, compare host/device counters, then select the next experiment.

Hoolock's newer matched kernel/DTB is a researched upgrade candidate, not
yet built. Our pinned m1n1 already has its AUSB PHY tunable handoff. Do not
blindly swap only the DTB, enable DMA, or tune nonexistent FIFO bootargs.
See [the complete session handoff](research/t7001-usb-next.md) for changes,
checks, artifact hash, source links, rollback and ordered next steps.
Session changes remain uncommitted/unpushed; the original control is intact.

Full evidence and commands are in `docs/software-only-control.md`'s
"Round 3" through "Round 7".

Driver work (touch, Wi-Fi, etc.) remains explicitly approval-gated --
booting Linux does not change that; wait for the user before starting any
of it, per "Driver readiness and approval gate" in `docs/project-status.md`.

The historical-PongoOS control is a separate, lower-priority experiment,
still blocked: `palera1n`'s stager rejects its 708,704-byte binary (limit
is 0x7fe00 = 523,776 bytes) -- unresolved, not needed now that m1n1 works.

Do not resume blind changes to the modern PongoOS fork's direct-jump path;
that specific mechanism has been tried seven ways and ruled out each time.
A7–A8X Linux uses 4 KiB pages; older 16 KiB claims in historical logs are
superseded. Touch and Wi-Fi work still requires explicit user approval after
Linux boots.

## Target Hardware

- **Primary target**: iPad Air 2 (A8X, 2014) — 3-core ARM64, 2GB RAM, PowerVR GXA6850 GPU
- **Exploit**: checkm8 (permanent, unpatchable bootrom vulnerability for A5–A11)
- **Boot chain**: checkm8 → pongoOS → Linux kernel → NixOS userland

## Project Structure

```
ipad-nixos/
├── research/          # Phase 0 output — feasibility analysis
│   ├── landscape.md   # Existing projects analysis
│   ├── hardware.md    # iPad Air 2 hardware mapping
│   ├── boot-chain.md  # Full boot path documentation
│   ├── driver-gap.md  # Driver status matrix
│   └── feasibility.md # Final assessment and roadmap
├── boot/              # Boot chain tools and configs
├── kernel/            # Kernel configs and patches
├── nixos/             # NixOS configuration for iPad
├── drivers/           # Custom driver work
├── devenv.nix         # Development environment
├── flake.nix          # Nix flake
└── CLAUDE.md          # This file
```

## Phase 0: Research & Feasibility (autonomous)

Systematic analysis of all existing work. No hardware needed.

1. **Landscape analysis** — deep-dive every existing project:
   - checkm8 / checkra1n (bootrom exploit)
   - pongoOS (pre-boot environment)
   - Project Sandcastle (Android on iPhone)
   - postmarketOS iPhone/iPad support
   - linux-on-iphone GitHub projects
   - Asahi Linux (Apple Silicon Macs — different but relevant techniques)
   - Corellium (commercial iOS virtualization — published research)

2. **Hardware mapping** — iPad Air 2 (A8X) specifics:
   - SoC architecture, memory map, peripheral addresses
   - Device tree sources (from iOS firmware, existing Linux DTs)
   - Display controller, touch controller IC identification
   - WiFi/BT chip (Broadcom model, firmware requirements)
   - GPU (PowerVR GXA6850) — driver status in Mesa/open-source

3. **Boot chain documentation** — full path for iPad specifically:
   - checkm8 exploit execution
   - pongoOS loading and capabilities
   - Linux kernel handoff (how pongoOS passes control)
   - Device tree passing, initramfs requirements
   - What works on iPhone 7 that could transfer to iPad Air 2

4. **Driver gap matrix** — per subsystem:
   - Display: existing framebuffer support, DRM/KMS status
   - Touch: multi-touch controller RE status
   - WiFi: Broadcom chip model, firmware, driver (brcmfmac? wl?)
   - GPU: PowerVR open-source driver status (Mesa PVR?)
   - Audio: codec identification, ALSA/PipeWire feasibility
   - Battery/charging: power management IC
   - USB: host/device mode capabilities
   - Bluetooth: chip, firmware, driver
   - Sensors: accelerometer, ambient light, etc.

5. **NixOS scaffolding** — aarch64 cross-compilation:
   - Base NixOS config targeting A8X
   - Cross-compilation flake setup
   - Minimal rootfs generation

## Phase 1+: Hardware-in-the-loop (interactive)

Requires physical iPad + USB connection to NixOS workstation.

### Feedback Loop Setup

```
NixOS ThinkPad ──USB──► iPad Air 2
     │                      │
     ├─ Claude reads serial ◄─ /dev/ttyACM0 (boot logs)
     ├─ Claude builds kernel
     ├─ Claude prepares flash scripts
     │
     └─ User: runs ./flash.sh, takes photos for display testing
```

### Tools

- `libimobiledevice` — iOS USB communication
- `libirecovery` — recovery/DFU mode
- `picocom` — serial console reader
- `ghidra` / `radare2` — binary analysis
- Nix cross-compilation for aarch64

## Guidelines

- Research first, code second
- Document every finding in research/ directory
- Be honest about blockers and difficulty
- Cross-reference multiple sources before concluding anything
- Focus on iPad Air 2 (A8X) specifically — don't generalize across all iPads
