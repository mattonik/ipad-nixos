# J81 tethered-tablet baseline and charging plan

## Purpose

The immediate goal is a useful, light Linux terminal/tablet while Wi-Fi,
Bluetooth and touch remain blocked by the D2207 GPIO ownership question.  It
must boot entirely in RAM, keep the known-good USB link, and charge without
an operator entering raw PMIC commands after every boot.  It is deliberately
not a proposal to write the internal NAND, add a desktop environment, or
claim a touchscreen interface before its power rail and firmware work.

## What is already real

| Capability | Evidence | Practical result |
| --- | --- | --- |
| Linux boot and display | Hoolock Linux 7.3-rc1 is the active hardware baseline | The iPad can show its boot/debug console. |
| USB networking | `m1n1-hoolock-control` uses the base image's configfs gadget with `ecm.usb0`; bidirectional traffic and telnet at `172.16.42.1:23` were hardware-verified | A connected Mac can control the iPad and transfer results over the same cable that powers it. |
| Battery measurement | The BQ27545 gauge reports status, current, voltage, temperature and capacity | Charging policy has feedback rather than operating blind. |
| Charging current | D2207 register `0x04c0` accepts and retains writes; 100 through 2500 mA are hardware-validated | 1000 mA and above produced stable positive charging current. |
| Reusable operator control | `boot/ipad_console.py` reads the gauge and D2207, offers validated tiers, verifies writeback, and has tests | Safe exploratory charging does not require hand-written I2C commands. |

The successful payload is **not** the standalone `nixos/initramfs.nix`
experiment.  The booted Hoolock payload is the old postmarketOS debug initrd
from `linux-apple-resources`, plus a tiny CPIO overlay which changes its USB
function from unavailable RNDIS to working ECM.  A fresh audit of that exact
base image found BusyBox, `telnetd`, `fbdebug`, `evtest`, and the debug-shell
hook.  It does not contain Dropbear, an SSH server, a web server, or a general
GUI toolkit.  Any tablet-facing change must preserve this base image and use a
small, reproducible overlay; replacing it with the untested NixOS initramfs
would discard the known-good boot and USB path.

## Charging: the next concrete work

The present 100 mA boot default is a policy omission, not a missing charger
driver.  `0x04c0 = 0x4a` selects a hardware-validated 1000 mA limit and was
enough to change the gauge from `Discharging` to `Charging`.  2500 mA is also
hardware-validated and is available from the diagnostic TUI.  The value resets
on reboot, which is why a boot-time policy is useful.

The smallest path is already prepared: the isolated
`m1n1-hoolock-charging-writable-test` payload contains patch `0017`, exposing
the existing charger driver as the normal Linux file:

```
/sys/class/power_supply/j81-d2207-charger/input_current_limit
```

It cross-builds cleanly but has not run on J81 hardware.  Its first hardware
test must be deliberately limited to reading the property, comparing it with
the raw `0x04c0` value, writing the previously validated `1000000` microamp
value, checking the readback, and observing the gauge for 30 seconds.  No
other PMIC register belongs in that test.

If that succeeds, the next payload needs only one small shell service started
by the existing debug hook.  It should use the sysfs property, not
`i2ctransfer`, and apply this fixed policy:

1. On boot, set `input_current_limit` to 2500000 microamps.
2. Every 30 seconds, read the BQ27545 `temp` and `capacity` files.
3. Set the limit back to 100000 microamps when temperature reaches 42.0 C or
   capacity reaches 80 percent; otherwise leave it at 2500000 microamps.
4. Log each transition once to `/tmp`, which is RAM-only.

This directly implements the existing conservative 42 C / 80% instruction.
It must never touch D2207 `0x0010` bit 2: hardware testing proved that bit
suspends USB input and worsens charging.  A locally running service also avoids
the misleading idea that loss of the USB host should itself stop charging.

There is one documentation/code discrepancy to resolve before implementing
that service: `boot/ipad_console.py` currently restores its interactive
high-tier experiment to 1000 mA after an abort, while the older charging log
records 100 mA as the required 80% cutoff.  The service must follow the
explicit 100 mA cutoff above; the interactive tool can be aligned separately
with a small tested change.

## USB access and services

The useful near-term form is a **tethered appliance**, not an independent
networked tablet:

1. Keep ECM exactly as it is: static iPad address `172.16.42.1`, direct cable,
   RAM-only root.  It is the only verified data path and it also provides
   power.
2. Replace the debug-shell's unauthenticated telnet only after a minimal,
   key-only SSH binary and its runtime libraries have been copied into an
   overlay and tested.  Do not expose an HTTP service first: SSH already gives
   authenticated shell, file copy, port forwarding and log retrieval in one
   small service.
