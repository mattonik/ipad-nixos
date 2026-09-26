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
| Charging current | D2207 register `0x04c0` accepts and retains writes; all tested tiers through 2400 mA are hardware-validated | 1000 mA and above produced stable positive charging current. |
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
enough to change the gauge from `Discharging` to `Charging`.  2400 mA is the
highest hardware-validated limit and is available from the diagnostic TUI.  The
value resets on reboot, which is why a boot-time policy is useful.

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

1. On boot, set `input_current_limit` to 2400000 microamps.
2. Every 30 seconds, read the BQ27545 `temp` and `capacity` files.
3. Set the limit back to 100000 microamps when temperature reaches 42.0 C or
   capacity reaches 80 percent; otherwise leave it at 2400000 microamps.
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

### Is 2400 mA enough?

For the present lightweight payload, the evidence says **yes**.  The J81 tests
at 1000, 2100 and 2400 mA all settled around the same 100--115 mA net battery
charge, with stable temperature, voltage and USB networking.  The extra input
headroom did not turn into a faster battery charge.  `input_current_limit` is
only the maximum input current the charger may draw; it is not a command to
force that current.  This is also the meaning of the standard Linux
[`input_current_limit`](https://docs.kernel.org/power/power_supply_class.html)
property.

Static Apple-driver analysis shows a wider *encoding* range: 75--3262 mA for
`0x04c0`.  It does not make higher values safe or useful on this cable.  The
same PMIC record currently reports a 3000 mA configured battery-charge limit
and a 3150 mA hardware charge-current ceiling, which are separate from the USB
input limit.  The TUI consequently rejects requests above the highest actual
J81 validation, 2400 mA.

Before considering a one-step higher test, obtain the following evidence while
the already validated 2400 mA limit is active:

| Read-only observation | Interpretation | Decision |
| --- | --- | --- |
| D2207 VBUS-current ADC is well below 2400 mA and VBUS voltage is stable | The PMIC is not reaching the present ceiling; a higher ceiling cannot increase input power. | Keep 2400 mA; investigate battery charge state or source capability only if faster charging becomes important. |
| VBUS current reaches the ceiling while voltage, temperature and USB link remain stable | The limit may be constraining the source. | A separately authorized, one-step test can be designed with a USB power meter and immediate rollback. |
| VBUS voltage sags, USB re-enumerates, temperature rises, or a PMIC fault appears | The source/cable/thermal path is constraining. | Lower the limit; do not test higher values. |

Apple's D2207 driver identifies VBUS-current ADC channel 9 and VBUS-voltage ADC
channel 19.  Their interface is now recovered, but it is not a passive register
read and therefore does not belong in the host TUI as an `i2ctransfer` shortcut.
A physical USB power meter remains the preferred cross-check.  No higher PMIC
write is justified until the first two observations agree.

#### Recovered D2207 VBUS ADC interface

The evidence is the same iPad5,3 12B410 kernelcache used for the earlier
charger work (SHA-256
`19c277d60e0a1185b1e4a1b72cda4f1f550c0b0bf670791542234a6dbbcc28bf`).
`AppleD2207PMUPowerSource` has two wrappers at `0xffffff8002b4cbdc` and
`0xffffff8002b4cbf4`; they request ADC channels 19 and 9 respectively through
`AppleDialogPMU`.  The provider vtable resolves those requests to D2207's
voltage conversion at `0xffffff8002b49200`, current conversion at
`0xffffff8002b494c0`, and raw conversion routine at
`0xffffff8002b4821c`.  This independently ties the channel numbers to the
power-source's VBUS telemetry rather than merely finding the constants in a
generic ADC table.

The raw conversion sequence is:

1. Serialize access to the ADC engine.  Preserve the driver's cached control
   bits, insert `channel & 0x3f`, set bit 7, and write the resulting byte to
   `0x0500` to start a conversion.  Some channels also temporarily use bit 6
   of `0x0501` before the start.
2. Wait for the PMIC ADC-complete event.  Apple's driver waits on its interrupt
   state with a one-second timeout; it does not poll the result bytes blindly.
3. Read two bytes from `0x0502`.  Decode the 12-bit sample as
   `(byte[1] << 4) | (byte[0] & 0x0f)`.  The upper nibble of `byte[0]` is state,
   not sample data; channel 9 is one of the explicitly permitted signed-state
   cases.
4. Clear the temporary ADC controls: read `0x0501`, retain only bits 0--2 and
   write it back; clear bit 7 from the saved `0x0500` byte and write that back;
   then release the serialized ADC operation.

The conversion formulas, including Apple's integer truncation, are exact:

| Quantity | Channel | Raw-to-engineering conversion | Resolution |
| --- | ---: | --- | ---: |
| VBUS current | 9 | `floor(raw * 52800 / 1000)` mA | 52.8 mA/count |
| VBUS voltage | 19 | `floor(raw * 96192 / 1000)` mV | 96.192 mV/count |

The two power-source wrappers pass a unity fixed-point multiplier
(`0x10000`), so those D2207 results are already milliamps and millivolts; there
is no additional board-specific scale in this J81 call path.

This is a read-only *measurement* in Apple's API, but not an I2C read-only
transaction: starting and acknowledging a conversion necessarily writes the
ADC control registers.  Direct host commands are consequently not proven safe
or complete.  The correct implementation point is the kernel PMIC driver,
where access can be serialized and the ADC-complete interrupt handled.  Only
after that driver exports a stable snapshot should the host TUI display it.

At the validated `0x04c0` 2400 mA setting, collect VBUS current and voltage in
the same snapshot as the BQ27545 battery current, voltage and temperature:

- VBUS current within one ADC count of 2400 mA with stable VBUS means the
  programmed input ceiling is plausibly binding; this is the only result that
  supports designing a separately authorized higher-limit test.
- VBUS current materially below 2400 mA means `0x04c0` is not binding.  Raising
  it cannot create more input power.
- Current below the ceiling together with falling VBUS voltage or USB resets
  identifies the source/cable path as the constraint.  Stable VBUS and stable
  input current, while net battery current stays near the observed
  100--115 mA, instead points downstream: system load, the battery charge
  controller or battery charge acceptance.  Comparing input power
  (`VBUS mV * VBUS mA`) with battery power (`battery mV * battery mA`) separates
  system consumption from battery acceptance; neither battery current alone
  nor the `0x04c0` setting can do that.

## USB access and services

The useful near-term form is a **tethered appliance**, not an independent
networked tablet:

1. Keep ECM exactly as it is: static iPad address `172.16.42.1`, direct cable,
   RAM-only root.  It is the only verified data path and it also provides
   power.
2. Replace the debug-shell's unauthenticated telnet only after a minimal,
   key-only SSH binary and its runtime libraries have been copied into an
   overlay and tested.  Do not expose an HTTP service first: SSH already gives
   an authenticated shell, remote commands and log retrieval in one small
   service.  File transfer and forwarding are separate capabilities and are
   not part of the first acceptance gate below.
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

### Verified debug-initrd and SSH packaging audit, 2026-09-26

The audit used the built, hardware-proven `m1n1-hoolock-control` initramfs,
not the separate NixOS initramfs experiment. Its exact startup contract is:

- `/init` mounts proc, sysfs, devpts and configfs, installs the BusyBox
  applets, initializes mdev and the framebuffer, then executes each hook
  synchronously as `sh "$hook"`.
- The existing `20-debug-shell.sh` sources `/etc/deviceinfo` and
  `/init_functions.sh`, calls `setup_usb_network` and `start_udhcpd`, starts
  telnet, then deliberately enters `loop_forever`. It does not return to
  `/init`; returning would continue into root-partition discovery and violate
  this payload's RAM-only appliance model.
- The two network helpers are already one-shot operations. The first uses a
  marker in `/tmp`; the second recognizes its generated `/etc/udhcpd.conf`.
  Reuse them instead of duplicating the configfs gadget setup.
- The known-good control archive already has a later `etc/deviceinfo` entry
  selecting `deviceinfo_usb_rndis_function="ecm.usb0"`. Derive the service
  package from `m1n1-hoolock-control`; starting again from upstream
  `debug_initrd.img` would silently restore the unusable RNDIS default.

The exact replacement pattern is another uncompressed `newc` archive appended
to the decompressed control initramfs. Its hook path is
`etc/postmarketos-mkinitfs/hooks/20-debug-shell.sh`, without a leading `./`,
mode `0755`, uid/gid zero. Recompress with `gzip -n`. The first hook starts the
existing telnet recovery daemon, starts Dropbear in the background, checks
that its PID remains alive, and finishes with the existing `loop_forever`.
An SSH packaging failure must not let the hook fall through into storage
probing. The SSH-only follow-up keeps this non-returning lifecycle.

The current pinned `pkgsCrossMusl` Dropbear is **not static**. The evaluated
Dropbear 2025.89 daemon has a Nix-store musl interpreter and `DT_NEEDED`
entries for `libz.so.1`, `libcrypt.so.2` and `libc.so`, with absolute
Nix-store `RUNPATH` entries. `dropbearkey` needs musl and zlib. Raw CPIO does
not perform the dependency copying that `makeInitrdNG` performs for
`nixos/initramfs.nix`, and the base image's older
`/lib/ld-musl-aarch64.so.1` cannot satisfy the executable's hard-coded
interpreter path. The first implementation should reuse the existing package
and include the daemon, key generator, exact interpreter and runtime closure
at their original paths. A static rebuild is unnecessary just to save roughly
two megabytes in this RAM-only image.

The archive check must read every ELF `PT_INTERP`, `DT_NEEDED` and `RUNPATH`
and prove the loader and libraries exist at the exact archived paths. Merely
checking that the daemon itself is present is insufficient.

Dropbear also needs state absent from the base image: a root entry in
`/etc/passwd`, `/etc/group`, `/var/empty`, `/root` and
`/root/.ssh/authorized_keys`. `/root` and `.ssh` must be mode `0700`;
`authorized_keys` must be `0600`. Only a public client key belongs in the
archive. Bind Dropbear to `${IP}:22` and pass `-s` for key-only authentication.
`-g` means "disable root password login", not "permit root", and is redundant
with `-s`. Disable local and remote forwarding with `-j -k` for the first
test; enable a specific forwarding use later if it is actually needed.

Because the root filesystem is volatile, a host key generated at boot changes
after a cold boot. That is acceptable for the first direct-cable experiment
only when its fingerprint is checked over the retained telnet/console path.
A private host key must not be committed or copied through a world-readable
Nix store merely to stabilize the fingerprint. Persistent host identity needs
a separate secret-delivery design after SSH works.

The evaluated Dropbear output contains neither `scp` nor an SFTP server, and
its compiled SFTP helper path does not exist in this initramfs. Modern macOS
`scp` uses SFTP by default, so file-copy success must not be claimed in the
first test. A bounded file can instead be streamed through a remote shell and
verified by hash. Package an SFTP server only when convenient file transfer
becomes a real requirement.

#### Safe staged test

**Static gate:** build a separate package derived from
`m1n1-hoolock-control`. Require PongoOS, m1n1, DTB, kernel and bootargs to be
byte-identical to that control; require the new uncompressed initramfs to begin
with the complete control archive; parse all concatenated `newc` members with
last-entry-wins semantics; and compare the added entries with an exact
allow-list of the replacement hook, Dropbear closure, public key and minimal
account files. Run `sh -n` on the final hook, verify its CPIO metadata, check
all ELF dependencies as above, and verify final payload assembly and hashes.
Reuse the archive parser and invariants in `boot/test_usb_diagnostic.py`; a
second parser would add risk without evidence.

**Hardware stage 1, recovery retained:** cold-boot the isolated payload over
the direct cable. Require the same ECM enumeration, host address
`172.16.42.2/24`, successful ping, and working telnet at
`172.16.42.1:23`. From telnet, confirm Dropbear stayed alive, its log has no
loader/library error, and ports 22 and 23 are bound only to `172.16.42.1`.
Check the generated host-key fingerprint, then require:

1. the intended public key opens both a remote command and an interactive PTY;
2. a wrong key is rejected;
3. a password-only attempt is rejected;
4. three SSH disconnect/reconnect cycles leave ECM, telnet and Dropbear
   healthy; and
5. one small file streamed through `ssh` has the same hash in `/tmp`.

This first stage is a packaging/recovery test, **not yet a secure
replacement**, because unauthenticated telnet remains open.

**Hardware stage 2, SSH-only:** only after stage 1 succeeds across a second
cold boot, build the same overlay without starting telnet. Require port 23 to
be closed, repeat the authentication and reconnect checks, and confirm the
hook remains in RAM-only hold if Dropbear exits. This is the point where the
service becomes the secure USB baseline. Keep the known-good control payload
as the DFU recovery artifact; do not combine this test with charging-policy,
PCIe, Bluetooth or touch changes.

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
| 1 | Boot the existing charging-writable test and perform its narrow 2400 mA check | It converts a proven raw PMIC mechanism into the normal kernel interface without adding a new driver | Sysfs value and raw register agree; 30 s gauge observation stays clean and charging. |
| 2 | Add the small boot-time charging service | Removes the per-boot manual operation using only evidence-backed values | Cold boot reaches 2400 mA; 42 C and 80% simulations/read-only review show the fallback is 100 mA. |
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
