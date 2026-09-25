# T7000 PCIe: hardware test findings, 2026-09-21 to 2026-09-23

Consolidated reference for every real hardware result from the J81 PCIe
host-controller investigation. The dated narrative (why each test was
designed the way it was, and the reasoning between rounds) lives in
[`docs/plans/2026-09-13-j81-wifi-pcie.md`](../docs/plans/2026-09-13-j81-wifi-pcie.md);
this file exists so the raw evidence -- what was actually run, and exactly
what came back -- is in one place rather than spread across six dated
sections.

## The conclusion, stated first

Nine real hardware boots, each changing exactly one variable versus the
previous clean one:

| # | Patch | What it did | Result |
| --- | --- | --- | --- |
| 1 | `0018` (write-capable) | Full enable sequence: shared-window writes (`REFCLK_EN`, `PERST_INTERNAL`, `0x10c`, `LINK_ENABLE`, LTSSM start) + `reset-gpios` DT node + DART/`iommu-map` + full `pci_host_common_init()` | **Hung.** Black screen, backlight on, no console, no USB. Two attempts, identical. |
| 2 | `0018` ("read-only", later found not actually passive) | Same as above minus the shared-window writes and `reset-gpios`, but still called `pci_host_common_init()` (full ECAM + bus scan) and left DART/`iommu-map` enabled | **Hung**, identically. |
| 3 | `0019` (PMGR-only) | Only the DT `status = "okay"` flip + automatic `power-domains = <&ps_pcie>` genpd power-up. No MMIO, no PCI core, no DART. | **Clean.** |
| 4 | `0020` (shared-window read) | `0019` + one bounded `readl()` of the shared register window (port 1 LTSSM offset only) | **Clean.** `ltssm=0x00000000`. |
| 5 | `0021` (ECAM read) | `0019` + one bounded `readl()` of ECAM offset 0 (bus0/dev0/fn0), via raw `devm_ioremap_resource()`, no `pci_ecam_create()` | **Clean.** `vendor/device=0xffffffff`. |
| 6 | `0022` (multi-offset ECAM read) | Same as `0021`, three reads: bus 0, bus 1, bus 4 | **Clean.** All three `0xffffffff`. |
| 7 | `0023` (isolated `pci_host_common_init()`) | The *exact* call both `0018` attempts made -- `devm_pci_alloc_host_bridge()` + `pci_host_common_init()` with a bare ECAM ops struct -- and nothing else. No shared-window writes, no PERST, no DART. | **Clean.** Returns `0`; full generic bus scan completes. |
| 8 | `0024` (remaining shared offsets) | `0019` + four bounded `readl()`s of port 1's `REFCLK_EN`/`PERST_INTERNAL`/`0x10c`/`LINK_ENABLE` -- the offsets read-only `0018` read but `0020` never isolated | **Clean.** Real, non-trivial values (see below). |
| 9 | `0025` (DART enable, no `iommu-map`) | `0019`'s exact inert PCIe probe + `dart_apcie1` flipped to `"okay"` (real Linux `apple-dart` probe: register map, reset, IRQ) -- no `iommu-map` consumer | **Hung.** Black screen after the m1n1 logo/sequence; no USB re-enumeration; no networking. First hang since `0018`. |

Every individual piece `pci_host_common_init()` touches, and every
register either hanging `0018` driver ever read, has now been proven
safe in isolation: the DT status flip, the power-domain attachment, every
shared-window register the enable sequence touches, ECAM mapping and reads
at multiple points, and the complete generic PCI bus scan itself
(including its BAR-sizing config-space writes and bus-number programming).

**DART is now the sole remaining common difference.** All six clean
follow-up payloads (`0019` through `0024`) deliberately kept
`dart_apcie1` disabled and removed `iommu-map`; both hanging `0018`
attempts enabled them. DART probe/reset and PCIe-to-DART IOMMU attachment
are the one thing left untested. The pinned Linux DART driver programs MMIO
at probe time, so that is meaningful even before an endpoint exists. Apple
requests `function-dart_force_active` early in port enable (after gate
requests, before controller writes), but Linux does not implement Apple's
separate on-demand-availability model; a Linux DART probe characterizes its
own reset path rather than replaying Apple's platform function.

**Two secondary corrections, also load-bearing for anyone continuing this
work**:

1. `pci_host_common_init()` never calls `pci_host_common_parse_ports()`.
   That helper is opt-in and must be called explicitly by a controller
   driver. PERST# was **never actually deasserted** by either hanging
   `0018` attempt, despite the DT carrying a `reset-gpios` child node --
   verified directly against the real pinned `pci-host-common.c` source
   (`github:HoolockLinux/linux` at `6831bc701a6ce059e71e5aaa9488c9195bea6927`).
2. The register-window math is correct, not an off-by-one: shared window
   (ADT `reg` index 9) is `0x600000000`, size `0x2000` (8 KiB); ECAM
   (index 0) is `0x610000000`, size `0x1000000` (16 MiB). Both confirmed
   live on hardware (see raw output below), matching the values decoded
   from the real J81 ADT.

## Raw hardware output, in order

### Control payload (unmodified `m1n1-hoolock-control`), 2026-09-21

Booted normally through the same PongoOS/`bootm`/m1n1 pipeline used for
every test below -- postmarketOS visible, USB networking up,
`172.16.42.1` pingable at 0% loss. Run between the two hanging `0018`
attempts and the first clean test, specifically to rule out host/cable/DFU
flakiness as an explanation for the hangs. It did.

### `0019` PMGR-only test

```
[dmesg]
pcie-apple-t7000 610000000.pcie: t7000-pcie pmgr-only-test: probe reached (no MMIO, no PCI core, no DART)
```

### `0020` bounded shared-window read test

```
[    0.125897] pcie-apple-t7000 610000000.pcie: t7000-pcie diag: window 9 at [mem 0x600000000-0x600001fff]
```
(from the earlier, superseded `0018` "read-only" attempt's window-mapping
log line, included here because it's the first real hardware confirmation
of the shared window's address -- the hang that attempt hit was unrelated
to this specific line, per the analysis above)

```
[dmesg, 0020 itself]
pcie-apple-t7000 610000000.pcie: t7000-pcie shared-read-test: probe entry
pcie-apple-t7000 610000000.pcie: t7000-pcie shared-read-test: window 9 at [mem 0x600000000-0x600001fff]
pcie-apple-t7000 610000000.pcie: t7000-pcie shared-read-test: mapped, about to read LTSSM register
pcie-apple-t7000 610000000.pcie: t7000-pcie shared-read-test: port 1 ltssm=0x00000000
```

### `0021` bounded ECAM read test

```
[    0.125732] pcie-apple-t7000 610000000.pcie: t7000-pcie ecam-read-test: probe entry
[    0.125828] pcie-apple-t7000 610000000.pcie: t7000-pcie ecam-read-test: window 0 at [mem 0x610000000-0x610ffffff]
[    0.125928] pcie-apple-t7000 610000000.pcie: t7000-pcie ecam-read-test: mapped, about to read config offset 0
[    0.126013] pcie-apple-t7000 610000000.pcie: t7000-pcie ecam-read-test: bus0/dev0/fn0 vendor/device=0xffffffff
```

### `0022` multi-offset ECAM read test

```
[    0.126653] pcie-apple-t7000 610000000.pcie: t7000-pcie ecam-multi-test: probe entry
[    0.126751] pcie-apple-t7000 610000000.pcie: t7000-pcie ecam-multi-test: window 0 at [mem 0x610000000-0x610ffffff]
[    0.126851] pcie-apple-t7000 610000000.pcie: t7000-pcie ecam-multi-test: mapped, starting bounded reads
[    0.126893] pcie-apple-t7000 610000000.pcie: t7000-pcie ecam-multi-test: about to read bus 0 dev0 fn0 (offset 0x0)
[    0.126927] pcie-apple-t7000 610000000.pcie: t7000-pcie ecam-multi-test: bus 0 dev0 fn0 vendor/device=0xffffffff
[    0.126956] pcie-apple-t7000 610000000.pcie: t7000-pcie ecam-multi-test: about to read bus 1 dev0 fn0 (offset 0x100000)
[    0.126987] pcie-apple-t7000 610000000.pcie: t7000-pcie ecam-multi-test: bus 1 dev0 fn0 vendor/device=0xffffffff
[    0.127018] pcie-apple-t7000 610000000.pcie: t7000-pcie ecam-multi-test: about to read bus 4 dev0 fn0 (offset 0x400000)
[    0.127048] pcie-apple-t7000 610000000.pcie: t7000-pcie ecam-multi-test: bus 4 dev0 fn0 vendor/device=0xffffffff
[    0.127076] pcie-apple-t7000 610000000.pcie: t7000-pcie ecam-multi-test: all reads completed
```

### `0023` isolated `pci_host_common_init()` test

```
[    0.128709] pcie-apple-t7000 610000000.pcie: t7000-pcie full-probe-test: probe entry, about to call pci_host_common_init()
[    0.128818] pcie-apple-t7000 610000000.pcie: host bridge /soc/pcie@610000000 ranges:
[    0.128919] pcie-apple-t7000 610000000.pcie:      MEM 0x0620000000..0x07bfffffff -> 0x0620000000
[    0.129006] pcie-apple-t7000 610000000.pcie:      MEM 0x07c0000000..0x07ffffffff -> 0x00c0000000
[    0.129116] pcie-apple-t7000 610000000.pcie: ECAM at [mem 0x610000000-0x610ffffff] for [bus 00-04]
[    0.129269] pcie-apple-t7000 610000000.pcie: PCI host bridge to bus 0000:00
[    0.130127] pcie-apple-t7000 610000000.pcie: t7000-pcie full-probe-test: pci_host_common_init() returned 0
```

### `0024` remaining shared-window offsets test

```
[    0.128357] pcie-apple-t7000 610000000.pcie: t7000-pcie shared-remaining-test: probe entry
[    0.128463] pcie-apple-t7000 610000000.pcie: t7000-pcie shared-remaining-test: window 9 at [mem 0x600000000-0x600001fff]
[    0.128564] pcie-apple-t7000 610000000.pcie: t7000-pcie shared-remaining-test: mapped, starting bounded reads
[    0.128650] pcie-apple-t7000 610000000.pcie: t7000-pcie shared-remaining-test: about to read port1 refclk_en (offset 0x180)
[    0.128741] pcie-apple-t7000 610000000.pcie: t7000-pcie shared-remaining-test: port1 refclk_en = 0x11010100
[    0.128825] pcie-apple-t7000 610000000.pcie: t7000-pcie shared-remaining-test: about to read port1 perst_internal (offset 0x188)
[    0.128915] pcie-apple-t7000 610000000.pcie: t7000-pcie shared-remaining-test: port1 perst_internal = 0x00000100
[    0.129006] pcie-apple-t7000 610000000.pcie: t7000-pcie shared-remaining-test: about to read port1 unknown_10c (offset 0x18c)
[    0.129096] pcie-apple-t7000 610000000.pcie: t7000-pcie shared-remaining-test: port1 unknown_10c = 0x00000001
[    0.129181] pcie-apple-t7000 610000000.pcie: t7000-pcie shared-remaining-test: about to read port1 link_enable (offset 0x198)
[    0.129269] pcie-apple-t7000 610000000.pcie: t7000-pcie shared-remaining-test: port1 link_enable = 0x00000000
[    0.129368] pcie-apple-t7000 610000000.pcie: t7000-pcie shared-remaining-test: all reads completed
```

## Confirmed register/address values (live hardware, not decoded/inferred)

| Item | Value | Source |
| --- | --- | --- |
| Shared window base | `0x600000000` | `0020`/`0018` window-map log |
| Shared window size | `0x2000` (8 KiB) | same |
| Port-1 LTSSM register (`0x820 + 1*0x40 = 0x860`) at rest | `0x00000000` | `0020` |
| ECAM window base | `0x610000000` | `0021`/`0022`/`0023` |
| ECAM window size | `0x1000000` (16 MiB) | same |
| bus0/dev0/fn0 config space (ECAM offset `0x0`) | `0xffffffff` (no device) | `0021`, `0022` |
| bus1/dev0/fn0 config space (ECAM offset `0x100000`) | `0xffffffff` (no device) | `0022` |
| bus4/dev0/fn0 config space (ECAM offset `0x400000`) | `0xffffffff` (no device) | `0022` |
| `pci_host_common_init()` outer MEM range 1 | `0x0620000000..0x07bfffffff -> 0x0620000000` | `0023`, matches DT `ranges` |
| `pci_host_common_init()` outer MEM range 2 | `0x07c0000000..0x07ffffffff -> 0x00c0000000` | `0023`, matches DT `ranges` |
| `pci_host_common_init()` return value | `0` (success) | `0023` |
| Port-1 `REFCLK_EN` (`0x100+0x80=0x180`) at rest | `0x11010100` (bits 8/16/24/28 set) | `0024` |
| Port-1 `PERST_INTERNAL` (`0x108+0x80=0x188`) at rest | `0x00000100` (bit 8 set, not bit 0) | `0024` |
| Port-1 `0x10c` (`0x10c+0x80=0x18c`) at rest | `0x00000001` (bit 0 set) | `0024` |
| Port-1 `LINK_ENABLE` (`0x118+0x80=0x198`) at rest | `0x00000000` | `0024` |

