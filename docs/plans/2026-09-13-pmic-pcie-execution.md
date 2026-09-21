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
  or enumerate PCI.  The matching PCIe/DART DT nodes preserve the real J81
  resources but are disabled, so the driver cannot bind on J81.

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

## Read-only charging observer, 2026-09-15

`boot/ipad_console.py` now has **Charging: read-only D2207 snapshot**.  It
reads the charging driver's two sysfs values and PMIC registers `0x04c0` and
`0x04cf`, applies the same conversions as the driver, then prints `MATCH` or
`DIFF`.  Its PMIC commands are only two-byte register-address selection plus
`r1`; they send no data byte and cannot modify PMIC state.  This makes the
first CHG-1 device check reproducible without exposing a charging-control
write path.

`boot/test_ipad_console.py` asserts the exact four commands and both expected
comparisons offline.  It passed with `python3 boot/test_ipad_console.py` and
`python3 -m py_compile boot/ipad_console.py boot/test_ipad_console.py`.

### CHG-1 hardware result, 2026-09-21

The current control payload booted normally and its USB network shell was
used for the first live snapshot.  The driver reported an input-current limit
of `100000` uA and a constant-charge-current maximum of `3000000` uA.  Raw
D2207 reads were `0x04c0 = 0x02` and `0x04cf = 0x3c`; both decoded to the same
values and the observer printed `MATCH` twice.  The BQ27545 simultaneously
reported `Discharging`, 72%, 3.985 V and `-645000` uA.  This proves the
read-only child is registered and decodes those two PMIC controls correctly.
It does not prove VBUS detection, input-online state, charge enable or a
working charging policy.  The next charging evidence remains a USB-meter
cable A/B table and read-only status-block observations; no PMIC write follows
from this result.

After a normal USB replug in the same session, USB networking and telnet
returned immediately but the gauge remained `Discharging` at `-651000` uA
(71%).  The two reported limits were unchanged.  Re-enumerating the data cable
therefore does not by itself establish a charging state.

### Software-only CHG-2 investigation, 2026-09-21: no USB meter available

Martin does not own a USB power meter, and confirmed the same cable and
connector charges a stock iPadOS install normally -- ruling out the cable and
connector as the cause. Two live, read-only checks were run over the existing
USB network shell instead, both fully reversible and requiring no new
hardware:

1. **USB gadget enumeration state.** `/sys/class/udc/20c100000.usbdev/state`
   reads `configured`; `current_speed` and `maximum_speed` both read
   `high-speed`. This rules out the otherwise-plausible theory that the
   observed 100 mA is simply the USB 2.0 spec's default for an unconfigured
   device -- the gadget is fully enumerated and configured right now. `dmesg`
   additionally shows several full-speed-then-high-speed renegotiation
   cycles across the uptime (cable replugs/resets), none of which changed the
   reported limits, consistent with the same-day replug test above.
2. **Charger-detection plumbing.** Neither `/sys/class/extcon` nor
   `/sys/class/typec` exist on this kernel. `dmesg` has zero lines matching
   `charg`, `extcon`, `d2207`, or `role-switch` anywhere in the boot log
   (confirmed the ring buffer had not wrapped -- the earliest boot-time
   `dwc2`/gadget lines from timestamp 0 are still present). The charger's
   sysfs node exposes only `input_current_limit` and
   `constant_charge_current_max` -- no `online`, `status`, or `present`
   property exists at all. `waiting_for_supplier` reads `0` (not deferred on
   a missing supplier). The charger's own devicetree node
   (`/soc/i2c@20a110000/pmic@3c/charger`) has exactly two properties,
   `compatible` and `name` -- no register offsets, no interrupt, nothing
   else wired in; the driver hardcodes the two PMIC register addresses
   internally.

**Conclusion: this is not a negotiation-failure bug to debug. Nothing in the
current Linux stack has ever attempted to raise the input current limit at
all.** The driver is a minimal, intentionally read-only reporting shim -- it
reads two fixed PMIC registers and exposes them, with no charger-type
detection, no USB-event-driven current negotiation, and no write path of any
kind. The `100000`/`0x02` value is almost certainly the D2207's power-on
default, unchanged since boot, not a live (mis-)detection result. This
reframes CHG-2/CHG-3 from "why does detection give the wrong answer" to "what
write, to which register, does Apple's own driver perform once it decides to
raise the limit" -- the same shape of question KLCT was for touch, and the
next step is the same offline-driver-archaeology technique that answered it.