3. Keep telnet as the recovery method in the first SSH experiment.  Remove it
   only after reconnecting by SSH across a cold boot.
4. Add a tiny read-only `tablet-status` shell command before any graphical
   interface.  It can print battery state, current, temperature, charge limit,
   USB address, uptime and the last kernel messages.  BusyBox and sysfs already
   supply everything it needs; no Python, web framework or database is
   warranted.

The base image's debug hook starts `telnetd` on the USB address and loops in
RAM.  Therefore the appropriate implementation mechanism is an overlay that
replaces just that hook (or wraps it), leaving `/init`, USB setup, DHCP and the
ECM `deviceinfo` override byte-for-byte unchanged.  Before creating this
overlay, audit the dynamic libraries required by the chosen SSH binary and
verify that the existing hook provides a usable process lifecycle.  This is a
software-only packaging task; it does not need a new hardware hypothesis.

This is not a new packaging technique: `m1n1-usb-diagnostic` already appends a
second `newc` archive containing a replacement
`etc/postmarketos-mkinitfs/hooks/20-debug-shell.sh`.  The tablet payload should
reuse that exact pattern.  The replacement hook can first call the base
`setup_usb_network` and `start_udhcpd` functions, then start the charging
service, status command and SSH server.  It must retain telnet in this first
revision, so a bad SSH package cannot lock us out.  A musl-static SSH server is
preferred; a dynamically linked binary is acceptable only when its loader and
complete library closure are included and checked in the assembled archive.

## On-screen interface

There is no reason to add Weston, Qt or a Wayland compositor now.  GPU
acceleration and touch are unavailable, and the current base image has only
BusyBox and framebuffer diagnostics.  The first local interface should be a
text status screen on the already booted console, with USB SSH as its control
path.  It would make the device understandable while charging: IP address,
battery percentage, charging/discharging state, temperature and uptime.

Before implementing it, run only these read-only checks on the active payload:

```
cat /proc/consoles
ls -l /dev/fb* /sys/class/graphics
cat /sys/class/graphics/fb0/name
cat /proc/bus/input/devices
```

They distinguish a usable framebuffer console from a splash-only display and
show whether a button input device already exists.  A static text status page
is worthwhile if the console is present.  Menu navigation should wait for a
confirmed input device; touch remains a separate driver and power problem.

## Sequencing and acceptance gates

| Order | Work | Why it comes now | Gate to advance |
| --- | --- | --- | --- |
| 1 | Boot the existing charging-writable test and perform its narrow 2500 mA check | It converts a proven raw PMIC mechanism into the normal kernel interface without adding a new driver | Sysfs value and raw register agree; 30 s gauge observation stays clean and charging. |
| 2 | Add the small boot-time charging service | Removes the per-boot manual operation using only evidence-backed values | Cold boot reaches 2500 mA; 42 C and 80% simulations/read-only review show the fallback is 100 mA. |
| 3 | Package key-only SSH beside the existing telnet recovery shell | Makes the USB link usable for normal development and file transfer | SSH reconnects after a cold boot; telnet fallback still works during this first step. |
| 4 | Add `tablet-status`, then validate the framebuffer console | Gives immediate local feedback with no graphics dependency | All fields display correctly and continue updating over a 30-minute charging session. |
| 5 | Add optional button navigation only if an input device is present | Avoids inventing input support | Button events are observed and a read-only menu works. |
| 6 | Return to Wi-Fi, Bluetooth and touch after the D2207 capture hardware is available | Those subsystems remain blocked by non-persistent PMIC GPIO control | Passive iPadOS trace identifies the additional PMIC transaction or ownership state. |

This route provides a modest but honest result: a bootable iPad display with a
local status view, safe charging and a secure USB-tethered Linux shell.  It
does not depend on PCIe enumeration, Bluetooth, GPU acceleration, touch or
writable NAND, so progress can continue while those investigations wait for
the logic-analyser evidence.

## Research record

- Current payload construction: `flake.nix` package
  `m1n1-hoolock-control`.
- USB evidence and boot-chain history: `docs/software-only-control.md` and
  `research/t7001-usb-next.md`.
- Charging live evidence and Stage 2 implementation:
  `docs/plans/2026-09-13-pmic-pcie-execution.md`.
- Host-side controlled charging tool: `boot/ipad_console.py` and
  `boot/test_ipad_console.py`.
- The actual archived base initrd audited here is pinned by
  `linuxAppleResources` in `flake.nix`; its `20-debug-shell.sh` hook supplies
  the current telnet shell.
