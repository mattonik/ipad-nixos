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

**The only remaining gap**: postmarketOS's debug-shell hook also starts a
telnet daemon (`172.16.42.1:23`), but the modern mainline DTB used for that
boot has no T7001 USB-device-controller node (`g_ether` printed "couldn't
find an available UDC" during the same boot), so there was no USB network
link to reach it over -- the shell was alive, just had no input channel.

**In progress, not yet confirmed working**: `m1n1-control` now uses the
*historical* kernel's own DTB (it has the real `usbdev@20c100000`,
`apple,t7000-usb` node mainline lacks, matched by a real driver already in
this same kernel), patched with the same CPU-cell and framebuffer fixes
proven on the modern DTB. `pd_ignore_unused clk_ignore_unused` and
`PMOS_NO_OUTPUT_REDIRECT` stay in bootargs. `example.config` already has
everything the USB gadget path needs (`CONFIG_USB_GADGET`,
`CONFIG_USB_ETH`, `CONFIG_USB_ETH_RNDIS`, etc.). **UART is not needed** --
this is a concrete, well-understood, software-only gap.

First hardware run of the historical DTB (Round 4) failed differently: m1n1
couldn't add `cpu-release-addr` to the secondary CPU nodes because the
recompiled DTB had zero spare room to grow into (this historical DTS
predates mainline's placeholder-property convention). Fixed by compiling
with `dtc -p 0x10000` (64 KiB padding); verified locally, not yet
re-tested on hardware. Full evidence and commands are in
`docs/software-only-control.md`'s "Round 3" and "Round 4".

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
