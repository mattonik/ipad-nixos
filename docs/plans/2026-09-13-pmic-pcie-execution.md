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

## Acceptance criteria for this pass

- D2207: either identify an evidence-backed write transaction, or document
  precisely why the available artifacts cannot distinguish it.  No assertion
  of writable PMIC support is allowed without readback evidence.
- PCIe: compile-only work must leave the default J81 payload behavior
  unchanged, identify every controller register window used, and preserve the
  known BCM4350 endpoint as disabled until link/power sequencing is reviewed.
- Charging: the next on-device step remains read-only driver registration and
  sysfs/raw-register comparison.  It does not alter the 100 mA setting.