All `0xffffffff` config-space results are the ordinary, correct PCI "no
device present" response -- not faults, not garbage, not hangs. The
shared-window "at rest" values from `0024` are real and non-trivial (not
all-zero, not all-Fs), and each is at least loosely consistent with what
the recovered `_enablePortHardware` sequence does to that register:
`link_enable` reading `0x0` matches the sequence's own first step (clear
bit 0 -- a no-op here); `0x10c` reading bit 0 set matches the sequence
later clearing that same bit; `perst_internal` reading bit 8 (not bit 0,
the bit the sequence actually sets) means bit 8 is a distinct,
still-unidentified status flag; `refclk_en`'s denser bit pattern
(8/16/24/28) is worth decoding further later but wasn't required for this
evidence gate. Consistent throughout: the real enable sequence (which
deasserts PERST# and starts LTSSM) has never actually run on this
hardware in any test so far, so no endpoint has ever been link-trained or
made visible.

## Next step

The passive-read gap is now fully closed -- every register either hanging
`0018` driver read is independently confirmed safe, and the complete
generic PCI bus scan is independently confirmed safe. **DART is the sole
remaining common difference** between the hanging attempts and every
clean test.

This is a research task, not a hardware test: recover Apple's
`function-dart_force_active` semantics and the `PCIE`/`PCIE_AUX`/`PCIE_REF`
power-gate operations offline, from the real iOS kernelcache (the same
evidence source as the rest of this investigation). Then run one
DART-probe-only hardware test: DART enabled, PCIe left inert, no IOMMU
consumer. Only after that result and the missing gate evidence should
controller writes, explicit PERST handling, and link training be
attempted, in Apple's full recovered order: controller setup → DART
active → tunables → PERST release → link start → PCI enumeration.

## `function-dart_force_active` and gate semantics, recovered 2026-09-23

Ghidra analysis of the same pinned iPad5,3 12B410 kernelcache used
throughout this investigation (`AppleEmbeddedPCIE.kext` at
`0xffffff8002be9000`, `AppleS5L8960XDART.kext` at `0xffffff80026c2000`).
Method: `ipsw kernel kexts` located each kext's load address; a reused
Ghidra project (PRELINK_TEXT already imported/analyzed from earlier
sessions) let string and decompiler scripts run directly without a fresh
import.

### The real call order -- this corrects an earlier assumption

`AppleEmbeddedPCIEPort::init()` (`FUN_ffffff8002bed5bc`) resolves and
caches several platform functions per port during setup, including
`function-dart_force_active` (cached at object offset `+0x130`),
`function-perst` (`+0x140`), `function-device_wake` (`+0x148`), and
`function-clkreq` (`+0x128`) -- confirmed by direct string cross-references
(`function-dart_force_active`, `function-nvme_mmu_force_active`,
`_dartForceActiveFunction != nullptr`, `manual-enable`, all in this kext).
It also reads the ADT's `power-gates` property (a single `u32` index) into
`+0xa8`.

**`AppleEmbeddedPCIEPort::enableGated()`** (`FUN_ffffff8002bee6cc`,
confirmed by its own `"enableGated"` log-string reference) is the real
state machine, and its order for the initial enable states is, in this
exact sequence:

1. Enable the power gate (`vtable+0x6b8`, called with the `power-gates`
   index from `+0xa8`).
2. Enable the clock gate (`vtable+0x6d0`, same index).
3. **Call `function-dart_force_active(true, 0, 0)`** through the cached
   function pointer at `+0x130`.
4. If an NVMe-MMU force-active function was also resolved (`+0x138`,
   not applicable to this WiFi port), call it the same way.
5. **Only after that** does it poll for the gate to actually report
   "active" (`+0xa0` object, `vtable+0x618`, `REQUIRE`d to succeed).
6. Conditional link-speed-dependent setup, two more internal setup calls.
7. **Only after all of that** does it perform the first shared-window
   register writes, via a `(this, register, value)` write helper
   (`FUN_ffffff8002bef92c`) -- registers `0x114`, `0x104`, `0x100` in that
   order, followed later by a read-modify-write of register `0x80`.

**This corrects the previous documented assumption** ("Apple invokes
`function-dart_force_active` only after port hardware setup") -- the real
order is the opposite: DART force-active is requested essentially
immediately after the power/clock gate request, *before* the driver even
confirms the gate is active, and well before any register write to the
controller happens at all.

### What `function-dart_force_active` actually does on the DART side

`AppleS5L8960XDART::_forceAvailable(bool available)` (`FUN_ffffff80026c43fc`,
confirmed by its own log string) is straightforward: take an internal
lock, store `available` into the object's `_available` field (offset
`0xf6`), call the virtual `_updateAvailability()` method, release the
lock. If `_manualAvailabilityEnabled` (offset `0xf5`) is false at the time
of the call, it logs a warning (`"_forceAvailable called on DART with
_manualAvailabilityEnabled false"`) but does **not** stop -- it still sets
`_available` and still calls `_updateAvailability()`.

**`_updateAvailability()`** (the function that warning string is emitted
from) is the part that matters: if `_manualAvailabilityEnabled` is false,
it **ignores** the `_available` flag entirely and instead derives
availability automatically by polling up to four registered IOMMU mapper
slots (`vtable+0x600`, once per index 0-3) for whether any is currently
active. Only if `_manualAvailabilityEnabled` is true does it actually use
the flag `_forceAvailable` just set. Either way, if the computed
availability differs from the DART's current state (offset `0xf4`), it
calls one of two virtual handlers -- effectively "become available" or
"become unavailable" -- which are presumably where the real
`_dartPowerup()`/`_dartPowerdown()` work happens.

**Real, still-open point**: this means calling `function-dart_force_active`
only has a practical effect on availability if `_manualAvailabilityEnabled`
was *already* true. This driver's own `init()` reads a `manual-enable` ADT
boolean into a **port**-level field (`AppleEmbeddedPCIEPort`'s own
`+0x178`), but that is a different object from the DART itself
(`AppleS5L8960XDART`) -- where and how the DART's own
`_manualAvailabilityEnabled` (its `+0xf5`) gets set to true was not traced
in this pass. If it's never set, `function-dart_force_active(true)` reduces
to "log a warning, then re-derive availability from zero registered
mappers" -- i.e. a no-op that likely leaves the DART powered down. This is
worth resolving before concluding a DART-only Linux test result means
anything conclusive about Apple's own real activation path.

### Where the `PCIE`/`PCIE_AUX`/`PCIE_REF` gates fit in

The literal ADT property names `power-gates` and `clock-gates` do **not**
appear anywhere in `AppleEmbeddedPCIE.kext`'s own string table -- only one
opaque, shared symbol constant is referenced to read a single `u32` value
(matching the already-documented `power-gates: 0x39` (57) ADT value) into
the port object. Both gate-enable calls in `enableGated()`
(`vtable+0x6b8`/`+0x6d0`) take *only* that one index as their argument;
this leaf driver code never separately references the other two
`clock-gates` entries (`58`/`PCIE_AUX`, `56`/`PCIE_REF`).

The pinned [Linux PMGR implementation](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/drivers/pmdomain/apple/pmgr-pwrstate.c)
resolves the Linux side. It registers one genpd per DT power-state node and
adds a parent only for each node's explicit `power-domains` property. In the
pinned [T7001 PMGR DTS](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/arch/arm64/boot/dts/apple/t7001-pmgr.dtsi),
`ps_pcie`, `ps_pcie_aux`, and `ps_pcie_ref` have no parent links.
Consequently, `power-domains = <&ps_pcie>` powers **only** `ps_pcie`; it
cannot implicitly power either sibling. `0019` proves that one domain safe,
but not that AUX/REF are enabled or unnecessary.

Apple may still handle its ADT `clock-gates` array below the port driver.
The current Linux DT does not model the two sibling PMGR states, however.
Recovering their Apple ownership remains necessary for a production
controller driver, but it does not prevent a narrow probe of the existing
Linux DART reset path.

### Practical takeaway for the next hardware test

The next payload should preserve the PMGR state used by both hanging builds
while changing only DART probe behavior: keep the proven `0019` PCIe node
enabled with its no-MMIO diagnostic driver, enable `dart_apcie1`, and omit
`iommu-map`. That lets the stock Linux DART driver map, reset, and register
its IRQ while the PCIe driver remains inert. It is a better isolation than
enabling DART with PCIe disabled, because the DART node has no power-domain
reference of its own and that alternative would also remove `ps_pcie`.

If this payload is clean, repeat it with only `iommu-map` restored. This
separates the DART driver's reset path from the PCIe-to-IOMMU attachment
performed before PCIe driver probe. Neither payload should add AUX/REF
domains, controller MMIO, PERST handling, or PCI enumeration. The
`_manualAvailabilityEnabled` question remains relevant to reproducing
Apple's full controller sequence, but not to characterizing Linux DART
probe.

## `0025` DART-enable test: hangs, 2026-09-23

Ran the payload the section above specified: `0019`'s proven inert PCIe
probe unchanged, `dart_apcie1` flipped to `"okay"`, no `iommu-map`. Same
DFU/palera1n recipe as every prior round; `05ac:4141` confirmed, `m1n1.bin`
+ `Image.gz` uploaded via `boot/load_m1n1.py` with no replug after the
`bootm` request (per the infrastructure note below).

**Result: hung.** The iPad showed the normal m1n1 logo and boot sequence,
then went to a black screen with only the backlight on -- no framebuffer
console text at all, unlike every one of the six prior clean tests
(`0019`-`0024`), which all produced visible boot text. Polled USB
enumeration and `ping 172.16.42.1` for 30+ seconds after the handoff: the
device never re-enumerated as a USB network gadget and never answered a
single ping. This is the same observable signature as both original `0018`
hangs -- total silence, no crash message, no watchdog recovery seen -- not
a slow boot.

This isolates the fault to `dart_apcie1` alone. `0019`'s own PCIe PMGR-only
node (`status = "okay"` + `power-domains = <&ps_pcie>`) has already been
independently hardware-proven clean six times over; the only new variable
`0025` introduces is enabling the DART node, which lets the stock Linux
`apple-dart` driver's `apple_dart_probe()` actually run: map the DART's
MMIO window, register its IRQ, and -- the most likely point of failure --
reset the unit, which is the first place probe touches a real DART
register rather than just OS bookkeeping (`ioremap`/IRQ registration don't
themselves generate a bus transaction).

**Captured-ADT correction, 2026-09-23:** the saved ADT is textual, not an
opaque binary blob. `dart-apcie1` has **no** `power-gates` or `clock-gates`
property. It does have `manual-availability = 1`. This is decisive enough to
reject the AUX/REF-gate hypothesis as the next test: those gates may still
matter to a future PCIe controller driver, but the captured Apple DART node
does not name them as its own dependencies.

The comparison is useful: the same ADT has six T7001 DART nodes. Display,
scaler, JPEG, ISP, and AVE DARTs carry explicit power/clock-gate values;
the PCIe DART is the only one with `manual-availability = 1` and no such
gate property. The PCIe bridge also has `manual-enable` and resolves
`function-dart_force_active` to this DART. This directly matches the
previously recovered DART object's `_manualAvailabilityEnabled` field and
the port driver's force-active call.

The leading explanation is now an **availability-order mismatch**, not a
missing decoded gate: Apple's port driver asks this manual-availability DART
to become available before controller accesses, whereas the stock Linux
driver immediately maps and resets it during platform probe. The next
offline Ghidra task is tightly scoped: trace `manual-availability` in
`AppleS5L8960XDART` to confirm it initializes `_manualAvailabilityEnabled`,
then trace the virtual "become available" handler called by
`_updateAvailability()`. That handler is the evidence needed to learn what
Apple performs before its first DART register access. No further DART
hardware payload should be built or run until it is recovered.

### Availability setup trace, 2026-09-23

This first part of that Ghidra task is now complete against the exact
iPad5,3 iOS 8.1 (12B410) kernelcache. A focused import of only
`AppleS5L8960XDART.kext` at `0xffffff80026c2000` found one and only one
reference to the string `manual-availability`: initializer
`FUN_ffffff80026c316c`. It reads the ADT property, validates its four-byte
value, and stores whether it is non-zero directly at object offset `0xf5`.
That proves the captured `dart-apcie1` value of one enables
`_manualAvailabilityEnabled`; it is no longer an inference from matching
names.

The same trace also recovers the full local platform-function route. DART's
platform-function dispatcher at `FUN_ffffff80026c429c` accepts the `tcaF`
selector (little-endian `0x46616374`) and a boolean input, then calls
`FUN_ffffff80026c43fc` (`_forceAvailable`). That function locks the object,
stores the boolean at `0xf6`, and dispatches the virtual method at vtable
slot `+0x610` before releasing the lock. This is the call reached by the
PCIe port's already-recovered `function-dart_force_active(true)` request.

The virtual `+0x610` target remains unresolved. A second focused import that
included the adjoining `IODARTFamily` region still did not yield a reliable
static target: the call is genuinely virtual, rather than a hidden direct
branch in the DART kext. The next offline task is therefore to trace the
runtime vtable initialization or the superclass availability implementation,
then inspect the handler's first MMIO or PMGR action. Do not turn this result
into a Linux DT or driver change yet: it identifies the missing transition,
not the register sequence that transition performs.

**Per the plan's own conditional gate, test 2 (`0026`, `iommu-map`
restored) does not run next** -- the instruction was "if that boots,
repeat with iommu-map restored," and it did not boot. `0026` stays built
and cross-build-verified (`result-dart-b`) but untested; running it now
would only add a second, less-isolated variable on top of an already-
failing base, not new evidence.

### Availability transition fully decompiled, 2026-09-24

Picked up exactly where the trace above stopped: the virtual `+0x610`
target. Found `_updateAvailability()`'s own concrete function body directly
-- `DumpStrings` output already on hand from the earlier Ghidra pass
includes the literal pretty-function string
`"virtual bool AppleS5L8960XDART::_updateAvailability()"` at
`0xffffff80026c6663`, and it has exactly one cross-reference, from
`FUN_ffffff80026c49b8`. That is the function: it uses its own name string
as a `REQUIRE`-style assert argument, the same pattern every other
recovered function in this kext uses.

Decompiled it in full. It first asserts the object's lock is held, then
computes the new availability state: if `_manualAvailabilityEnabled`
(`0xf5`) is false, it polls up to four registered IOMMU mapper slots
(vtable `+0x600`) for activity, exactly as summarized before; if true, it
takes the forced flag Apple's `_forceAvailable` wrote at `0xf6` directly,
skipping the mapper poll entirely -- confirmed mechanism, not inference,
and directly applicable here since the captured ADT sets
`manual-availability = 1`. It then compares the new state against a cached
current-availability flag at `0xf4`; if unchanged, it does nothing further.
If changed, it dispatches **one of two further virtual calls**: vtable
`+0x5d8` on a false->true transition ("become available"), vtable `+0x5d0`
on true->false ("become unavailable").

Neither handler has its own name string in this kext (a second string
search came up empty), so the earlier session's assumption that they might
be inherited from `IODARTFamily` was reasonable -- but wrong. Rather than
trace the C++ constructor chain to find the real instance vtable, searched
process memory directly for the already-known `_updateAvailability` pointer
value at its confirmed `+0x610` offset. Exactly one match:
vtable base `0xffffff80026c7140`. Reading `+0x5d8` and `+0x5d0` from that
base resolves both handlers to concrete addresses inside this same kext:
`FUN_ffffff80026c5b38` (become available) and `FUN_ffffff80026c5c48`
(become unavailable). Both decompiled cleanly.

**Become available**, in exact order: asserts not-yet-available and the
lock held; calls **two operations on a cached helper sub-object** (object
offset `0xe8`, obtained once during `init()` via what reads as an
`OSDictionary`-style property lookup) with enable-flag arguments -- `(helper,
1, 0)` then `(helper, 1, 0, 0)`. This is the same two-call shape already
established for the PCIe port's own `enableGated()` (power gate, then clock
gate) -- strong circumstantial evidence this is the DART's **own, separate**
power/clock gate request, not a reuse of the PCIe port's `ps_pcie` gate.
Only *after* that does it mark `_available = true`, call one more virtual
hook on itself (`+0x5e8`, args `(this, 1)` -- plausibly a powerup-adjacent
step, not independently confirmed), and finally **enable its interrupt
event source** (vtable `+0xa8` on a cached `IOInterruptEventSource`-shaped
object) -- and a second event source too, conditionally on a capability
flag. **The DART's own interrupt is not enabled until this transition
completes.**

**Become unavailable** is the exact mirror: disables the interrupt
source(s) first, marks unavailable, then releases the same two gates last
(`(helper, 0, 0)` then `(helper, 0, 0, 0)`).

**This is a materially stronger, more mechanistic explanation than the
AUX/REF-gate hypothesis it replaces.** It's not that Linux is missing a
specific named PMGR domain reference -- it's that Apple's DART has its own
dedicated availability state machine, gated by `manual-availability` (ADT)
plus an explicit `_forceAvailable(true)` call (the PCIe port driver's job,
part of `enableGated()`), and that state machine's own "become available"
step is what actually requests the DART's power/clock gate -- separately
from, and before, anything else touches DART hardware. The stock Linux
`apple-dart` driver has no equivalent concept at all: `apple_dart_probe()`
maps registers and resets the unit unconditionally during platform probe,
with no availability transition, no gate request beyond whatever
`power-domains` the DT declares (nothing at all, for `dart_apcie1`), and no
ordering tie between "becoming usable" and enabling its own interrupt. If
the DART's own gate genuinely must be requested through this exact
transition before the silicon responds to any register access, Linux's
immediate reset in `apple_dart_probe()` would hit ungated hardware -- fully
consistent with, and now mechanistically explaining, the observed hang.

**Not resolved this pass**: the identity of the offset-`0xe8` helper
object's own class, and therefore what its `vtable+0x560`/`+0x568` calls
actually do at the PMGR/register level -- whether they resolve to the same
`ps_pcie` gate the PCIe port already requests, to `ps_pcie_aux`/
`ps_pcie_ref` (the orphaned genpd nodes already found in the pinned PMGR
DTS), or to a distinct gate index Linux's DT doesn't model at all. The
helper's own `OSSymbol*` property-name lookup resolves through live,
pre-linked kernel data this legacy (`no __DATA_CONST`) kernelcache doesn't
expose as static strings -- the same class of wall the TOUCH-3 investigation
hit repeatedly on this same kernelcache generation.

### Helper object identified: `AppleARMPerformanceController`, 2026-09-24

Rather than chase the on-disk `OSSymbol*` chain further (the same dead end
TOUCH-3 hit repeatedly on this kernelcache generation), identified the
helper by **where it lives**, not what it's named. Read the raw bytes at
the cached property-lookup target's own address (`0xffffff80026938c0`,
the value `_forceAvailable`'s helper lookup resolves against) directly:
offset `+0x0` held a real, non-null pointer into other kernel code, and
offset `+0x10`/`+0x18` were null -- the shape of an on-disk `OSMetaClass`
instance whose `className`/`superClassLink` fields are populated only by
the kext's C++ static constructor at load time, not present in the file.
That's consistent with a *real* metaclass singleton, just not one whose
name is readable statically.

