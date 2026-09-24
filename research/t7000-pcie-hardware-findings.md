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