### The real write path, 2026-09-21: found and fully decoded

Re-extracted the same iPad5,3 12B410 kernelcache (SHA-256
`19c277d60e0a1185b1e4a1b72cda4f1f550c0b0bf670791542234a6dbbcc28bf`, matching
the copy already used for KLCT and the PCIe window-role work) and disassembled
`AppleD2207PMU.kext` directly (`0xffffff8002b44000`, size `0x11000`, found via
its own `CFBundleIdentifier</key><string>...</string>` declaration in
`__PRELINK_INFO` -- not a dependency reference, which is where an earlier,
looser substring search went wrong this same session). The class
`AppleD2207PMUPowerSource` (found via its own class-name and log strings,
e.g. `AppleD2207PMUPowerSource::handleInterrupt(%#x)`, `usb-input-limit-calibration`)
contains the real write logic, string-anchored and disassembled directly with
`llvm-objdump` (the Xcode.app copy is gated behind an unaccepted license on
this machine -- worked around by invoking
`/Library/Developer/CommandLineTools/usr/bin/llvm-objdump` directly, a
separate, unaffected install).

**`AppleD2207PMUPowerSource`'s current-limit setter, `0xffffff8002b4c574`,
does exactly what CHG-1/CHG-2 needed to know:**

1. Reads register `0x04c0` (the same register the read-only observer already
   validated) through the identical two-byte-address-plus-length I2C vtable
   call already established for GPIO2 (`mov w1, #<addr>`, length `1`, `blr`
   through the transport object's vtable -- read at slot `+0x5a8`, write at
   slot `+0x5b0`).
2. Passes a caller-supplied target current through a tiered clamp/derate
   function (`0xffffff8002b4c610`) that matches Apple's classic USB charger-ID
   tiers almost exactly: targets above 2399/2099/999/499/249/99 mA clamp down
   to 2325/2025/950/475/250/100 mA respectively (a consistent few-percent
   safety margin under each nominal tier) -- logged via the already-found
   strings (`p1000 = %d, p500 = %d`, `p2100 = %d, p2400 = %d`, `target = %d,
   adjusted = %d`).
3. **Writes the resulting single byte back to register `0x04c0`.** A
   neighboring helper in the same kext, found at the time via the byte-decode
   idiom `and w8, w8, #0x3f; mov w9, #0x32; mul w0, w8, w9`, was initially
   (incorrectly) assumed to be `0x04c0`'s own decode formula -- **corrected
   after the live test below: that helper actually reads register `0x04cf`
   (`constant_charge_current_max`, a separate register), not `0x04c0`.**
   `0x04c0`'s real formula is the one `boot/ipad_console.py`'s observer
   already used (`code >= 0xfe ? 3262 : 75 + (100*code+7)//8`, in mA) --
   now independently confirmed live, see below.
4. A second helper in the same call path (`0xffffff8002b4c9ac`) performs an
   independent read-modify-write of register `0x0010`, toggling bit 2 based
   on whether the target current is zero or nonzero -- read the same way,
   written the same way, immediately adjacent in the same function. This is
   very plausibly a separate charge-enable bit, not yet confirmed by name.

This satisfies this pass's own acceptance criterion in full: an
evidence-backed write transaction, not an assumption -- Apple's own compiled
driver reading and writing the *exact* register CHG-1 already validated
against real hardware, using the same transport ABI already proven correct
for GPIO2, with a byte-decode formula that independently reproduces CHG-1's
observed value.

**What remains open, and why it's a narrower question than before:** the
setter at `0xffffff8002b4c574` is invoked through a C++ vtable slot (found as
a raw pointer at `0xffffff8002b50600`), not a direct call anywhere within this
kext -- so nothing in `AppleD2207PMU.kext` itself calls it, and the code that
decides *when* to call it with a higher target (i.e. the actual charger-type
detection: reading a D+/D- ID resistor, a BC1.2 result, or similar) lives
elsewhere, not traced this pass. The question has narrowed from "does a write
path exist at all" (now answered: yes, fully decoded) to "what upstream code
calls this vtable slot, and how does it decide the target current" -- a
smaller, more tractable follow-up, likely requiring the same full-kernelcache
Ghidra cross-reference technique already used for KLCT's dispatch chain
rather than single-kext `objdump`.