Cross-referenced that address against the real per-kext load-address table
(`ipsw kernel kexts -j`, the same tool used for the touch investigation)
against the exact pinned iPad5,3 12B410 kernelcache: `0xffffff80026938c0`
falls inside **`com.apple.driver.AppleARMPlatform`**'s own address range
(`0xffffff800265e000`-`0xffffff80026b2000`, immediately before
`IODARTFamily`) -- the same kext this project's TOUCH-3 fifth pass already
opened for the `KLCT` gate-dispatch trace. A prelinktext-wide scan also
found ~30 *other* kexts each caching a reference to this same metaclass
address, confirming it's a widely shared utility class, not something
DART-specific.

Fetched a real, unstripped `AppleARMPlatform.kext` (iOS 10.3, s8000/A9 --
different build, same class family, the identical technique TOUCH-3 used
for `KLCT`) from
[userlandkernel/ios-unstripped-kexts](https://github.com/userlandkernel/ios-unstripped-kexts)
via a sparse clone (a few hundred KB, not the whole repo) and read its real
C++ symbol table with `nm`. It defines **`AppleARMPerformanceController`**
with exactly two public, non-workloop-internal methods matching our call
shapes precisely:

```
AppleARMPerformanceController::enableDeviceClock(unsigned long, unsigned long)
AppleARMPerformanceController::enableDevicePower(unsigned long, unsigned long, unsigned long*)
```

-- a 2-argument and a 3-argument method, in that order, exactly matching
the become-available handler's two calls (`+0x560` with 2 args, `+0x568`
with 3 args). This is the **same class family** already reverse-engineered
in this project's TOUCH-3 investigation (`AppleT7000PerformanceController`,
the T7000-specific subclass, is where the clock-gate register formula
`ioBase + 0x20000 + gate_index*8`, bit 28 enable, across a 101-entry table,
was independently recovered) -- the DART's own gate request and the
touchscreen's `KLCT` clock gate both ultimately go through the same
SoC-wide performance-controller singleton.

