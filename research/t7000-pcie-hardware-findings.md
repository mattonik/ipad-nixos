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