This evidence is substantially stronger than what existed for the earlier
GPIO2 attempt: GPIO2's "correct write, no effect" conclusion relied on
matching a single write's wire format against Apple's driver; here, Apple's
own driver performs a full, symmetric read-then-write of the *same* register
this project already validated by live readback, with an independently
reproducible encoding formula.

### Live write test, 2026-09-21: the write takes effect -- unlike GPIO2

Martin authorized a single, small, reversible, monitored write test of
`0x04c0` specifically (not the `0x0010` charge-enable bit found alongside
it -- that stays untested). Procedure and results, run over the existing USB
network telnet shell:

1. **Baseline.** `0x04c0` raw read: `0x02`. Sysfs `input_current_limit`:
   `100000`. Gauge: `Discharging`, `-689000` uA, 49%, 33.1 C. `dmesg` clean.
2. **Write.** `i2ctransfer -f -y 0 w3@0x3c 0x04 0xc0 0x0a` (the exact
   two-address-byte-plus-data-byte transaction shape already established for
   GPIO2, target code `0x0a`).
3. **Immediate readback: `0x0a`.** The write took and persisted --
   **unlike GPIO2's ACKed-but-unchanged result.** No `dmesg` errors.
4. **Effect check, before restoring.** Sysfs `input_current_limit` now reads
   `200000` -- decoding `0x0a` through `boot/ipad_console.py`'s existing
   formula (`75 + (100*10+7)//8 = 200`) confirms *that* formula is correct
   for `0x04c0`, and retroactively confirms the disassembly's byte-decode
   attribution above was wrong (see the correction inline). More
   significantly: the gauge's discharge current **dropped from `-689000` uA
   to `-567000` uA** in the same window -- a real ~120 mA change in measured
   battery current, not just a changed register. This is evidence the write
   affects genuine input current draw, not only a cosmetic sysfs number,
   even without touching the separate `0x0010` charge-enable bit.
5. **Restore.** `i2ctransfer -f -y 0 w3@0x3c 0x04 0xc0 0x02`. Readback:
   `0x02`. Sysfs: back to `100000`. `dmesg` clean throughout.

**This is the first live PMIC write this project has found to actually take
effect on real J81 hardware** (GPIO2 remains the only prior attempt, and it
did not). It does not by itself prove full "charging" -- gauge `STATUS`
stayed `Discharging` throughout, `0x0010`'s charge-enable bit was
deliberately not touched this pass, and a single ~120 mA current-draw change
is not the same as a verified charge curve. What it does establish: `0x04c0`
is a real, live, AP-writable register with a measurable effect on the
device's power behavior, using exactly the transaction shape Apple's own
compiled driver performs.

### Live write test, 2026-09-21 (continued): `0x0010` bit 2 -- writable, but not a "charge enable" bit

Martin authorized the same test on `0x0010` bit 2, isolated from `0x04c0`
(left at its rest value `0x02` throughout, confirmed unchanged before and
after) so any effect could be attributed to this one register alone.
Read-modify-write discipline mirrored exactly what
`AppleD2207PMUPowerSource`'s own helper does (`0xffffff8002b4c9ac`): read
the current byte, OR in bit 2 to enable, restore the *original* byte
afterward rather than assuming a fixed rest value.

1. **Baseline.** `0x0010` raw read: `0x00` (bit 2 clear). `0x04c0` confirmed
   still `0x02`. Gauge: `Discharging`, `-709000` uA, 39%, 34.8 C.
2. **Write.** `i2ctransfer -f -y 0 w3@0x3c 0x00 0x10 0x04` (set bit 2, same
   transaction shape). Readback: **`0x04` -- took and persisted**, same as
   `0x04c0`'s test.
3. **Effect check.** Gauge `STATUS` stayed `Discharging` throughout (no
   transition toward `Charging` or `Not charging`). Discharge current went
   the **wrong direction**: `-709000` -> `-809000` uA, and held there
   (`-808000` uA five seconds later) -- roughly 100 mA of *additional* draw,
   not reduced discharge. `0x04c0` reread and confirmed still `0x02`
   (isolation held; the earlier test's effect can't be leaking in here).
4. **Restore.** `i2ctransfer -f -y 0 w3@0x3c 0x00 0x10 0x00`. Readback:
   `0x00`. `dmesg` clean throughout. Current was still `-809000` uA
   immediately after restoring (gauge lag, not a failed restore -- the raw
   register readback already confirmed `0x00`); rechecked 8 seconds later
   and it had settled to `-701000` uA, matching the original baseline almost
   exactly. This settle-back is good evidence the current bump really was
   caused by the register write (temporally correlated both ways), not
   coincidental background load.