The call-site arguments are consistent and readable across both
directions: become-available calls `enableDeviceClock(1, 0)` then
`enableDevicePower(1, 0, 0)`; become-unavailable calls
`enableDeviceClock(0, 0)` then `enableDevicePower(0, 0, 0)`. The first
argument tracks availability directly (1 = enable, 0 = disable) in both
calls; the second argument is a constant `0` in both directions and both
methods -- most likely a device/gate-index selector into
`AppleARMPerformanceController`'s own internal table, fixed for this
particular DART instance, distinct from the raw PMGR register gate index
found for touch (that translation happens inside `enableDeviceClock`/
`enableDevicePower` themselves, not visible at the DART's call site).

**Net conclusion, now solid**: Apple's DART requests its own clock *and*
power gate through the same shared performance-controller framework every
other SoC IP block (including touch's `KLCT`) uses -- not through the PCIe
port's `ps_pcie`/`PCIE_AUX`/`PCIE_REF` PMGR domains at all, and not through
anything Linux's current `power-domains = <&ps_pcie>` binding reaches.
This is a materially different -- and more specific -- root cause than
either the original AUX/REF-gate guess or a generic "missing power domain"
framing: it's a **whole different gate-request path** the Linux DT and
driver have no representation of.

**Still open**: the exact device/gate-index value (`0` at the call site,
but not yet confirmed as the physical PMGR gate index -- that translation
lives inside `enableDeviceClock`/`enableDevicePower`'s own bodies, which
weren't decompiled this pass) and its resulting physical register address.
Decompiling those two methods in *this exact* 8.1/T7000 kernelcache (not
just the iOS 10.3/A9 reference used for symbol identification) is the next
offline task, and can likely reuse the already-known clock-gate formula
from the touch investigation as a starting hypothesis for at least the
clock half.

**Do not build another DART hardware payload or DT change until the
physical gate is known.** The standing gate holds, now against a
concretely named class and two concretely named methods rather than an
unresolved virtual call.

### Physical register: attempted, genuinely not resolved this pass, 2026-09-24

Tried to close the last gap directly. Result is a real, honest wall, not a
found answer -- worth recording precisely so the next pass doesn't repeat
dead ends.

**The offset-based vtable read didn't hold up.** Reused the
memory-scan-for-a-known-pointer technique that worked cleanly for DART's
own vtable, anchored this time on `AppleT7000PerformanceController::
callPlatformFunction` (`0xffffff80031e921c`, already known from this
project's TOUCH-3 fifth pass, confirmed still valid by re-decompiling it --
same `KLCT`-dispatching body). One clean match at vtable base
`0xffffff80031f2090`. But reading `+0x560`/`+0x568` from that base and
force-decompiling both targets gave results inconsistent with
`enableDeviceClock`/`enableDevicePower`: `+0x560` is a trivial 3-instruction
stub (`mov w0,#0xe0000000; movk w0,#0x2c7; ret` -- unconditionally returns
an "unsupported"-shaped IOKit error, ignoring its arguments entirely), and
`+0x568` is a per-device state-matching lookup (walks a bitmask array
against a table entry, no MMIO access, and its Ghidra-inferred signature
took only 2 explicit parameters where `enableDevicePower` needs 3). A
`callPlatformFunction`-anchored offset that works reliably near the base
of the vtable does not reliably transfer this far into a ~150+ method
class -- the earlier "arg-count matches" reasoning was a real, useful
structural clue but not sufficient on its own to prove the exact slot
number, and this pass shows it doesn't.

**Found stronger, independent confirmation the mechanism is real,
though.** Searched `AppleARMPlatform.kext`'s own address range in *this
exact* kernelcache (not the iOS 10.3/A9 reference) for gate-related
strings and found `"enableDeviceClockGated() Exec Time"` and
`"Clock Gate Control"` -- genuine `IOReportChannel` telemetry labels,
proving `_enableDeviceClockGated` is a real, actively-instrumented
function in this exact build, not just an assumption carried over from a
different kernelcache. Their only cross-reference is the statistics-
registration function (`FUN_ffffff800266e3ec`, part of
`publishStatistics`/`initVoltageAndPerformanceStates`), which registers a
named performance counter but doesn't itself call the worker function --
a dead end for finding the entry point directly, but solid evidence the
function exists and matters.

**Located the right neighborhood, not yet the exact register.** A full
decompile pass across `AppleARMPlatform.kext`'s ~30,000 lines (all
defined functions) found a cluster of six functions that all read the
same per-device table already seen at `+0x568` (base pointer at object
offset `0x328`, `0x350`-byte stride per device) -- consistent with this
being the real device-state table `enableDeviceClock`/`enableDevicePower`
operate on. One of them
(`FUN_ffffff800266c57c`) dispatches a call shaped like an enable trigger
-- `helperObj->vtable[0x100](&deviceEntry[0x300], 1)`, where `helperObj`
is a *separate* cached object read from `this+0x298` -- the most promising
lead for the actual low-level register-write engine, but that helper
object's own class wasn't identified this pass, and none of the six
functions decompiled contain an obviously MMIO-shaped write (no large
constant resembling a PMGR base address such as the already-known
`0x20e000000`).

**Honest conclusion**: the mechanism, the class, and the two real method
names are solid, evidence-backed facts. The exact physical PMGR register
they resolve to is not -- three independent techniques (vtable-offset
math, string-xref, and a whole-kext function-cluster search) were tried
this pass and each hit a genuine wall, the same class of wall this
project's TOUCH-3 investigation documented explicitly rather than pushing
through with a guess. **Do not treat the per-device table offsets or
`FUN_ffffff800266c57c` as confirmed** -- they are leads for the next pass,
not conclusions.

### Scoped auto-analysis pass and real-symbol disassembly, 2026-09-24

Ran a real (not `-noanalysis`) Ghidra auto-analysis pass, but scoped to
just `AppleARMPlatform.kext` + `AppleT7000.kext`'s address ranges via
`AutoAnalysisManager.reAnalyzeAll()` on a restricted `AddressSet` -- 12
seconds, not the ~10 minutes a full-image re-analysis would cost. **Result:
the earlier function boundaries at `+0x560`/`+0x568` were already correct**
-- re-decompiling them afterward produced byte-identical output. This
rules out "bad function boundary from `-noanalysis`" as the explanation
for the earlier mismatch; the functions genuinely are what they looked
like (a 3-instruction "unsupported" stub, and a 2-explicit-parameter
state-matching lookup). That itself is new information: `+0x568`'s
confirmed 2-parameter shape does not match `enableDevicePower`'s declared
3-parameter signature, so the earlier vtable-offset identification of
`+0x560`/`+0x568` as `enableDeviceClock`/`enableDevicePower` specifically
was very likely wrong, even though the broader claim (DART's helper is
some `AppleARMPerformanceController`-family object, not `ps_pcie`) still
stands on kext-ownership and class-existence evidence independent of this
specific offset reasoning.

Pivoted to a more reliable source: disassembled `enableDeviceClock` and
`enableDevicePower` directly by symbol name in the real, unstripped
reference `AppleARMPlatform` binary (`llvm-objdump
--disassemble-symbols=...`, no ambiguity since these are real exported
C++ symbols, not decompiler guesses). **Both are thin delegating shims**,
confirmed byte-for-byte:

```
enableDeviceClock(gateArg, enable):
  if (*(this + 0x298) == 0) return 0xe00002c7;      // "unsupported"
  delegate = *(this + 0x290);
  tail-call delegate->vtable[0xe0](delegate, gateArg, enable, 0, 0);

enableDevicePower(gateArg, enable, outPtr):
  if (*(this + 0x2a0) == 0) return 0xe00002c7;       // same stub, same constant
  delegate = *(this + 0x290);
  tail-call delegate->vtable[0xe0](delegate, gateArg, enable, outPtr, 0);
```

Both check their own presence flag (`+0x298` for clock, `+0x2a0` for
power -- separate flags), then forward to the **same cached delegate
object** at `+0x290`, dispatching through the **same vtable slot `+0xe0`**
on it, arguments zero-padded to a fixed 4-parameter shape. This explains
the earlier "unsupported" stub exactly: it's the shared fallback when no
delegate is configured for that operation -- not evidence the mechanism
is unused, just evidence of *which* build/config has it wired up.

Searched our own 8.1/T7000 kernelcache for the same "delegate cached at a
fixed offset, dispatch via `+0xe0`" shape and found one real match
(`FUN_ffffff800266888c`, using offset `0x298` directly rather than the
reference build's separate flag/delegate pair at `0x298`/`0x290` -- plausible
given field layouts can shift between OS versions) -- but its own argument
shape (one parameter, forwarding a fixed field rather than the caller's own
arguments) doesn't cleanly match either enable method, so it is *not*
confirmed as `enableDeviceClock`/`enableDevicePower` itself, only
supporting evidence that the same delegate-shim architecture exists in
this build too.

**Net result of this pass**: a genuine, symbol-verified architectural
fact -- the real gate toggle happens inside a **separate delegate object**
(cached once, shared by both clock and power requests, invoked through one
common vtable slot), not inside `AppleARMPerformanceController` itself.
This is new, solid information, but it does not by itself locate the
delegate's own class or its `+0xe0` handler's register write in our exact
kernelcache. Four independent techniques across two research passes
(vtable-offset math, string-xref, function-cluster search, and now
real-symbol delegate-shim disassembly) have each narrowed the picture
without landing on the final address. **This is the same class of wall
this project's TOUCH-3 investigation hit and explicitly stopped at
("finding the offset from here means opening a new kext, a new
investigation") rather than push through with a guess.** Not pursuing
further via static analysis alone; matching that precedent here too.

### Review correction: helper class remains unproven, 2026-09-24

The availability transition result above survives review: the exact J81
kernelcache proves the manual-availability path, the two state-transition
handlers, their ordering, and the two opaque helper calls. The later claim
that this helper is `AppleARMPerformanceController` does **not** survive at
the same confidence level. Locating the *cast target or property symbol*
at `0xffffff80026938c0` inside `AppleARMPlatform.kext` establishes its
owning kext, but does not name the object returned to the DART at `+0xe8`.

An independently checked reference binary gives a more specific result:
`AppleARMIODevice::enableDeviceClock(enable, index)` and
`AppleARMIODevice::enableDevicePower(enable, out, index)` occupy exactly
the helper vtable slots `+0x560` and `+0x568` and have the DART call shapes.
The reference is `AppleARMPlatform.kext/AppleARMPlatform` from
`userlandkernel/ios-unstripped-kexts` commit `96ca2b7f`
(`kexts/10.3/s8000`, SHA-256
`8c098e3cec752cecbb4ff590ace675be7c20e6910898b99e74b22ca3f18b4533`).
They select index zero from a device's `clock-gates` and `power-gates`
arrays before forwarding the physical ID to the performance controller.
This makes `AppleARMIODevice`-family behavior a better candidate than
direct `AppleARMPerformanceController` calls, but it does not close the
case: J81's `dart-apcie1` has neither property, so the calls may return
unsupported or operate on another provider.

Treat the helper class, physical gate, and the assertion that it is
independent of `ps_pcie`/AUX/REF as **open**. The next bounded offline task
is to trace the exact store into DART `this+0xe8` in 12B410, establish
whether it is the DART provider cast to `AppleARMIODevice`, and capture the
two return values. If both are unsupported, trace virtual hook `+0x5e8`,
which is the first unresolved operation after availability changes. Do not
build another DART payload, add a DT power domain, or run `0026` from this
evidence alone.

### Helper and recovery path resolved, 2026-09-24

The exact 12B410 trace now resolves the remaining helper ambiguity. The
kernel is SHA-256
`19c277d60e0a1185b1e4a1b72cda4f1f550c0b0bf670791542234a6dbbcc28bf`.
`IODARTFamily::start()` stores its provider at `this+0x88` at
`0xffffff80026b2fec`. `AppleS5L8960XDART` then loads that provider,
performs `OSMetaClassBase::safeMetaCast` at `0xffffff80026c31d0` against
`AppleARMIODevice::gMetaClass` (`0xffffff80026938c0`), and stores the
result at `this+0xe8` at `0xffffff80026c31d4`. The AppleARMPlatform static
constructor at `0xffffff8002665d0c` names that metaclass
`AppleARMIODevice`. The helper is therefore the DART provider cast to
`AppleARMIODevice` (or a subclass), not a property lookup and not
`AppleARMPerformanceController`.

The resolved exact vtable slots are `+0x560` =
`AppleARMIODevice::enableDeviceClock` at `0xffffff80026656d8` and `+0x568`
= `AppleARMIODevice::enableDevicePower` at `0xffffff8002665788`. They use
`clock-gates[index]` and `power-gates[index]` respectively. J81's captured
`dart-apcie1` ADT node has neither array, so both index-zero calls return
`kIOReturnUnsupported` (`0xe00002c7`). The DART transition handler at
`0xffffff80026c5b38` ignores both results, sets available, and continues.
These calls cannot be the missing J81 DART gate or explain the Linux hang.

The first remaining hardware-facing path is now resolved too. The DART
vtable at `0xffffff80026c7140` maps `+0x5e8` to
`0xffffff80026c5d40`, matching `_dartRecoverFromPowerdown(bool)` against
two unstripped Apple references. After availability becomes true, Apple
writes `DART+0x24 = error-reflector >> 12` first; J81's ADT value
`0x20ffff000` gives `0x0020ffff`. It then restores mappings and
configuration, including cached TCR at `+0x0c`, `fetch-config` at `+0x30`,
`diag-config` at `+0x20`, `+0x1000` and related values, then clears/polls
the TLB. Linux instead begins `apple_dart_hw_reset()` with a read of
`DART+0x00` and does not perform this recovery ordering.

**Current best hypothesis:** the recovered write-first initialization
sequence, not a missing `clock-gates`/`power-gates` declaration, is the
meaningful difference behind `0025`. It is still a hypothesis until an
isolated test succeeds. The next implementation task is a compile-only J81
initialization quirk and an evidence-gated payload that performs only the
first Apple write (`+0x24 = 0x0020ffff`) before aborting probe, with no
`iommu-map`; do not run it until hardware testing is explicitly requested.

### Recovery-write evidence gate implemented and cross-build verified, 2026-09-24

`kernel/patches/0027-pcie-apple-t7000-dart-recovery-write-test.patch`,
layered directly on `0016` (a clean branch, same pattern as `0019`-`0026`
-- not stacked on `0025`/`0026`). `pcie` is unchanged from `0019`'s exact
inert PMGR-only probe. `dart_apcie1` stays flipped to `"okay"` as in
`0025`, but its `compatible` property is redirected from the real
`"apple,t7000-dart", "apple,s5l8960x-dart"` to a new,
test-specific `"apple,t7000-dart-recovery-test"` string, so the stock
`apple-dart` driver (already proven to hang here in `0025`) never binds to
this node at all -- there is no ambiguity in which driver wins, since
`apple-dart.c`'s own `of_match_table` simply doesn't recognize the new
compatible string.

A new, dedicated driver, `drivers/iommu/apple-dart-t7000-recovery-test.c`
(wired into `drivers/iommu/Kconfig`/`Makefile` as
`CONFIG_APPLE_DART_T7000_RECOVERY_TEST`, the same pattern `0016` used to
wire in the PCIe skeleton), does exactly one thing: `devm_platform_
ioremap_resource()`s the DART's register window, writes `0x0020ffff` to
offset `0x24` (Apple's own `_dartRecoverFromPowerdown()` formula, the
real J81 ADT `error-reflector` value `0x20ffff000` right-shifted 12 bits
-- not guessed, cited from the "Helper and recovery path resolved"
section above), logs before and after, and returns `-ENODEV` to abort
probe. No reset sequence, no IRQ registration, no IOMMU domain setup, no
further register access of any kind.

Built via the same reconstruct/diff/verify methodology used for every
patch this session: reconstructed the pre-patch (`0016`-baseline) state
of all four touched files (`drivers/pci/controller/pcie-apple-t7000.c`,
`arch/arm64/boot/dts/apple/t7001.dtsi`, plus -- new for this patch --
`drivers/iommu/Kconfig` and `Makefile`, fetched fresh from the pinned
commit since nothing before `0027` touches them), wrote the intended
post-patch content, generated the diff, then applied the assembled patch
to a fresh copy of the reconstruction and confirmed all five resulting
files (including the new `apple-dart-t7000-recovery-test.c`) byte-match
the intended content exactly. One real mistake caught by this process
before it reached the repo: the first assembled patch's DTS hunk had a
spurious three-hunk split (a trailing-blank-line mismatch between the
`before`/`after` reconstructions) that failed to apply cleanly on the
builder with "Hunk #3 FAILED at 407" -- fixed by matching the trailing
newline exactly, then re-verified clean.

New isolated build (`kernel/hoolock-pcie-dart-recovery-test.nix`,
`hoolock-pcie-dart-recovery-test-kernel`, `m1n1-hoolock-pcie-dart-
recovery-test` payload in `flake.nix`, config adds both
`CONFIG_PCIE_APPLE_T7000=y` and the new `CONFIG_APPLE_
DART_T7000_RECOVERY_TEST=y`). **Cross-build verified clean**, 2026-09-24:
exit 0, complete real payload (`Pongo.bin`/`m1n1.bin`/`t7001-j81.dtb`/
`Image.gz`/`initramfs.gz`/`m1n1-linux.bin`/`SHA256SUMS` all present, only
the same benign pre-existing `dtc` advisory warnings every prior payload
has produced). Verified beyond just the exit code, matching this
project's own standard: the built DTB's raw strings contain
`apple,t7000-dart-recovery-test` and not the real `apple,t7000-dart`/
`apple,s5l8960x-dart` compatible strings, and the built kernel's
`System.map` contains `apple_t7000_dart_recovery_test_probe`,
`_of_match`, `_driver_init`/`_driver_exit`, and the `_driver` struct
itself -- the new driver is genuinely compiled and linked in, not merely
present in source.

### `0027` hardware result: hangs, 2026-09-24

Ran on real hardware: same DFU/palera1n recipe as every prior round,
`05ac:4141` confirmed, `m1n1-linux.bin` uploaded via `boot/load_m1n1.py`.
**Result: hung.** Black screen, backlight only; no USB re-enumeration and
no `ping 172.16.42.1` response over 30+ seconds, then reconfirmed still
black after the device was replugged. Same observable signature as `0018`
(both attempts) and `0025`.

**This is a genuinely informative negative result, not just a repeat.**
`0027`'s driver performs *only* a single write to `DART+0x24` -- no read
of any kind, no reset sequence, nothing else -- yet the hang reproduced on
the very first register touch. `0025`'s stock `apple-dart` driver begins
with a *read* of `DART+0x00`. If the hang were specifically about
read-before-write ordering, `0027` should have been clean. It wasn't.
**The most consistent reading now is that essentially any MMIO access to
the DART's register window hangs the bus**, independent of which
operation or which offset is touched first -- not a specific
sequencing defect in Apple's recovery formula.

This reopens, rather than closes, the power/clock-gating question --
but points at a **different, untested mechanism** than the one already
ruled out. The `AppleARMIODevice`-family `clock-gates[index]`/
`power-gates[index]` wrapper calls are a confirmed dead end for J81 (no
array on `dart-apcie1`'s ADT node, calls return unsupported, Apple's own
driver ignores that and proceeds) -- but that only shows Apple's *software*
never explicitly requests a per-device gate through *that* mechanism. It
does not show the underlying silicon needs no gate at all: real hardware
commonly relies on a gate already being active via a parent domain, a
board-level default, or iBoot/SecureROM's own early power sequencing --
none of which this project's checkm8-based boot chain (which skips iBoot
entirely) can be assumed to replicate.

**The specific, never-tested angle**: `dart_apcie1` has no `power-domains`
property of its own anywhere in the current DT -- confirmed directly
against the trusted `0016`-baseline reconstruction. `pcie` is the only
node in this whole block with `power-domains = <&ps_pcie>`. Every DART
test so far (`0025`, `0027`) enabled `dart_apcie1` alongside `pcie`
without ever giving the DART node its own domain reference -- meaning the
one straightforward, standard-Linux-binding hypothesis (does the DART's
own MMIO window require `power-domains = <&ps_pcie>`, or one of the
already-known-to-exist-but-unreferenced `ps_pcie_aux`/`ps_pcie_ref` genpd
nodes in the pinned PMGR DTS) has never actually been tried on hardware.
This is a different, more basic mechanism than the disproven
`AppleARMIODevice` gate-wrapper theory, and the natural next controlled
test: same `0027` driver unchanged (a single bounded write, no reset, no
read), with `dart_apcie1` given an explicit `power-domains` reference.

**Required test order if hardware work resumes:** begin with only
`power-domains = <&ps_pcie>` on `dart_apcie1`, leaving `0027` otherwise
byte-for-byte unchanged. This is not redundant with the existing PCIe-node
reference: the DART test driver may bind before the inert PCIe driver has
acquired `ps_pcie`, whereas a direct DART reference makes genpd power it
before the DART probe. A clean boot would establish a real lifecycle/order
dependency. A repeat hang would rule out only that direct-domain ordering,
not AUX/REF.

Before assigning `ps_pcie_aux` or `ps_pcie_ref` to a DART MMIO test, test
each domain individually with the DART node bound to a no-MMIO logging
driver. That isolates whether merely powering the sibling domain is safe.
Only after each clean result may it be paired, one at a time, with the
single-write `0027` driver. Never attach all three domains in one payload:
that would make either outcome uninterpretable.

**Do not build or run another DART payload without an explicit go-ahead.**
Test 2 (`0026`, `iommu-map` restored) stays untested and is now doubly
premature -- both the recovery-write and the gate-wrapper theories it
would have followed from are no longer live leads on their own.

### Domain-gate plan implemented and cross-build verified, 2026-09-24

Three new patches, matching the exact ordered plan above.

**`kernel/patches/0028-pcie-apple-t7000-dart-recovery-write-pspcie-test.patch`**
(Test A, run first). Layered directly on `0016`, reproducing `0027`'s
Kconfig/Makefile/driver-file changes in full (an independent branch, not
stacked on `0027`) plus one new DT line: `dart_apcie1` gets
`power-domains = <&ps_pcie>` in addition to its existing redirect away
from the stock `apple-dart` driver. The single-write driver itself
(`apple-dart-t7000-recovery-test.c`) is otherwise byte-for-byte unchanged
from `0027`. `pcie` is unchanged from `0019`'s inert probe. This tests the
real, previously-untried genpd-ordering guarantee: a device's own
`power-domains` reference makes Linux power that domain before *that
device's* probe() runs, which `0027` alone never guaranteed (`pcie`'s own
reference only orders against `pcie`'s probe, a different device).

**`kernel/patches/0029-pcie-apple-t7000-dart-nommio-pspcieaux-test.patch`**
and **`0030-...-pspcieref-test.patch`** (Tests B1/B2, run only if A still
hangs). Both layered directly on `0016`, each an independent branch. Both
introduce a new, dedicated no-MMIO logging driver
(`drivers/iommu/apple-dart-t7000-nommio-test.c`, new
`CONFIG_APPLE_DART_T7000_NOMMIO_TEST`) that mirrors `0019`'s own inert PCIe
probe exactly: `dev_info()` then `return 0`, no `ioremap`, no register
access of any kind. `dart_apcie1` is redirected to this driver via yet
another dedicated compatible string (`"apple,t7000-dart-nommio-test"`,
distinct from `0027`/`0028`'s) and given `power-domains = <&ps_pcie_aux>`
(`0029`) or `<&ps_pcie_ref>` (`0030`) -- never both, never combined with
`ps_pcie`, matching the plan's explicit requirement. `pcie` is unchanged
in both. These test whether merely powering each sibling domain is safe
at all, before either is ever paired with a real MMIO-touching DART test.

All three built via the same reconstruct/diff/verify methodology as every
prior patch: pre-patch state reconstructed for every touched file
(`pcie-apple-t7000.c`, `t7001.dtsi`, `drivers/iommu/Kconfig`/`Makefile`),
intended post-patch content written, diffs generated and offset-corrected,
then each assembled patch applied to a fresh copy of the reconstruction
and every resulting file byte-verified against the intended content
before being written into the repo. All three applied cleanly with no
fuzz.

New isolated builds (`kernel/hoolock-pcie-dart-recovery-pspcie-test.nix`,
`kernel/hoolock-pcie-dart-nommio-pspcieaux-test.nix`,
`kernel/hoolock-pcie-dart-nommio-pspcieref-test.nix`, three matching
`m1n1-hoolock-pcie-dart-*-test` payloads in `flake.nix`, each config
adding the relevant new `CONFIG_APPLE_DART_T7000_*_TEST=y` on top of the
usual `CONFIG_PCIE_APPLE_T7000=y`). **All three cross-build verified
clean**, 2026-09-24: exit 0, complete real payloads, only the same benign
pre-existing `dtc` advisory warnings every prior payload has produced.
Verified beyond the exit code: each built DTB's raw strings carry the
correct dedicated compatible string (`apple,t7000-dart-recovery-test` for
A, `apple,t7000-dart-nommio-test` for B1/B2 -- and `dtc` itself would have
hard-failed, not merely warned, had either sibling domain's phandle
reference been invalid, so the successful compile is itself confirmation
`&ps_pcie_aux`/`&ps_pcie_ref` resolve correctly); each built kernel's
`System.map` contains the relevant new driver's probe symbol and driver
struct, confirming genuine compilation, not just source presence.

**Not yet hardware-tested.** `result` now points to Test A
(`m1n1-hoolock-pcie-dart-recovery-pspcie-test`), the required first step.
Tests B1/B2 are built and staged ahead of time (avoiding a second
build-wait cycle later, the same reasoning `0025`/`0026` used) but must
not be *run* on hardware unless Test A hangs, per the ordered plan above.

### Test A (`0028`) hardware result: clean -- the hang is resolved, 2026-09-24

Ran on real hardware: same DFU/palera1n recipe as every prior round,
`05ac:4141` confirmed, `m1n1-linux.bin` uploaded via `boot/load_m1n1.py`.
**Result: clean boot.** postmarketOS visible on screen, USB networking up
(`172.16.42.1`, 0% ping loss over 3 packets), debug shell reachable by
telnet. `dmesg`:

```
[    0.064188] apple-t7000-dart-recovery-test 602002000.iommu: t7000-dart recovery-write-test: about to write error-reflector (offset 0x24) = 0x0020ffff
[    0.064202] apple-t7000-dart-recovery-test 602002000.iommu: t7000-dart recovery-write-test: write completed, aborting probe
[    0.126592] pcie-apple-t7000 610000000.pcie: t7000-pcie pmgr-only-test: probe reached (no MMIO, no PCI core; DART recovery-write test enabled separately)
```

The write to `DART+0x24` completed in 14 microseconds (`0.064202` -
`0.064188`) and boot continued normally through `pcie`'s own probe and the
rest of the kernel's startup to a fully working shell. **This is the exact
same driver and the exact same single write that hung in `0027`** -- the
only change between the two patches is `dart_apcie1` gaining its own
`power-domains = <&ps_pcie>` reference.

**This resolves the investigation's central question.** It was never
about a missing AUX/REF gate, and it was never about read-before-write
ordering inside the DART's own recovery sequence (both `0025`'s read-first
stock driver and `0027`'s write-only test hung identically). It was about
**genpd power-up ordering relative to the DART's own device probe**:
`pcie`'s `power-domains = <&ps_pcie>` reference only guarantees `ps_pcie`
is powered before *`pcie`'s own* probe runs -- it says nothing about
whether `ps_pcie` is still (or yet) powered when a *different* device's
(`dart_apcie1`'s) probe runs later, since Linux's genpd core scopes that
guarantee per consumer device, not globally. Once `dart_apcie1` gets its
own direct reference, genpd guarantees `ps_pcie` is active before *its*
probe runs too, and the exact same MMIO write that previously hung
succeeds instantly. `ps_pcie_aux`/`ps_pcie_ref` were never the answer --
Tests B1/B2 (`0029`/`0030`) are no longer needed and should not be run.

**What this means for the real driver**: the stock Linux `apple-dart`
driver (`drivers/iommu/apple-dart.c`) never gave `dart_apcie1` a
`power-domains` reference either -- exactly the same gap `0025` (which
hung) shared with `0027`. The natural next test, not yet built, is
restoring the *stock* `apple-dart` driver's real compatible strings on
`dart_apcie1` (undoing the `0025`/`0027`/`0028` compatible-string
redirect) while keeping the new `power-domains = <&ps_pcie>` reference --
i.e. repeating `0025` itself with this one fix applied. If that boots
clean too, DART's own full probe/reset/IRQ path is unblocked, and the
project can return to the deferred four-step plan (DART active → tunables
→ PERST release → link start → PCI enumeration).

### Power-domains fix implemented and cross-build verified, 2026-09-24

`kernel/patches/0031-pcie-apple-t7000-dart-pspcie-fix-test.patch`,
layered directly on `0016` (an independent branch, not stacked on
`0025`/`0027`/`0028`/`0029`/`0030`). `pcie` is unchanged from `0019`'s
inert probe. `dart_apcie1`'s `compatible` is **restored** to the real
`"apple,t7000-dart", "apple,s5l8960x-dart"` strings -- undoing the
test-driver redirect every `0025`/`0027`/`0028` variant used -- so the
stock Linux `apple-dart` driver binds for real this time: register map,
reset, IRQ registration, the works. The only other change from `0025` is
the one fix Test A proved: `power-domains = <&ps_pcie>` added directly to
`dart_apcie1`. Still no `iommu-map` -- this isolates the DART's own real
probe/reset/IRQ path with the fix applied, before ever restoring the
PCIe-to-DART IOMMU consumer relationship (that remains a separate,
later test, matching the original `0025`/`0026` pairing).

Built via the same reconstruct/diff/verify methodology as every prior
patch; applied cleanly with no fuzz, both touched files byte-verified
against the intended content. No new Kconfig/Makefile/driver-file changes
were needed this time -- `CONFIG_APPLE_DART` is already `=y` in the base
Hoolock defconfig, and this test uses the existing stock driver rather
than a new dedicated one.

New isolated build (`kernel/hoolock-pcie-dart-pspcie-fix-test.nix`,
`m1n1-hoolock-pcie-dart-pspcie-fix-test` payload in `flake.nix`).
**Cross-build verified clean**, 2026-09-24: exit 0, complete real payload,
only the same benign pre-existing `dtc` advisory warnings every prior
payload has produced. Verified beyond the exit code: the built DTB's raw
strings now carry the **real** `apple,t7000-dart`/`apple,s5l8960x-dart`
compatible strings (not a test-specific redirect), confirming the stock
driver genuinely binds to this node in this build; `dtc`'s clean compile
also confirms the `power-domains = <&ps_pcie>` phandle resolves correctly
(an invalid reference would have been a hard compile failure, not a
warning).

**Not yet hardware-tested.** `result` now points to this payload.

### `0031` hardware result: clean -- the real DART driver works, 2026-09-24

Ran on real hardware: same DFU/palera1n recipe as every prior round,
`05ac:4141` confirmed, `m1n1-linux.bin` uploaded via `boot/load_m1n1.py`.
**Result: clean boot.** postmarketOS visible on screen, USB networking up
(`172.16.42.1`, 0% ping loss over 3 packets), debug shell reachable by
telnet. `dmesg`:

```
[    0.065412] apple-dart 602002000.iommu: DART [pagesize 1000, 4 streams, bypass support: 0, bypass forced: 0, AS 32 -> 36] initialized
[    0.130263] pcie-apple-t7000 610000000.pcie: t7000-pcie pmgr-only-test: probe reached (no MMIO, no PCI core; DART power-domains fix enabled separately)
```

This is the **stock, unmodified Linux `apple-dart` driver's own success
message** -- not a diagnostic stand-in. `apple_dart_probe()` genuinely ran
to completion: mapped the register window, read the DART's real hardware
capability registers (4 KiB page size, 4 translation streams, no bypass
support, 32-to-36-bit address space extension -- all real values read off
the hardware, not guessed or hardcoded anywhere in this project's patches),
reset the unit, and registered successfully. No hang, no timeout, no
missing boot text -- the exact opposite of `0025`'s black screen with this
one DT property added.

**This closes the investigation that began with `0018`'s two hangs.** The
complete causal chain, now fully evidenced end to end:

1. `0018` (full enable sequence, DART/`iommu-map` live) hung -- twice,
   identically.
2. `0019`-`0024` isolated every other piece of the PCIe enable path
   (DT status, `power-domains = <&ps_pcie>` on `pcie` itself, shared-window
   reads, ECAM reads, the full generic PCI bus scan, all remaining
   shared-window offsets) as safe in isolation, narrowing the difference to
   DART activation alone.
3. `0025` (DART enabled, stock driver, no `iommu-map`) reproduced the hang
   in isolation -- confirming DART was the cause, not incidental to `0018`'s
   other changes.
4. Offline Ghidra tracing of the exact 12B410 kernelcache found Apple's own
   `AppleS5L8960XDART` performs a `_dartRecoverFromPowerdown()` write-first
   sequence as part of becoming available, and separately that its
   `clock-gates`/`power-gates` gate-wrapper calls are a dead end for J81
   (no array declared, Apple's own driver ignores the failure).
5. `0027` (an isolated single write, no read at all) also hung, ruling out
   read-before-write ordering as the explanation.
6. `0028` (the same single write, `dart_apcie1` given its own
   `power-domains = <&ps_pcie>` reference) booted clean -- identifying the
   real cause: genpd power-up ordering scoped per consumer device, not a
   missing gate.
7. `0031` (this test): the same fix applied to the real, unmodified stock
   driver. Clean. **DART is now provably usable under Linux on this
   hardware.**

**Next, not yet built or decided**: `dart_apcie1` still has no `iommu-map`
consumer relationship declared to `pcie` -- this test characterizes the
DART's own probe/reset/IRQ path in isolation, the same scope `0025` always
had. Per the user's own four-step plan (recorded earlier this
investigation), the next step after DART succeeds is restoring `pcie`'s
`iommu-map` (establishing the real IOMMU-consumer relationship via
`of_iommu_configure()`, which was `0026`'s original, still-untested scope)
-- now with the `power-domains` fix carried over -- before eventually
returning to the full Apple controller sequence (DART active → tunables →
PERST release → link start → PCI enumeration).

### `iommu-map` restoration implemented and cross-build verified, 2026-09-24

`kernel/patches/0032-pcie-apple-t7000-dart-pspcie-fix-iommu-map-test.patch`,
layered directly on `0016` (an independent branch, not stacked on any
earlier DART patch). `dart_apcie1` keeps `0031`'s exact fix (real
compatible strings, `power-domains = <&ps_pcie>`, status `okay`). `pcie`
is unchanged from `0019`'s inert probe except for one restored property:
`iommu-map = <0x100 &dart_apcie1 0 1>` and `iommu-map-mask = <0xff00>`
-- the one thing `0025`/`0031` deliberately omitted, and `0026`'s
original (never hardware-tested) scope. This establishes the real
PCIe-to-DART IOMMU consumer relationship: `of_iommu_configure()` runs
automatically when the `pcie` platform device is created, before any
driver `.probe()` executes, so this exercises DT/OF plumbing this
project's PCIe testing has not touched before, distinct from (and
potentially more than) the DART's own bare probe path `0031` already
proved safe.

Built via the same reconstruct/diff/verify methodology as every prior
patch; applied cleanly with no fuzz, both touched files byte-verified
against the intended content. No new Kconfig/Makefile/driver-file changes
needed -- `CONFIG_APPLE_DART` is already `=y`, and `pcie`'s own inert
driver file is unchanged from `0019`'s in every respect but its header
comment.

New isolated build (`kernel/hoolock-pcie-dart-pspcie-fix-iommu-map-test.nix`,
`m1n1-hoolock-pcie-dart-pspcie-fix-iommu-map-test` payload in
`flake.nix`). **Cross-build verified clean**, 2026-09-24: exit 0, complete
real payload, only the same benign pre-existing `dtc` advisory warnings.
Verified beyond the exit code: the built DTB's raw strings carry the real
`apple,t7000-dart`/`apple,s5l8960x-dart` compatible strings, and `dtc`'s
clean compile confirms both the `power-domains` and `iommu-map` phandle
references resolve correctly (either being invalid would be a hard
compile failure, not a warning).

**Not yet hardware-tested.** `result` now points to this payload.

### `0032` hardware result: clean -- IOMMU consumer relationship confirmed, 2026-09-24

Ran on real hardware: same DFU/palera1n recipe as every prior round,
`05ac:4141` confirmed, `m1n1-linux.bin` uploaded via `boot/load_m1n1.py`.
**Result: clean boot.** postmarketOS visible on screen, USB networking up
(`172.16.42.1`, 0% ping loss over 3 packets), debug shell reachable by
telnet. `dmesg`:

```
[    0.019275] iommu: Default domain type: Translated
[    0.019282] iommu: DMA domain TLB invalidation policy: strict mode
[    0.066192] apple-dart 602002000.iommu: DART [pagesize 1000, 4 streams, bypass support: 0, bypass forced: 0, AS 32 -> 36] initialized
[    0.126074] pcie-apple-t7000 610000000.pcie: t7000-pcie pmgr-only-test: probe reached (no MMIO, no PCI core; DART power-domains fix with iommu-map enabled separately)
```

The DART itself initializes identically to `0031`. New this round: the
generic IOMMU core log lines (`iommu: Default domain type: Translated`,
`iommu: DMA domain TLB invalidation policy: strict mode`) -- confirming a
real *translated* (not passthrough/identity) default IOMMU domain was set
up, the expected configuration once a device (`pcie`) has a genuine
`iommu-map` consumer relationship wired through `of_iommu_configure()`.
No errors, no hang, no missing boot text.

**This is the second half of `0026`'s originally-planned test, now
finally run and clean.** The full evidence chain from `0018` through here
is complete: DART probes and initializes for real, and the PCIe-to-DART
IOMMU plumbing that real endpoint drivers (like `brcmfmac` for the WiFi
chip) would depend on is confirmed wired correctly at the OF/DMA layer.
Nothing about PCIe link training, controller register writes, PERST
handling, or bus enumeration has been touched yet -- `pcie`'s own driver
is still `0019`'s inert stand-in.

**Next, not yet decided**: implementing the real PCIe host-controller
driver logic this project's own earlier research already recovered (the
`_enablePortHardware` register sequence, PERST via the DT's `reset-gpios`,
DART already proven safe to enable ahead of controller writes) -- the
`0018`-shaped work, but now built on a fully evidenced, hang-free
foundation instead of the original guesses that caused `0018`'s hangs.
This is a materially larger, more complex change than any single-variable
DT test in this investigation and deserves its own explicit go-ahead
before implementation starts.

### Real PCIe host-controller driver, Stage 1: enable-sequence write test implemented and cross-build verified, 2026-09-24/25

Explicit go-ahead received, then "continue with the build and research
over night" -- proceeding through staged, cross-build-only (no hardware)
steps autonomously. Implementing the real driver as four single-variable
stages rather than one combined change, matching this investigation's own
established discipline:

- **Stage 1** (`0033`): the recovered `_enablePortHardware` shared-window
  write sequence alone -- no PERST, no per-port window, no link-start bit,
  no enumeration.
- **Stage 2** (`0034`): Stage 1 plus `pci_host_common_init()`'s generic
  ECAM bus scan -- still no PERST, so the scan is expected to find nothing
  (all-Fs reads), but this tests that *combining* the write sequence with
  real enumeration (which also performs config-space writes during
  BAR-sizing, unlike any bounded read test so far) doesn't hang.
- **Stage 3**: Stage 2 plus PERST deassertion via the `pci@0,0`/
  `reset-gpios` child node (`pci_host_common_parse_ports()`'s own built-in
  mechanism, already confirmed present in the pinned kernel source).
- **Stage 4**: Stage 3 plus the per-port controller window (ADT index 3)
  and its link-start bit -- the final piece of Apple's recovered order,
  never implemented in any prior attempt including the original `0018`.

**Stage 1 (`0033`) implemented.** Layered on `0016` (a clean branch, not
stacked on `0032` or any other test), matching every prior test in this
series. DTS portion identical to `0032`'s verified content (real DART
compatible strings, `power-domains = <&ps_pcie>` on `dart_apcie1`,
`iommu-map` restored on `pcie`) -- only comments updated to describe this
stage. Driver portion (`drivers/pci/controller/pcie-apple-t7000.c`) fully
rewritten: maps the shared window (reg index 9), writes the complete
recovered enable sequence for board port 1 (clear `LINK_ENABLE` bit 0; set
`PERST_INTERNAL` bit 0; `udelay(10)`; clear `UNKNOWN_10C` bit 0; set
`REFCLK_EN` bit 0 then bit 20; `udelay(100)`; set `LINK_ENABLE` bit 0;
clear `PERST_INTERNAL` bit 8; write `3` to the LTSSM-start register twice,
matching `enableGated`'s own repeat), logs before/after register state,
returns 0. No PERST, no per-port window, no `pci_host_common_init()`, no
bus enumeration.

Verified byte-exact via the established reconstruct/diff/verify
methodology before writing the real patch file (both the driver source and
the DTS region matched the intended content exactly when the diff was
re-applied to a fresh reconstruction of the `0016` baseline).

**Cross-build verified clean, 2026-09-25**: `nix build
.#packages.x86_64-linux.m1n1-hoolock-pcie-enable-sequence-test --no-link
-L` exits 0 -- complete real payload (`Pongo.bin`, `m1n1.bin`,
`t7001-j81.dtb`, `Image.gz`, `initramfs.gz`, `m1n1-linux.bin`, real
`SHA256SUMS`), only the same benign pre-existing `dtc` `power-domains`/
`gpios` advisory warnings this DTS has emitted since `0031`, zero `error:`
lines. Verified beyond the exit code: the built DTB's decompiled `pcie`/
`dart_apcie1` nodes carry the expected `reg`/`compatible` values, and the
kernel's `System.map` has `apple_t7000_pcie_probe`/`_driver_init`/
`_driver_exit`/`apple_t7000_pcie_driver` -- confirming the new driver is
genuinely compiled and linked in (the two small `static` helper functions,
`t7000_pcie_enable_port_hardware`/`apple_t7000_pcie_map_window`, don't
appear as separate symbols, consistent with ordinary compiler inlining of
single-call-site statics, not a sign the code was dropped -- confirmed by
also grepping the built `Image` for this driver's own `dev_info()` format
strings, e.g. `"t7000-pcie enable-seq-test: about to write the recovered
enable sequence for port %d"`, all present verbatim). `result` now points
to this payload.

**Hardware result: clean, 2026-09-25.** Same DFU/palera1n recipe.
postmarketOS booted normally, USB networking up (0% ping loss over 3
packets), debug shell reachable. `dmesg` confirms the complete write
sequence ran and the register transitions match the recovered order
exactly:

```
[    0.128002] pcie-apple-t7000 610000000.pcie: t7000-pcie enable-seq-test: probe entry
[    0.128102] pcie-apple-t7000 610000000.pcie: t7000-pcie enable-seq-test: window 9 at [mem 0x600000000-0x600001fff]
[    0.128200] pcie-apple-t7000 610000000.pcie: t7000-pcie enable-seq-test: before port 1 refclk_en=0x11010100 perst_internal=0x00000100 unknown_10c=0x00000001 link_enable=0x00000000 ltssm=0x00000000
[    0.128340] pcie-apple-t7000 610000000.pcie: t7000-pcie enable-seq-test: about to write the recovered enable sequence for port 1
[    0.128538] pcie-apple-t7000 610000000.pcie: t7000-pcie enable-seq-test: enable sequence write completed
[    0.128618] pcie-apple-t7000 610000000.pcie: t7000-pcie enable-seq-test: after port 1 refclk_en=0x11110101 perst_internal=0x00000001 unknown_10c=0x00000000 link_enable=0x00000001 ltssm=0x00000000
[    0.128661] pcie-apple-t7000 610000000.pcie: t7000-pcie enable-seq-test: probe complete -- no PERST, no per-port window, no link-start bit, no enumeration
```

Verified register-by-register against the recovered sequence:
`unknown_10c` clears (`0x1`→`0x0`, matches step 4), `refclk_en` gains
both bit 0 and bit 20 (`0x11010100`→`0x11110101`, matches steps 5-6),
`link_enable` sets bit 0 (`0x0`→`0x1`, matches step 8), and
`perst_internal` loses bit 8 while keeping bit 0 set from the earlier
write (`0x100`→`0x1`, matches steps 2 and 9). One genuinely informative
detail: `ltssm` reads back `0x00000000` after the sequence, even though
step 10 writes `3` to it twice -- the write did not visibly "stick".
This is not a fault; a link-start register plausibly only latches once
its preconditions (PERST deasserted, the per-port window's own
link-start bit) are also satisfied, both intentionally still absent in
this stage. Worth re-checking once Stage 3/4b add those pieces, not a
sign anything is wrong here.

No new dmesg errors beyond the pre-existing, unrelated `g_multi` gadget
probe failure (`failed to start g_multi: -22`) already seen in every
prior clean boot on this kernel. **This closes out Stage 1's hardware
gate -- proceed to Stage 2.** Full patch:
`kernel/patches/0033-pcie-apple-t7000-enable-sequence-write-test.patch`.

### Real PCIe host-controller driver, Stage 2: enable-sequence + generic ECAM enumeration test implemented and cross-build verified, 2026-09-25

**Stage 2 (`0034`) implemented.** Layered on `0016` (a clean branch, not
stacked on `0033`). DTS portion identical to `0033`'s -- only comments
updated. Driver portion rewritten around a custom `pci_ecam_ops.init`
callback (modeled on the minimal `pci_ecam_ops` pattern `0023` already
proved safe standalone, combined with the original `660645d` commit's
`apple_t7000_pcie_init(struct pci_config_window *cfg)` shape): `.init()`
maps the shared window and runs Stage 1's exact enable sequence for port
1, then returns 0 so `pci_host_common_init()`'s normal
`devm_pci_alloc_host_bridge()` + `pci_host_probe()` path runs a real
generic bus scan. Still no PERST deassertion (no `reset-gpios` child
node this stage) and no per-port controller window, so the scan is
expected to find nothing (all-Fs reads) -- the purpose of this stage is
confirming that *combining* the write sequence with the real generic
enumeration path (which, unlike any bounded-read test in this
investigation, also performs config-space *writes* during BAR-sizing
while walking every device/function slot) doesn't hang on its own,
before PERST is added in Stage 3.

Verified byte-exact via the established reconstruct/diff/verify
methodology before writing the real patch file.

**Cross-build verified clean, 2026-09-25**: `nix build
.#packages.x86_64-linux.m1n1-hoolock-pcie-enable-enumeration-test
--no-link -L` exits 0 -- complete real payload, only the same benign
pre-existing `dtc` advisory warnings. Verified beyond the exit code: the
built DTB's `pcie` node carries the expected content, `System.map` has
`apple_t7000_pcie_init`/`apple_t7000_pcie_ecam_ops`/`apple_t7000_pcie_probe`
plus confirmation that the generic ECAM/host-common machinery
(`pci_host_common_init`, `pci_ecam_create`,
`pci_generic_config_read`/`_write`) is genuinely linked into this build
(not merely declared), and the built `Image` contains every one of the
driver's own diagnostic `dev_info()` strings verbatim. `result` now
points to this payload.

**Hardware result: clean, 2026-09-25.** postmarketOS booted normally,
USB networking up (0% ping loss), debug shell reachable. `dmesg`
confirms the same register transitions as Stage 1 (unchanged, as
expected), followed by real generic PCI enumeration:

```
[    0.126391] pcie-apple-t7000 610000000.pcie: PCI host bridge to bus 0000:00
[    0.126714] pci 0000:00:01.0: [106b:1002] type 01 class 0x060400 PCIe Root Port
[    0.126752] pci 0000:00:01.0: PCI bridge to [bus 00]
[    0.126777] pci 0000:00:01.0:   bridge window [io  0x0000-0x0fff]
[    0.126803] pci 0000:00:01.0:   bridge window [mem 0x00000000-0x000fffff]
[    0.126830] pci 0000:00:01.0:   bridge window [mem 0x00000000-0x000fffff pref]
[    0.126888] pci 0000:00:01.0: PME# supported from D0 D3hot D3cold
[    0.127023] OF: /soc/pcie@610000000: no iommu-map translation for id 0x8 on (null)
[    0.128164] pci 0000:00:01.0: bridge configuration invalid ([bus 00-00]), reconfiguring
[    0.128496] pci 0000:00:01.0: PCI bridge to [bus 01]
```

**This is a genuinely new, positive result beyond "didn't hang"**: the
root port's own config space responded correctly and identified itself
with Apple's real vendor ID -- `[106b:1002]`, type 01 (PCI-to-PCI
bridge), class `0x060400` (PCI bridge) -- confirming the ECAM/config
access path works correctly through the *entire* generic PCI core
(`pci_host_probe()`'s full bus-walk, bridge discovery, and BAR-sizing
config writes), not just the register-level reads/writes prior tests
exercised. No downstream device was found behind the bridge, exactly as
expected -- PERST is still asserted in this stage, so the link cannot
train. The `no iommu-map translation for id 0x8` line is benign: the
generic PCI/IOMMU glue looks up a translation for the root port's own
requester ID before bus renumbering, and this DT's `iommu-map` only
declares the expected post-renumbering downstream device ID (`0x100`),
not the root port's own -- not an error, no OF/IOMMU code path
faulted. No other new dmesg errors. **Stage 2's hardware gate is closed
-- proceed to Stage 3.** Full patch:
`kernel/patches/0034-pcie-apple-t7000-enable-enumeration-test.patch`.

### Real PCIe host-controller driver, Stage 3: a design correction caught before building -- `pci_host_common_parse_ports()` is not automatic, 2026-09-25

While drafting Stage 3 (Stage 2 plus PERST deassertion via a
`pci@0,0`/`reset-gpios` DT child node), the original plan relied on a
claim carried over from the very first `0018` attempt's commit message:
that `pci_host_common_init()` automatically deasserts PERST# for any
DT child node with a `reset-gpios` property, via
`pci_host_common_parse_ports()`. Before building or committing anything,
this was checked directly against the real pinned
`drivers/pci/controller/pci-host-common.c` source (already cached from
an earlier fetch this session, and independently re-confirmed
byte-identical against the actual pinned kernel source tree in the Nix
store) -- **the claim is wrong**. `pci_host_common_parse_ports()` is
opt-in: `pci_host_common_init()` never calls it, and no Apple driver in
this kernel tree calls it either (only `drivers/pci/controller/dwc/
pci-imx6.c` does). This matches and reconfirms this project's own
earlier, already-documented correction of the same misconception (see
the "PMGR-only test" era notes above) -- this session independently
re-derived and re-verified it while designing Stage 3 specifically,
rather than assuming the DT node alone would work.

Found the real usage pattern in `pci-imx6.c`'s
`imx_pcie_host_init()`/`imx_pcie_assert_perst()`: a driver must call
`pci_host_common_parse_ports(dev, bridge)` itself (guarded by
`list_empty(&bridge->ports)`), then explicitly walk the resulting
`bridge->ports`/`port->perst` lists and call `gpiod_direction_output()`
itself to actually drive the GPIO -- the helper only *discovers* the
descriptor (via `devm_fwnode_gpiod_get(..., GPIOD_ASIS, ...)`, which
does not touch the pin).

**Stage 3 (`0035`) implemented correctly, accounting for this.**
`probe()` now calls `pci_host_common_parse_ports()` explicitly before
`pci_host_common_init()` (safe to do before the enable-sequence write,
since it only fetches the descriptor); the `.init()` callback recovers
the `bridge` pointer via `platform_get_drvdata()` (set by
`pci_host_common_init()` itself before it creates the ECAM window/calls
`.init()`), runs Stage 1/2's enable sequence unchanged, then walks
`bridge->ports` and calls `gpiod_direction_output(desc, 0)` once to
deassert PERST# -- a single deassert, not an imx6-style assert-then-
deassert power-sequencing dance, matching Apple's own recovered call
trace (a single `function-perst(0)` deassert, no separate assert step
recovered). Followed by `msleep(PCIE_RESET_CONFIG_WAIT_MS)` (100 ms),
the same generic PCIe-spec settle constant `pci-host-common.h`'s own
`pci_host_common_link_train_delay()` and `pci-imx6.c` use -- a standard
margin, not an Apple-recovered value.

**Cross-build verified clean, 2026-09-25**: `nix build
.#packages.x86_64-linux.m1n1-hoolock-pcie-enable-enumeration-perst-test
--no-link -L` exits 0 -- complete real payload, only the same benign
pre-existing `dtc` warning class (now including one new instance for
`pci@0,0`'s own `reset-gpios` property, the same "cell 0 is not a
phandle reference" advisory this DTS already emits for `gpio-keys`
buttons). Verified beyond the exit code: the built DTB's `pci@0,0` node
resolves `reset-gpios` to a real phandle reference (`<0x1c 0xb3 0x01>` --
`0xb3` = 179 decimal, the confirmed OIPG PERST pin), `System.map` has
`apple_t7000_pcie_probe`/`apple_t7000_pcie_init` plus confirmation that
`pci_host_common_parse_ports` and `gpiod_direction_output` are genuinely
linked in (not dead-code-eliminated), and the built `Image` contains
every diagnostic string from both branches of the PERST-deassert helper
(the success path and the "no PERST# GPIO found" fallback), confirming
the corrected logic is genuinely compiled in intact. `result` now points
to this payload.

**Hardware result: clean, 2026-09-25.** postmarketOS booted normally,
USB networking up (0% ping loss), debug shell reachable. `dmesg`
confirms the corrected PERST-handling code genuinely executed, not just
compiled:

```
[    0.128072] pcie-apple-t7000 610000000.pcie: t7000-pcie enable-enum-perst-test: deasserting PERST#
[    0.231319] pcie-apple-t7000 610000000.pcie: t7000-pcie enable-enum-perst-test: init complete, handing back to generic ECAM core
```

The ~103ms gap between these two lines is strong direct evidence the
deassertion path genuinely ran, not just logged: it matches the
`msleep(PCIE_RESET_CONFIG_WAIT_MS)` (100ms) call immediately after
`gpiod_direction_output()` almost exactly. The "no PERST# GPIO found,
nothing to deassert" fallback message did **not** appear, confirming
`pci_host_common_parse_ports()` genuinely discovered the `pci@0,0`
node's `reset-gpios` property and `gpiod_direction_output()` was
actually called on a real descriptor -- this is the first hardware
confirmation that the corrected Stage 3 design (the fix for the
disproven "automatic PERST deassertion" assumption) is not just
theoretically right but actually works end to end on this hardware.

Generic PCI enumeration proceeded exactly as in Stage 2 -- same root
port self-identification (`[106b:1002]` type 01, class `0x060400`),
same bridge reconfiguration onto bus 01, same benign `no iommu-map
translation for id 0x8` line, still **no downstream device found**.
This is the expected result, not a failure: Apple's own recovered order
has PERST deassertion as the second-to-last step, with the per-port
controller window's own link-start bit write (Stage 4b) still needed
before the link can actually train. No other new dmesg errors. **Stage
3's hardware gate is closed -- proceed to Stage 4a.** Full patch:
`kernel/patches/0035-pcie-apple-t7000-enable-enumeration-perst-test.patch`.

### Real PCIe host-controller driver, Stage 4a: bounded per-port controller window read (no write yet), 2026-09-25

Apple's recovered order finishes with one more step this project hasn't
implemented yet: after PERST is deasserted, set bit 0 of the *per-port
controller window's* own config register at offset `0x80` to start the
actual link attempt (`docs/plans/2026-09-13-j81-wifi-pcie.md`'s
"Enable-sequence checkpoint", step 5). That per-port window (ADT reg
index `2 * port + 1` = 3 for port 1, physical address `0x602004000`) has
never been touched by any test in this investigation -- every prior
register access (`0019`-`0035`) was either the shared window (reg index
9) or the ECAM/config-space window (reg index 0), both independently
proven safe to read *and* write across many rounds before any write was
attempted on them (`0020`/`0024` read the shared window repeatedly
before `0027`/`0028` ever wrote to the DART; `0021`/`0022` read ECAM
before `0023`/`0018` ever ran a full bus scan). Rather than write to the
per-port window on the very first touch, this stage applies that same
discipline: it adds exactly one new variable, a single bounded, logged
read of that window (offsets `0x00` and `0x80`), still no write. The
actual link-start write is deliberately deferred to a later stage (4b),
gated on this read succeeding cleanly.

**ADT index derivation double-checked before committing to it.** The
existing plan doc's own register-window table (see
"Window-role checkpoint" above) labels ADT entries by the literal
address digit -- entry 3 (`0x602004000`) is called "port 2" there, since
"2" appears in the address. This looks like it could contradict using
index 3 for "port 1," but it's a different, purely descriptive labeling
convention from Apple's own 0-indexed `port` C variable, which this
driver already uses consistently for the shared-window stride
(`base + port * 0x80`) -- and the shared window's `port = 1` stride
block was already hardware-confirmed populated by `0024`'s real
non-trivial register readback. `AppleEmbeddedPCIEPort` maps
controller-window resource `2 * port + 1` using that same variable, so
`port = 1` (the confirmed populated port) maps to ADT index 3, matching
what every implementation note in this project has already stated. No
correction was needed here, but resolving the apparent conflict
explicitly (rather than leaving it as a coincidence) is itself part of
why this stage reads before writing: a plausible register value at
offset `0x80` is further evidence the index is right, and an obvious
fault would be a reason to re-derive it.

Verified byte-exact via the established reconstruct/diff/verify
methodology.

**Cross-build verified clean, 2026-09-25**: `nix build
.#packages.x86_64-linux.m1n1-hoolock-pcie-port-controller-window-read-test
--no-link -L` exits 0 -- complete real payload, only the same benign
pre-existing `dtc` warning class. Verified beyond the exit code:
`System.map` confirms `pci_host_common_parse_ports`/
`gpiod_direction_output` are genuinely linked in, and the built `Image`
contains every diagnostic string including the new
`"port %d controller window: 0x00=0x%08x 0x80=0x%08x"` format string --
confirming the bounded-read logic is genuinely compiled in, not just
patched into a file that got dropped. `result` now points to this
payload.

**Hardware result: a real, informative, non-fatal failure --
`-EBUSY`, not a hang, 2026-09-25.** postmarketOS booted normally, USB
networking up, debug shell reachable throughout (initial worry that the
probe had hung was wrong -- a first `dmesg` grep targeted only this
driver's own `t7000-pcie ...-test:` log prefix and missed the actual
failure, which used the device's own `pcie-apple-t7000 <addr>.pcie:`
prefix via `dev_err_probe()`). The real log:

```
[    0.129657] pcie-apple-t7000 610000000.pcie: t7000-pcie enable-enum-perst-portread-test: deasserting PERST#
[    0.231328] pcie-apple-t7000 610000000.pcie: error -EBUSY: can't request region for resource [mem 0x602004000-0x602004fff]
[    0.231417] pcie-apple-t7000 610000000.pcie: error -EBUSY: failed to map port 1 controller window
[    0.231456] pcie-apple-t7000 610000000.pcie: probe with driver pcie-apple-t7000 failed with error -16
```

The ~103ms gap before the `-EBUSY` confirms the PERST deassertion and
its settle delay both completed normally (consistent with Stage 3's
already-confirmed timing) -- the failure is specifically in mapping the
per-port controller window itself, and it's a real diagnosis, not a
mystery: `0x602004000` (this window's base) falls *inside*
`dart_apcie1`'s own MMIO region (base `0x602002000`, size `0x200000`/2
MiB -- covers up to `0x602202000`). The real, already-hardware-proven
`apple-dart` driver exclusively claims that whole 2 MiB span on its own
probe (`0031`), so `devm_ioremap_resource()`'s exclusive
`devm_request_mem_region()` step correctly refuses to let this driver
claim an overlapping sub-region. This is a genuine physical address
overlap between two ADT nodes' declared `reg` windows in Apple's own
SoC layout, not a bug in the recovered ADT-index derivation -- the
index (`2*port+1 = 3` for port 1) is still believed correct; the
problem is purely how Linux's resource-reservation model handles two
drivers legitimately needing access to overlapping physical ranges.

No other new dmesg errors; the rest of the boot proceeded completely
normally after the clean probe failure.

**Fix implemented and cross-build verified as `0038` (Stage 4a v2)**:
uses a non-exclusive `devm_ioremap()` for just this one window instead
of `devm_ioremap_resource()`, skipping the exclusive reservation --
safe since the goal is only to read the window for diagnostic evidence,
not to exclusively own it. The shared window (reg index 9, no known
overlap) is unaffected, still mapped exclusively as before. `0036`
itself is kept as the historical record of this finding, not amended in
place, matching this project's convention for patches that reached
hardware and produced a real result.

Verified byte-exact via reconstruct/diff/verify.

**Cross-build verified clean, 2026-09-25**: exit 0, complete payload,
only the same benign `dtc` warning class. Verified beyond the exit
code: `System.map` confirms `apple_t7000_pcie_probe`/
`apple_t7000_pcie_init` are present (the new
`apple_t7000_pcie_map_window_shared()` helper itself is small and
single-call-site, so it inlines like every other small static helper
in this driver family -- confirmed indirectly instead via the built
`Image` containing every diagnostic string including the success-path
`"port %d controller window: 0x00=0x%08x 0x80=0x%08x"` format string,
meaning the corrected mapping path genuinely compiles through to the
read). Available as
`m1n1-hoolock-pcie-port-controller-window-read-test-v2`.

**Hardware result: clean, 2026-09-25 -- the fix works.** postmarketOS
booted normally, USB networking up (0% ping loss), debug shell
reachable. `dmesg` (checked against both the driver's own log prefix
and the device's `pcie-apple-t7000` prefix this time, per the lesson
from the first attempt):

```
[    0.126057] pcie-apple-t7000 610000000.pcie: t7000-pcie portread-test-v2: deasserting PERST#
[    0.231338] pcie-apple-t7000 610000000.pcie: t7000-pcie portread-test-v2: port 1 controller window: 0x00=0x00000000 0x80=0x00000000
[    0.231375] pcie-apple-t7000 610000000.pcie: t7000-pcie portread-test-v2: init complete, handing back to generic ECAM core (no link-start write this stage)
```

The per-port controller window read succeeded cleanly for the first
time -- no `-EBUSY`, no probe failure, `probe()` returned 0. Both
offsets read `0x00000000`. This is a plausible, non-fault "at rest"
value, not evidence of a floating/unmapped bus: offset `0x80` bit 0 is
exactly the link-start bit Stage 4b will set, and reading it as
currently-clear is the expected state for a port that has never had
that bit written -- real hardware state, not garbage. Generic bus
enumeration then proceeded normally as in every prior stage. No new
dmesg errors anywhere. **This closes Stage 4a's hardware gate for
real** (the `0036`/`-EBUSY` round is now fully superseded, not just
theoretically fixed).

**Before proceeding to Stage 4b: `0037` has the identical bug.** It was
built before this fix existed and calls the same exclusive
`apple_t7000_pcie_map_window()` (`devm_ioremap_resource()`) for the
per-port controller window in its own link-start-write path -- it would
hit the exact same `-EBUSY` if tested as-is. A Stage 4b v2 with the same
non-exclusive-mapping fix is needed before this stage can be tested;
`0037` stays as a historical record like `0036`.

**`0039` (Stage 4b v2) implemented, verified byte-exact, and
cross-build verified clean, 2026-09-25.** Exit 0, complete payload,
only the same benign `dtc` warning class. Verified beyond the exit
code: `System.map` confirms `apple_t7000_pcie_probe`/
`apple_t7000_pcie_init` plus `pci_host_common_parse_ports`/
`gpiod_direction_output` are genuinely linked in, and the built `Image`
contains every diagnostic string including both the before/after
controller-window log lines for the actual link-start write. Available
as `m1n1-hoolock-pcie-link-start-write-test-v2`.

**Hardware result: clean boot, the write genuinely takes, but no
downstream device enumerates yet, 2026-09-25.** postmarketOS booted
normally, USB networking up (0% ping loss), debug shell reachable.
`dmesg` (checked against both log prefixes):

```
[    0.231344] pcie-apple-t7000 610000000.pcie: t7000-pcie link-start-test-v2: port 1 controller window before: 0x00=0x00000000 0x80=0x00000000
[    0.231381] pcie-apple-t7000 610000000.pcie: t7000-pcie link-start-test-v2: port 1 controller window after: 0x00=0x00000000 0x80=0x00000001
[    0.231413] pcie-apple-t7000 610000000.pcie: t7000-pcie link-start-test-v2: init complete, handing back to generic ECAM core for bus enumeration
```

**The write genuinely took and stuck**: offset `0x80` bit 0 read back
as `1` after the write, not reverted or pulsed away -- unlike the
shared window's LTSSM register in every earlier stage, which read back
`0` even after being written `3` twice. This is real, direct evidence
the per-port controller window is not just readable (confirmed by Stage
4a v2) but genuinely writable, and that this specific bit is a real,
persistent control bit, not a self-clearing command/pulse register.

**No crash, no hang, anywhere across the entire now-complete staged
sequence** (Stage 1 through this final write) -- this closes out
definitively whether writing to real, previously-untouched PCIe
hardware registers is safe to attempt at all on this SoC, following
this project's own read-before-write discipline at every step.

Generic bus enumeration then proceeded exactly as in every prior stage
-- the root port self-identified (`[106b:1002]`, bridge to bus 01) --
but **no downstream device (the BCM4350 WiFi endpoint) was found**,
even after: the initial boot-time scan, a manual `echo 1 >
/sys/bus/pci/rescan` immediately after boot, and a second rescan after
an additional ~5 second wait. `/proc/iomem` confirms all the expected
windows (shared, ECAM, both `ranges` apertures) are correctly
registered. `setpci` was not available in this minimal debug shell to
probe bus 1 config space directly.

**One genuinely ambiguous data point, reported precisely rather than
over-interpreted**: the root port's own kernel-decoded link status
(`/sys/bus/pci/devices/0000:00:01.0/current_link_speed` /
`current_link_width`) reports `2.5 GT/s PCIe` / width `1` -- non-zero,
not the all-zero/absent values a genuinely down link might be expected
to show. This is *not* being treated as proof the physical link
trained: it's unclear without further investigation whether these
sysfs values reflect a real, active downstream link, a default/reset
state the Link Status register happens to report regardless of link
state, or something specific to this SoC's root complex that doesn't
require a downstream device to report non-zero. Recorded as raw
evidence for a future pass, not a conclusion either way.

**Interpretation, not yet confirmed**: Apple's own recovered
`enableGated` order includes several steps this staged implementation
has deliberately excluded throughout
(`docs/plans/2026-09-13-j81-wifi-pcie.md`'s "Enable-sequence
checkpoint", steps 2-4) -- capability discovery, applying
`apcie-config-tunables`/`dbi-overrides` through the per-port window,
and config+MSI programming. It's plausible one or more of these, not
yet ported to Linux anywhere in this project, are genuinely required
before the endpoint will respond to config-space reads, not merely
cosmetic. This is a well-motivated next research direction, not a dead
end -- the core staged approach (enable sequence, PERST, and now the
link-start write) is fully confirmed safe and working exactly as
recovered; what's left is whichever additional step(s) make the
endpoint actually answer.

**Full staged sequence (Stages 1-4b v2) is complete and
hardware-verified safe end to end.** `result` points to this payload.
Next step is research, not a blind retry: identify which of the
excluded steps (if any) the endpoint genuinely needs, or design a
link-training-completion poll (a genuine Stage 4c) if timing alone
turns out to be the gap.

### What the no-endpoint result rules out, and the next bounded experiment, 2026-09-25

The clean Stage 4b result is progress, but it does **not** show that the
physical link trained. It does establish three facts that constrain the next
step:

1. The current Linux test path already includes a conservative 100 ms wait
   after PERST# deassertion before the first configuration-space access.
2. A second, manual bus rescan about five seconds later still found no
   BCM4350. A longer wait before another otherwise identical scan is therefore
   unlikely to be the missing action. A link-status poll may still be useful
   as a diagnostic, but is not a credible standalone fix.
3. The captured J81 ADT provides the exact controller records Apple selects;
   no values need be guessed or borrowed from another SoC:

   | ADT property | Offset | Clear mask | Set value |
   | --- | ---: | ---: | ---: |
   | `apcie-config-tunables` | `0x090` | `0x000000ff` | `0x00000028` |
   | | `0x130` | `0x00000003` | `0x00000003` |
   | | `0x134` | `0x00000001` | `0x00000001` |
   | `dbi-overrides` | `0x024` | `0x00000001` | `0x00000001` |
   | | `0x07c` | `0x00000400` | `0x00000000` |
   | | `0xb44` | `0x00000003` | `0x00000002` |

Each record is a little-endian `(offset, clear-mask, set-value)` triple; the
recovered Apple helper implements `new = (old & ~clear-mask) | set-value`.
The original claim that both lists use the port-controller window, with a
direct DBI gate at port-window offset `0x0bc`, is corrected below: only the
`apcie-config-tunables` list uses that direct window. `dbi-overrides` uses
Apple's separate configuration accessor.

**Stage 5A — baseline only.** Build a payload from the Stage 4b-v2 branch
that performs no new write. After the existing link-start readback, log the
seven 32-bit values at `0x024`, `0x07c`, `0x090`, `0x0bc`, `0x130`, `0x134`,
and `0xb44` from the same non-exclusive port-1 mapping. Retain the ordinary
generic enumeration and USB-network shell. This confirms every prospective
offset is live on J81 and preserves a before-state for the later RMW results.
It deliberately does not claim link status or attempt a fourth blind rescan.

**Stage 5B — exact Apple records, after the remaining trace check.** Recover
from the pinned Apple driver whether `dbi-overrides` precede or follow
`apcie-config-tunables`, whether either set is conditional on a discovered
capability, and the DBI-enable bit semantics. Only then add the minimum
RMW helper, with the DBI access kept separate from the already-working
port-window helper. Do not add MSI or firmware work to this experiment: MSI
cannot make an endpoint answer the first configuration read, and firmware
cannot load before enumeration.

This makes the next hardware run evidence-producing in either outcome. If
Stage 5A faults or shows implausible data, stop at the mapping/ownership
question. If Stage 5B remains endpoint-free, the remaining Apple capability
and root-config programming become the isolated next target rather than an
unbounded collection of PCIe writes.

### Stage 5A implemented, verified byte-exact, and cross-build verified, 2026-09-25

`0040` implements the plan above exactly: layered on `0016` (a clean
branch, not stacked on `0033`-`0039`), it runs the full recovered
enable sequence through the link-start write (unchanged from Stage 4b
v2, same non-exclusive per-port-window mapping already hardware-
confirmed by `0038`/`0039`), then adds one read-only baseline capture
of the seven offsets (`0x024`, `0x07c`, `0x090`, `0x0bc`, `0x130`,
`0x134`, `0xb44`) within that same already-mapped window -- no new
writes. Reuses the exact ADT-recovered offsets from the table above;
no values guessed or borrowed from another SoC.

Verified byte-exact via the established reconstruct/diff/verify
methodology.

**Cross-build verified clean, 2026-09-25**: exit 0, complete payload,
only the same benign `dtc` warning class. Verified beyond the exit
code: `System.map` confirms `apple_t7000_pcie_probe`/
`apple_t7000_pcie_init`, and the built `Image` contains the new
tuning-baseline format string with all seven offsets
(`"port %d tuning baseline: 0x024=... 0x07c=... 0x090=... 0x0bc=...
0x130=... 0x134=... 0xb44=..."`), confirming the baseline-capture code
genuinely compiled in. Available as
`m1n1-hoolock-pcie-tuning-baseline-test`.

**Hardware result: clean, all seven direct port-window offsets read real, plausible
values, 2026-09-25.** postmarketOS booted normally, USB networking up
(0% ping loss), debug shell reachable. `dmesg`:

```
[    0.231528] pcie-apple-t7000 610000000.pcie: t7000-pcie tuning-baseline-test: port 1 tuning baseline: 0x024=0x00000000 0x07c=0x00000000 0x090=0x00000004 0x0bc=0x00000000 0x130=0x00000004 0x134=0x00000000 0xb44=0x00000000
```

No fault, no implausible/garbage pattern (no `0xffffffff`, nothing
suggesting a floating bus), no new dmesg errors. Two offsets are
non-zero at rest (`0x090=0x00000004`, `0x130=0x00000004`); the rest
read `0x00000000`. The then-current interpretation of port-window `0x0bc`
as the DBI gate is corrected in the next section: this experiment did **not**
read the DBI control through Apple's configuration-access path.

**Applying Apple's recovered `(offset, clear-mask, set-value)` records
to this real baseline, for reference (not yet written) -- corrected
below**: only the three `apcie-config-tunables` rows apply directly to
these baseline reads. The independent Stage 5B verification pass (next
section) found that each `dbi-overrides` record's own "offset" field is
**not** a flat register offset in this window at all -- it decomposes
into a controller-level selector nibble and a separate low byte offset,
reached through a completely different access mechanism (see below).
Stage 5A's baseline reads at raw offsets `0x024`/`0x07c`/`0xb44` were
therefore not reading the same physical registers Apple's DBI mechanism
targets; the deltas originally listed for those three rows are not
meaningful and have been removed.

| Offset | Baseline | Clear mask | Set value | Predicted after |
| ---: | ---: | ---: | ---: | ---: |
| `0x090` | `0x00000004` | `0x000000ff` | `0x00000028` | `0x00000028` |
| `0x130` | `0x00000004` | `0x00000003` | `0x00000003` | `0x00000007` |
| `0x134` | `0x00000000` | `0x00000001` | `0x00000001` | `0x00000001` |

Every tunables record produces a plausible, small, well-formed delta
from this real baseline -- nothing suggesting the offsets or records
are wrong. **This closes Stage 5A's hardware gate for the three
tunables offsets.** The three `dbi-overrides` offsets (`0x024`, `0x07c`,
`0xb44`) were read at this stage, and the values were real and
non-faulting, but do not represent Apple's actual DBI target registers
-- see the next section for what does.

Full patch: `kernel/patches/0040-pcie-apple-t7000-tuning-baseline-test.patch`.

### Stage 5B offline trace: ordering, conditions, and DBI access resolved, 2026-09-25

Re-extracted the exact pinned iPad5,3 iOS 8.1 (`12B410`) kernelcache and
verified SHA-256 `19c277d60e0a1185b1e4a1b72cda4f1f550c0b0bf670791542234a6dbbcc28bf`.
Focused Ghidra decompilation of `AppleEmbeddedPCIEPort::init()` and
`enableGated()` resolves the outstanding Stage 5B questions:

1. Port initialization retains `dbi-overrides` from the controller first and
   then from the port, if either property exists. J81 has the three-record
   controller list and no port-local list. It retains
   `apcie-config-tunables` from the controller independently.
2. During enable, a present maximum-link-speed property is handled first.
   Apple then applies controller DBI overrides, then optional port DBI
   overrides, and finally applies controller tunables. The record lists are
   conditional only on their property's presence, not on discovered endpoint
   capabilities. J81 supplies both required controller properties.
3. The DBI helper reads a saved control value through the parent controller's
   configuration accessor with selector bit `0x08000000` and low offset
   `0x0bc`, writes `saved | 1`, applies every `(offset, clear-mask,
   set-value)` record, then restores the saved control value exactly. The
   high selector is part of the accessor address; it is **not** a direct
   `port_window + 0x0bc` operation.
4. Tunables use the already-proven direct per-port controller mapping and the
   same RMW formula, after the DBI lists. Apple does not toggle the DBI gate
   around these tunable writes.

This also explains an initially plausible but incorrect inference from Stage
5A. The standard DesignWare definition places its DBI read-only-write control
at `0x8bc`, bit 0; Apple's selector-plus-`0x0bc` configuration transaction is
consistent with that DBI access model, but not yet proven to have the same
physical address calculation under Linux. Stage 5A's direct
`port_window + 0x0bc` read neither proves nor disproves the DBI gate state.

**Correction, independently verified below**: only the three
`apcie-config-tunables` baselines (`0x090`/`0x130`/`0x134`) remain valid
-- they go through the direct per-port window, confirmed unchanged. The
three `dbi-overrides` baselines (`0x024`/`0x07c`/`0xb44`) do **not**
represent Apple's real DBI targets; see below for why.

**Revised implementation gate.** Do not write the six records yet. First
derive and cross-build a read-only configuration-view probe matching Apple's
selector (`port-1 configuration address | 0x08000000`, low offset `0x0bc`).
It must log the saved DBI control value and make no write. That confirms the
Linux ECAM calculation reaches the same view before Stage 5B writes
`saved | 1`, applies the three DBI records, restores the saved value, and
then applies the three direct tunables in Apple's confirmed order. This is
now an implementation-mapping gate, not a reverse-engineering-order gate.

### Independent verification of the Stage 5B trace, and one refinement, 2026-09-25

Re-traced the same functions fresh (not by reading the notes above) using
the same pinned kernelcache and the Ghidra project already set up this
session, to cross-check before anything gets written to real DBI
registers. Confirmed, precisely:

- **Ordering.** `FUN_ffffff8002bee6cc` (`enableGated`) calls
  `FUN_ffffff8002bef8d8` (checks the port object's cached controller
  `dbi-overrides` pointer at offset `0x1c0`, then its cached port-level
  `dbi-overrides` pointer at `0x1c8`, calling the same apply-function
  `FUN_ffffff8002bf07d8` for each if present) strictly before the
  `apcie-config-tunables` check at offset `0x1d0`
  (`FUN_ffffff8002bf09a0` if non-null). Matches claim 2 exactly.
- **Tunables mechanism.** `FUN_ffffff8002bf09a0` (the tunables applier)
  reads/writes through `FUN_ffffff8002befd78`/`FUN_ffffff8002bef92c`,
  which are literally `*(u32 *)(ctrl_base + offset)` on the port
  object's own direct MMIO mapping (`param_1 + 0xd0`, the same virtual
  address our driver's `readl`/`writel` on the per-port window use).
  Confirms tunables need no new access primitive.
- **DBI gate mechanism.** `FUN_ffffff8002bf07d8` (the DBI applier)
  never touches the direct MMIO mapping at all. It calls two vtable
  methods (slots `0x5e0` = read, `0x5e8` = write) on the *controller*
  object (`*(long **)(param_1 + 0xa0)`, not the port), with the gate
  access at `selector = (port_selector_base & 0xf0ffffff) | 0x08000000`,
  low offset `0xbc` -- matches claim 3's selector bit and low offset
  exactly.
- **New refinement claim 3 didn't spell out**: each `dbi-overrides`
  record's own "offset" field, inside the same apply loop, is *not* a
  flat register offset -- it decomposes into a selector-nibble
  (`(record_offset & 0xf00) << 16`, OR'd into the *record* selector,
  which does **not** include the gate's `0x08000000` bit -- a different
  selector composition than the gate access) and a low byte offset
  (`record_offset & 0xff`). For J81's three records: `0x024` -> nibble
  `0`, low `0x24`; `0x07c` -> nibble `0`, low `0x7c`; `0xb44` -> nibble
  `0xb000000`, low `0x44`. None of these three raw offsets are ever used
  as a direct MMIO offset anywhere in Apple's own driver -- confirming
  Stage 5A's `0x024`/`0x07c`/`0xb44` baseline reads, while real and
  non-faulting, were reading unrelated registers, not the DBI targets.
- **Cross-checked against the real J81 ADT capture directly**
  (`artifacts/adt/20260908T082112Z-j81.adt`, private, git-ignored): the
  populated port's own `apcie-port` property is `0x00000001`, matching
  this driver's `T7000_PCIE_TEST_PORT` exactly (one open question this
  investigation hadn't explicitly closed before). The raw
  `dbi-overrides`/`apcie-config-tunables` byte arrays decode to exactly
  the six records already documented above -- independently re-derived
  from the raw hex, not just re-read from the prior write-up.

**Vtable slots `0x5e0`/`0x5e8` resolved, 2026-09-25**: found real debug
strings `configRead32`/`configWrite32`/`configRead16`/`configWrite16`/
`configRead8`/`configWrite8` in the kext and traced their cross-references
-- `configRead32` referenced only from `FUN_ffffff8002bece24`,
`configWrite32` only from `FUN_ffffff8002becef0`. Decompiled both in
full; they are genuinely the vtable-slot implementations (matching
calling convention `(controller, selector, low_offset[, value])` exactly)
and reveal the real address formula:

```
addr_offset = (selector >> 0x10 & 0xf00) | low_offset
            | ((selector << 4) & 0x7000)
            | ((selector << 4) & 0xf8000)
            | ((selector << 4) & 0xff00000)
value = *(u32 *)(*(controller + 0xb0) + addr_offset)     // read
*(u32 *)(*(controller + 0xb0) + addr_offset) = value     // write
```

This is a classic ECAM-style bitfield composition (`bus<<20 | dev<<15 |
func<<12 | reg`, `selector`'s shifted bits supplying bus/dev/func,
`low_offset` supplying the low config-register bits) accessed through
`*(controller + 0xb0)` -- a **separate MMIO base from the direct
per-port window at `+0xd0`** that `apcie-config-tunables` uses. In other
words: DBI overrides are genuinely an ECAM-relative config-space
access through the controller's own config window, not a register in
the per-port controller window at all -- confirming the "ECAM-view
probe" framing directly. Both functions also conditionally call
`FUN_ffffff8002becd88` (the previously-identified "unlock" dispatcher)
around the access, gated on the return value of a small helper
(`FUN_ffffff8002becc84`) -- not yet decomposed, but structurally an
optional unlock/relock wrapping the raw access, consistent with
`_unlockConfigSpace`'s earlier-identified role as an adjacent mechanism
rather than the primitive itself.

**The final mapping gap is closed, 2026-09-25.** The parent controller's
initialization maps its provider resource index `0` and stores that virtual
base at `controller+0xb0`. J81's captured `apcie` ADT resource index `0` is
exactly the `0x610000000`, `0x01000000` ECAM region that Linux already maps
as `cfg->win` for generic enumeration. It is not a second, unrepresented
window.

The child `apcie-port = 1` produces Apple’s `port_selector_base = 1 << 11 =
0x00000800`. The DBI control selector is therefore `0x08000800`; applying
the recovered `configRead32` formula with low offset `0x0bc` gives **ECAM
offset `0x000088bc`**. The three DBI records similarly resolve to
`0x8024`, `0x807c`, and `0x8b44`. These are all inside the same already
hardware-proven 16 MiB ECAM mapping.

`kernel/patches/0041-pcie-apple-t7000-dbi-ecam-read-test.patch` implements
the resulting Stage 5B mapping gate. It reuses `cfg->win`, logs the selected
port-1 DBI control at `ECAM+0x88bc`, and makes **no new write**. In
particular, it does not set the DBI gate, apply a DBI override, restore a
gate value, or apply a tunable. Its expected marker begins
`dbi-ecam-read-test: port 1 selector=0x08000800 ecam+0x088bc`. A clean
hardware observation of that marker and its `dbi_control=...` value is the only
remaining gate before a separately reviewed Stage 5B write implementation.

**Independently re-verified before hardware, 2026-09-25.** Decompiled the
port-init function (`FUN_ffffff8002bed5bc`) directly: it sets offset `0x1b4`
via `(*(param_1+0xa8) & 0x1f) << 0xb`, where `param_1+0xa8` is loaded
straight from the ADT `apcie-port` property -- confirms `port_selector_base
= 1<<11 = 0x800` for port 1 exactly as derived above, independent of the
committed writeup. Re-ran the `configRead32` address formula by hand with
`selector=0x08000800`, `low_offset=0xbc` and got `0x88bc`, matching.

**Stage 5B hardware result: clean, marker observed exactly as predicted,
2026-09-25.** postmarketOS booted normally, USB networking up (0% ping
loss after a boot-recipe fix below), debug shell reachable. `dmesg`:
`t7000-pcie dbi-ecam-read-test: port 1 selector=0x08000800 ecam+0x088bc
dbi_control=0x00000000` -- no fault, boot continued straight through
generic PCI enumeration (root port self-ID unchanged from every prior
stage) and userspace init, no new dmesg errors beyond the same
pre-existing benign lines seen on every clean boot this project has had
(`g_multi` probe failure, `iommu-map` translation notice, PMIC `Bad cell
count`). `dbi_control` reading `0x00000000` at rest is a plausible
baseline: Apple's own DBI applier does `saved = read(gate); write(gate,
saved|1); ...; write(gate, saved)`, so an untouched `0` is exactly what
"never yet touched" should look like. **Stage 5B's read-only hardware
gate is closed.** Next, not yet built: the actual gated RMW -- set the
gate (`saved|1`), apply the three DBI override records at ECAM offsets
`0x8024`/`0x807c`/`0x8b44` using the confirmed selector/offset
decomposition, restore the gate to `saved` -- likely followed by
`apcie-config-tunables` at the already-hardware-proven direct-window
offsets, matching Apple's own confirmed ordering (DBI first, then
tunables).

**Boot-recipe bug found and fixed along the way, 2026-09-25**: the
checked-in `boot/Pongo.bin` was the original pre-m1n1 PongoOS 2.6.1
build (unchanged since project start) and has no `bootm` command at
all -- only `bootl`/`bootr`/`bootux`/`bootx`. Every documented
`--override-pongo "$PWD/boot/Pongo.bin"` recipe in this project's docs
points at that exact stale file, so `boot/load_m1n1.py`'s `bootm`
request silently no-opped three times in a row (`Bad command: bootm` on
PongoOS's own console -- invisible to the script's own success check,
which only verifies the USB transfer itself didn't error). Fixed by
overwriting `boot/Pongo.bin` in place with a current flake payload's own
bundled `Pongo.bin` (every `m1n1-hoolock-*` payload bundles an identical
one, real `bootm` support confirmed via `strings`: `boots m1n1`) --
see `docs/project-status.md`'s "`boot/Pongo.bin` replaced with an
m1n1-aware build" section for the full writeup. No script depends on
this file's exact bytes, so the fix needed no path changes.

### Real PCIe host-controller driver, Stage 4b: per-port link-start write, built ahead of Stage 4a's hardware gate, 2026-09-25

The final piece of Apple's recovered order: after PERST# is deasserted,
set bit 0 of the per-port controller window's own config register at
offset `0x80` to start the actual link attempt
(`docs/plans/2026-09-13-j81-wifi-pcie.md`'s "Enable-sequence checkpoint",
step 5). `0037` implements exactly this on top of Stage 4a, unchanged
otherwise.

**Built and staged ahead of Stage 4a's own hardware result** -- as of
this patch's implementation, `0036`'s bounded read of the per-port
window (never touched by any earlier test) has not yet been
hardware-tested. This follows this project's own established precedent
for building a next stage before its own gate clears (`0025`/`0026`,
`0029`/`0030` were built and staged ahead of their respective earlier
stages' hardware results too) -- but it means **this specific payload
must not be tested on hardware before Stage 4a's read comes back
clean**. Writing to a register window before confirming it's safe to
read would repeat exactly the mistake this investigation has
deliberately avoided at every other register region by always reading
before writing. The driver's own header comment states this explicitly,
as does the DTS comment and the Nix package description, so the
constraint travels with the artifact itself, not just this doc.

One additional open question flagged rather than resolved: after the
link-start write, the generic `pci_host_probe()` bus scan runs
immediately once `.init()` returns, and may issue its first
config-space read before the physical link has actually finished
training. Apple's own recovered call trace has no documented delay or
poll loop between the bit-0 write and the next config access at this
point, and none is invented here. If the endpoint still doesn't
enumerate on this stage even after Stage 4a's read comes back clean, a
link-training-completion poll (a genuine Stage 4c, not yet designed)
would be the next evidence-gated step -- not a blind retry.

Verified byte-exact via the established reconstruct/diff/verify
methodology.

**Cross-build verified clean, 2026-09-25, after a real Nix store
corruption detour.** The first two attempts failed with `gzip:
.../Image: No such file or directory` -- not a code problem. The
Linux-builder VM's GC (run by the operator to clear disk space from
earlier in this session) raced with an in-flight build: the kernel
derivation finished compiling and was registered valid, but GC deleted
its `Image` file before the payload-assembly step could read it back --
a gap in Nix's temp-root protection during that handoff. Worse, the
corrupted (registered-valid-but-incomplete) store path existed on
**both** the local Mac and the remote builder, and each side kept
re-populating the other with the same broken bits on retry until both
were cleared in the right order (remote first, confirmed by real
`nix-store --delete` output showing paths actually removed, then
local). Once both were genuinely clean, the retry did a real recompile
and succeeded: exit 0, complete payload, only the same benign `dtc`
warning class. Verified beyond the exit code: the kernel's `Image` file
is genuinely present (18 MB, not missing/empty), `System.map` confirms
`apple_t7000_pcie_probe`/`apple_t7000_pcie_init` plus
`pci_host_common_parse_ports`/`gpiod_direction_output` are linked in,
and the built `Image` contains every diagnostic string including the
new per-port controller window before/after log lines around the
link-start write.

**Reminder for future sessions**: if a Nix build fails with a file
genuinely missing from a store path that Nix otherwise treats as valid
(no rebuild attempted, or a rebuild that just re-copies the same broken
bits), suspect store corruption before suspecting the code -- especially
if GC ran on the builder recently. `nix-store --delete <path>
<path>-dev` (and any other referencing outputs the error names) on
*both* the local machine and the remote builder, in that order, is the
fix; a single-sided delete just gets re-corrupted from the still-broken
other side.

**Not yet hardware-tested -- and must not be, before Stage 4a's own
read comes back clean.** Full patch:
`kernel/patches/0037-pcie-apple-t7000-link-start-write-test.patch`.

## Infrastructure notes worth keeping

- **`gaster pwn` + raw `irecovery -f`/`-c go` does not reliably reach
  PongoOS on this Mac.** Documented as unreliable back in
  `docs/project-status.md`'s "Clean DFU relaunch attempt" (2026-09-03) and
  reproduced again this session. The proven route is the vendored
  `boot/vendor/palera1n-macos-arm64 --pongo-shell --override-pongo
  <Pongo.bin> --debug-logging`, requiring `sudo` (needs the operator's own
  terminal), with two physical Lightning replugs: once at `Checkmate!`/the
  download-mode prompt, once when the PongoOS logo actually appears on
  screen. Never replug again after that -- a replug after the `bootm`
  upload request killed a session that may otherwise have been fine.
- **The Linux-builder VM's disk can be corrupted by a hard-kill.** If its
  guest gets into a "vsock connect failed: Connection reset by peer" loop
  across multiple clean restarts, that's a real crash, not slow boot --
  more waiting doesn't fix it. Recreating `nixos.qcow2` from scratch (all
  VM state is gitignored, disposable build cache, not project work) does.
- **Each isolated PCIe test payload is layered directly on `0016`** (the
  inert compile-only skeleton), not on top of each other's patches --
  `0019` through `0023` are five independent, clean branches from the same
  base, each swapped in via its own `kernel/hoolock-pcie-*.nix` file and
  `flake.nix` output. This keeps every test's driver and DT change fully
  self-contained and lets any of them be rebuilt or reread independently.

### Real PCIe host-controller driver, Stage 5C: dbi-overrides/apcie-config-tunables RMW, 2026-09-25

Implements the actual gated write, per Apple's confirmed order: `dbi`
gate saved, set to `saved|1`, three `dbi-overrides` records applied
through the ECAM window at `0x8024`/`0x807c`/`0x8b44`, gate restored to
`saved` -- then three `apcie-config-tunables` records applied through
the already-mapped direct port-controller window at `0x090`/`0x130`/
`0x134`. All six `(offset, clear-mask, set-value)` triples are the exact
ADT-recovered values, no new guessing. `kernel/patches/0042-...`.
**Cross-build verified clean, 2026-09-25**: exit 0, checksums match,
`System.map` has `t7000_pcie_rmw`/`apple_t7000_pcie_probe` linked, built
`Image` contains all four new `dbi-write-test` log format strings.

**Hardware result: clean write, no crash, but still no downstream
endpoint, 2026-09-25.** postmarketOS booted normally, USB networking up.
`dmesg`:

```
dbi gate saved=0x00000000, setting saved|1
dbi-override 0x08024: 0x00000000 -> 0x00010001
dbi-override 0x0807c: 0x00733c12 -> 0x00733812
dbi-override 0x08b44: 0x000000d3 -> 0x000000d2
dbi gate restored to 0x00000000 (readback 0x00000000)
config-tunable 0x00090: 0x00000004 -> 0x00000028
config-tunable 0x00130: 0x00000004 -> 0x00000007
config-tunable 0x00134: 0x00000000 -> 0x00000001
```

Two of the three `dbi-overrides` records and all three `apcie-config-
tunables` records match the simple `(old & ~clear-mask) | set-value`
formula exactly (`0x807c`: bit 10 cleared as expected; `0x8b44`: low two
bits go from `0b11` to `0b10` as expected; all three tunables land
exactly on their predicted values). **One genuine anomaly**: `0x8024`'s
computed value should be `0x00000001` (clear-mask/set-value both `0x1`
against a `0` baseline), but the readback immediately after the write
shows `0x00010001` -- bit 16 set, which this driver never wrote. Since
the gate write/restore bracketing this record succeeded cleanly (`saved`
read back as `0x00000000` again afterward, unaffected), this isn't a
gate-timing artifact on our side; it looks like a real hardware-driven
status/side-effect bit at this specific ECAM offset, reacting to
something in the write sequence (most plausibly the gate being active
during this specific write, or a PCIe-core response triggered by
`0x8024` itself, which was `dbi-overrides`' own first raw ADT offset
`0x024` -- a plausible DesignWare-PCIe "port logic" link/PHY status
register). Not yet explained; worth revisiting with a targeted read-only
probe of `0x8024` alone if this stage's overall no-endpoint result isn't
resolved another way first.

Bus enumeration (boot-time and after a manual `echo 1 >
/sys/bus/pci/rescan` ~60s later) still found only the root port itself
(`00:01.0`, unchanged `106b:1002` self-ID) -- **no BCM4350 on bus 01**,
matching Stage 4b v2's own no-endpoint result exactly. No new dmesg
errors related to PCIe (one unrelated, likely-transient HDQ battery-gauge
read timeout appeared this boot -- a known-flaky protocol per
`research/j81-battery-hdq.md`'s own BAT-4 history, on a completely
separate bus with no relation to PCIe ECAM access).

**This is now the second stage (after Stage 4b v2) to confirm the write
side of this investigation is safe end-to-end while still not producing
enumeration.** Apple's `enableGated()` order recovered so far (DBI
overrides, tunables, then the link-start write already implemented in
Stage 4b) has now been fully reproduced on real hardware with no fault
-- meaning either: (a) a genuine link-training/settle delay is still
missing after these writes (no poll for link-up was attempted this
stage), (b) some other step in Apple's recovered order runs between
these writes and generic enumeration that this staged implementation
hasn't ported yet (MSI setup, a capability-conditional step, or a second
pass through `enableGated()`'s own dispatcher noted earlier -- it checks
*two* cached DBI-overrides pointers, `param_1+0x1c0` and `+0x1c8`,
calling the apply function up to twice), or (c) the `0x8024` anomaly
above is itself diagnostic of something not yet understood about this
register's real role. Next is investigating one of these leads with
static analysis or a targeted read-only probe, not a blind rescan retry.
