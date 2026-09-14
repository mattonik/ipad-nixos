# J81 PMIC and PCIe execution record

**Started:** 2026-09-13  
**Scope:** unblock the D2207-controlled peripherals without speculative live
PMIC writes, and turn the now-decoded J81 PCIe topology into a reviewable,
compile-only implementation target.

## Starting point

The real iPad Air 2 (J81/T7001) already boots the Hoolock 7.3-rc1 payload and
has bidirectional USB CDC-ECM networking.  Battery-gauge telemetry works over
UART5/HDQ, SPI3 has registered on hardware, and ANS1 has been read safely in
an observation-only configuration.  Bluetooth UART attach creates `hci0` but
the BCM43540 does not respond while D2207 GPIO2 is low.  Touch needs D2207
LDO14 and the Apple firmware/calibration path.  The observed D2207 USB input
limit is 100 mA, which explains discharge during a USB-network session.

The detailed state before this execution pass remains in
`docs/project-status.md`, `docs/plans/2026-09-08-j81-bluetooth-battery-adt.md`,
and `docs/plans/2026-09-13-j81-wifi-pcie.md`.

## Safety boundary

The only raw D2207 write attempted so far was a GPIO2 configuration write.
It returned a successful I2C transfer but its subsequent readback did not
change.  Therefore this pass does **not** issue further live PMIC writes.
The first task is to recover the Apple PMIC driver's real write/protection
protocol from local static artifacts.  A live test is permitted only after a
specific transaction, rollback readback, and affected rail/GPIO are all
evidenced.

## Work performed in this pass

1. Confirmed the repository starts clean at `579ef86`; origin matches `main`.
2. Confirmed the existing `m1n1-hoolock-control` package includes the
   read-only D2207 charging child.  It exposes only `INPUT_CURRENT_LIMIT` and
   `CONSTANT_CHARGE_CURRENT_MAX`; it has no write callback.
3. Attempted a local no-link Nix build.  This workstation has no `nix`
   executable.  The configured `builder@linux-builder` SSH endpoint at
   `127.0.0.1:31022` also refused connections, so a fresh build cannot be
   claimed from this session.
4. Kept the previous successful remote build as historical evidence only.  To
   rebuild, start the repository-local `darwin.linux-builder-vz` VM using the
   exact procedure in `docs/build-infrastructure.md`, then run:

   ```sh
   nix build .#packages.x86_64-linux.m1n1-hoolock-control --no-link -L
   ```

5. Started two offline implementation tracks: D2207 write-path recovery and
   a disabled-by-default T7000 PCIe-host skeleton.  Their results are recorded
   below when reviewed.

## PCIe compile-only result

The first PCIe change is deliberately an inert kernel-integration checkpoint:

- `kernel/patches/0016-pcie-apple-t7000-compile-only-skeleton.patch` adds
  `CONFIG_PCIE_APPLE_T7000` and a platform driver for a future
  `apple,t7000-pcie` node.
- `kernel/hoolock-pcie-check.nix` and the
  `hoolock-pcie-check-kernel` flake package make it possible to compile that
  patch without changing the normal Hoolock kernel or any boot payload.
- The probe validates exactly twelve firmware register windows and four port
  interrupts, then returns `-EOPNOTSUPP`.  It does not map registers, enable
  clocks/power, request GPIOs or interrupts, train a link, configure DART/MSI,
  or enumerate PCI.  A device-tree node is intentionally absent, so even this
  driver cannot bind on J81.

The patch dry-runs cleanly against the pinned Hoolock source revision
`6831bc7`, and `git diff --check` passes.

**Cross-build verified, 2026-09-14.** The `darwin.linux-builder-vz` VM was
restarted (from inside this repo, per `docs/build-infrastructure.md`) and
confirmed healthy (`nix-daemon --stdio` gives the expected benign EOF, `free
-h` shows the documented ~8 GB). `nix build
.#packages.x86_64-linux.hoolock-pcie-check-kernel --no-link -L` completed
with exit 0: the config question for `PCIE_APPLE_T7000` is answered `Y`,
`drivers/pci/controller/pcie-apple-t7000.c` compiles cleanly (`CC
drivers/pci/controller/pcie-apple-t7000.o`), and the kernel/modules/dev
outputs all build and copy back successfully. No errors; the only warnings
are the builder VM's expected lack of internet access (`cache.nixos.org`
unresolvable) and one pre-existing, unrelated Nix packaging deprecation
notice. This closes the one item this pass explicitly left pending.

The real J81 `apcie` ADT data was also normalized for the implementation that
follows.  Its twelve absolute MMIO windows are:

```
0x610000000 (16 MiB config aperture)
0x601004000  0x601001000  0x602004000  0x602001000
0x603004000  0x603001000  0x604004000  0x604001000
0x600000000 (8 KiB shared window)
0x601005000  0x603005000
```

Its PCI `ranges` property is a 64-bit prefetchable aperture from PCI
`0x620000000` to CPU `0x620000000`, size `0x1a0000000`, plus a
non-prefetchable aperture from PCI `0xc0000000` to CPU `0x7c0000000`, size
`0x40000000`.  These are apertures for endpoint BARs; they do not assign roles
to the twelve controller windows.  The next PCIe phase is to map those window
roles and add an equally disabled DT/DART topology before any controller
register access is written.

## D2207 write-path result

Offline disassembly of the exact iPad5,3 iOS 8.1 kernelcache, independently
cross-checked against unstripped iOS 10.0 and 10.3 D2207, Dialog PMU, and I2C
drivers, establishes that the earlier Linux attempt was already Apple's normal
GPIO transaction:

```text
I2C address 0x3c, one transaction: 03 e6 02
```

`AppleD2207PMU` maps GPIO2 to `0x03e6`, reads one byte, changes function bits
to `0x02`, and writes that one byte.  Its PMU configuration declares a
two-byte, big-endian register address and zero bank switches.  The Dialog PMU
transport passes precisely those two address bytes followed by the data byte
to the Apple I2C controller.  There is no GPIO/LDO checksum, alternate write
opcode, bank select, commit operation, or unlock sequence omitted by the
Linux command.

The driver does contain one unrelated GPU test-mode sequence (`0x7000 <-
0x1d`, GPU test work, then `0x7000 <- 0x00`).  GPIO and LDO code never calls
it.  This demonstrates that Apple emits an unlock where one is required; using
that GPU-only sequence for GPIO, touch power, Bluetooth, or charging would be
unsupported and unsafe.

Therefore the earlier ACK followed by unchanged readback is **not** a framing
mistake that can be solved by trying more byte patterns.  It must be a runtime
ownership/state/lock condition outside the normal D2207 GPIO/LDO path, or a
hardware/model-state difference that the static images cannot distinguish.
No further live PMIC write is justified at this stage.

The only evidence-producing next experiment is passive: capture SDA/SCL with
a logic analyser while iPadOS turns Bluetooth on or off, then compare the
observed bus traffic with `03 e6 02` and any immediately preceding
transactions.  It introduces no injected PMIC traffic and can establish
whether a separate controller changes the state in the real device.

## Acceptance criteria for this pass

- D2207: either identify an evidence-backed write transaction, or document
  precisely why the available artifacts cannot distinguish it.  No assertion
  of writable PMIC support is allowed without readback evidence.
- PCIe: compile-only work must leave the default J81 payload behavior
  unchanged, identify every controller register window used, and preserve the
  known BCM4350 endpoint as disabled until link/power sequencing is reviewed.
- Charging: the next on-device step remains read-only driver registration and
  sysfs/raw-register comparison.  It does not alter the 100 mA setting.