**Conclusion: this bit is real and writable (unlike GPIO2), but the
"charge-enable" hypothesis from the disassembly is not supported by this
result.** Setting it *increased* battery drain rather than reducing or
reversing it, with no `STATUS` change -- consistent with it gating some
circuit that itself draws quiescent/parasitic current (a comparator, a
boost stage, an LED, a detection block) rather than connecting USB input
current through to the battery. It may still be part of the real charging
path (e.g. a precondition that only produces net charging current once
`0x04c0` is *also* raised, since this test deliberately kept `0x04c0` at
its 100 mA rest value throughout, or may require other, still-unidentified
register state alongside it) or may control something unrelated to
charging entirely. **Do not assume this is the charge-enable bit going
forward** -- treat it as "real, writable, causes ~100 mA of extra draw
when set," nothing more confirmed than that. The disassembly's `csel`-based
set/clear logic and its co-location with the current-limit setter remain
the only reasons to suspect it's charging-related at all.

### Live write test, 2026-09-21 (continued): both registers together -- combination is worse than `0x04c0` alone, not better

Martin authorized the combined test. Baseline confirmed both registers at
rest (`0x04c0 = 0x02`, `0x0010 = 0x00`) before touching anything; gauge
`Discharging`, `-705000` uA, 38%, 34.4 C.

Wrote both, in the order Apple's own driver calls them (the enable-bit
helper before the current-limit setter, per the disassembly): `0x0010 <-
0x04` (readback `0x04`), then `0x04c0 <- 0x0a` (readback `0x0a`). Both took
and persisted. `dmesg` clean.

**Effect: no better than `0x0010` alone, and worse than `0x04c0` alone.**
Sysfs `input_current_limit` correctly decoded `0x0a` to `200000` uA (same
round-trip through the real driver as the isolated test). But gauge
`STATUS` stayed `Discharging` throughout, and current sat at `-809000` /
`-808000` uA -- **matching the `0x0010`-alone result almost exactly, not
the improved `-567000` uA seen with `0x04c0` raised alone.** The bit 2
quiescent draw looks like it dominates regardless of the current-limit
setting, rather than the two effects combining toward net charging.

Restored in reverse: `0x04c0 <- 0x02` (readback `0x02`), `0x0010 <- 0x00`
(readback `0x00`). Sysfs back to `100000`. `dmesg` clean throughout. Current
settled to `-701000` uA eight seconds later, matching baseline.

**Conclusion: the combination hypothesis is not supported either.** Three
clean, isolated, fully-reversible live tests now agree: `0x04c0` alone
measurably *helps* (reduces discharge by ~120 mA); `0x0010` bit 2 alone
measurably *hurts* (~100 mA more draw, no `STATUS` change); together, bit
2's penalty roughly cancels `0x04c0`'s benefit, landing close to the
`0x0010`-alone result. Nothing tested this pass produced an actual
`Charging` transition. Whatever *does* trigger real charging -- if it's
software-controlled at all, rather than something the D2207's own
autonomous charger-detection hardware gates independently of both these
registers -- remains unidentified. The next-best lead is tracing the
current-limit setter's real caller (the still-untraced vtable dispatch
from the fifth/sixth touch-style passes), since that's the only place
likely to reveal what else Apple's driver checks or sets before charging
actually starts.

### Caller trace, 2026-09-21: genuinely exhausted this pass -- static analysis can't resolve it

Set up the same full-`__PRELINK_TEXT` Ghidra project used for KLCT (import as
raw binary at `0xffffff8002593000`, full headless auto-analysis, ~10-11
minutes), specifically to use Ghidra's own reference engine --
`ReferenceManager.getReferencesTo()` -- rather than the plain-text `grep`
that already failed to find a caller (virtual calls are indirect; the target
address never appears as a literal at the call site, only inside the vtable
data itself).

Ghidra's own constant-propagation-based reference resolution found exactly
**one** reference to the setter (`0xffffff8002b4c574`): the vtable data slot
at `0xffffff8002b50600` itself. **Zero references to that vtable slot from
anywhere in the 14 MB region.** This means the object that ends up calling
through this vtable gets its vtable pointer from something Ghidra's own
propagation can't resolve to a literal address either -- most likely the
object is constructed dynamically at runtime (e.g. obtained via IOKit's
provider-matching/property-lookup machinery, the same pattern
`AppleARMFunction`/`callPlatformFunction` used for KLCT) rather than through
a compile-time-constant `adr`/`adrp` sequence. **Genuinely exhausted with the
techniques available this pass** -- the same honest conclusion the touch
investigation reached at its fourth pass, for the same underlying reason
(indirect dispatch through a dynamically-obtained object, not a static
constant). Finding the real caller would need either a different technique
entirely (e.g. tracing `IOService::start()`/personality-matching machinery
directly) or is simply not answerable from this kernelcache's disassembly
alone.

### Live write test, 2026-09-21: raising `0x04c0` further -- real charging achieved

Martin proposed raising the input current limit clearly above the measured
discharge rate, to see whether `STATUS` would actually transition. Baseline
confirmed clean first: `0x04c0 = 0x02`, `0x0010 = 0x00` (still at rest from
the prior test), gauge `Discharging` at `-705000` uA, 29%, 33.7 C.

Wrote `0x04c0 <- 0x4a` (decimal 74; the formula gives exactly `1000` mA for
this code, one of Apple's own real tier values, not an arbitrary
number) -- deliberately **`0x0010` was left untouched** this time, isolating
the test to the one register that had already shown a real, positive
effect. Readback confirmed `0x4a`; sysfs `input_current_limit` correctly
decoded it to `1000000` uA (matching the formula exactly, independently
reconfirming it for a second data point). `dmesg` clean.

**`STATUS` transitioned to `Charging` immediately -- the first time this
project has ever observed it.** `CURRENT_NOW` went positive:
`+44000` uA, then `+53000` uA eight seconds later, then `+66000` /
`+76000` uA over the following ~20 seconds -- a real, stable, gently
*rising* trickle charge, not a single-sample artifact. Voltage rose in step
(`3756000` -> `3770000` uA over the same window). Temperature held flat at
`336`-`337` (33.6-33.7 C) throughout -- no thermal concern. This single
register write, alone, was sufficient: **no `0x0010` bit, no other register,
no Apple driver code path involved at all -- just a large enough
`input_current_limit` for the input current to exceed the system's own
draw.**

This substantially reframes the whole charging investigation. The earlier
100 mA default was never a "detection failure" or a "missing enable
signal" -- it was simply **too low a ceiling to ever produce positive net
current once system load is accounted for**. `0x0010` bit 2's real role
remains unexplained (its own isolated test still showed a real, negative
effect -- extra draw, no benefit), but it is now clearly **not required**
for charging to occur.

**Martin's explicit standing instruction for this state:** keep `0x04c0` at
`0x4a` (charging) until either the next test step supersedes it, temperature
becomes a concern, or any other safety issue appears -- and **automatically
restore to the `0x02` default the moment capacity reaches 80%**, as a
conservative cutoff. This is being monitored on a recurring check-in basis;
see the running log below for each observation and the eventual stop
condition and reason.

#### Charging monitor log

Safety thresholds in effect: stop (restore `0x04c0 -> 0x02`) immediately if
capacity reaches 80%, `TEMP` reaches 42.0 C (`420`), the device becomes
unreachable, `dmesg` shows anything concerning, or Martin gives a new
instruction that supersedes this. Checked on a recurring basis (not
continuous polling); each entry below is one observation.

| Time (approx) | STATUS | CURRENT_NOW | TEMP | CAPACITY | Note |
| --- | --- | --- | --- | --- | --- |
| write+0s | Charging | +44000 uA | 33.7 C | 29% | Write took effect immediately |
| write+8s | Charging | +53000 uA | 33.7 C | 29% | Confirms stability, not a fluke |
| write+~30s | Charging | +66000 uA | 33.7 C | 29% | Rising |
| write+~60s | Charging | +76000 uA | 33.6 C | 29% | Rising further; `0x04c0` reconfirmed `0x4a` |

(Continued below as the recurring check-ins accumulate; this table is the
running record Martin asked for.)

## Acceptance criteria for this pass

- D2207: either identify an evidence-backed write transaction, or document
  precisely why the available artifacts cannot distinguish it.  No assertion
  of writable PMIC support is allowed without readback evidence.
- PCIe: compile-only work must leave the default J81 payload behavior
  unchanged, identify every controller register window used, and preserve the
  known BCM4350 endpoint as disabled until link/power sequencing is reviewed.
- Charging: the next on-device step remains read-only driver registration and
  sysfs/raw-register comparison.  It does not alter the 100 mA setting.
