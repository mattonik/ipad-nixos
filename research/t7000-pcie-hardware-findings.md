# T7000 PCIe: hardware test findings, 2026-09-21 to 2026-09-23

Consolidated reference for every real hardware result from the J81 PCIe
host-controller investigation. The dated narrative (why each test was
designed the way it was, and the reasoning between rounds) lives in
[`docs/plans/2026-09-13-j81-wifi-pcie.md`](../docs/plans/2026-09-13-j81-wifi-pcie.md);
this file exists so the raw evidence -- what was actually run, and exactly
what came back -- is in one place rather than spread across six dated
sections.

## The conclusion, stated first

Seven real hardware boots, each changing exactly one variable versus the
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
are the one thing left untested. This matters because the pinned DART
driver programs MMIO at probe time, while Apple invokes
`function-dart_force_active` only *after* port hardware setup -- a real,
concrete reason DART activation could behave differently than expected if
probed on its own, standalone, with the wrong ordering relative to the
controller.

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

**This strongly implies** those two additional gates are walked
automatically by the underlying platform/PMGR power-state machinery as a
side effect of the same "enable my power state" call, not by explicit
per-gate driver code -- i.e. Apple's own `clock-gates` ADT array convention
is likely handled generically below this driver, not hand-rolled per gate.
**Practical implication for this project**: whether the existing Linux DT
`power-domains = <&ps_pcie>` genpd binding (already hardware-proven "clean"
by `0019`) also walks all three PMGR gates the same generic way is a real,
unverified assumption -- it should be checked against the actual
Apple-PMGR/genpd driver source in the pinned Hoolock kernel before treating
`0019`'s clean result as covering `PCIE_AUX`/`PCIE_REF` too, not just the
single `PCIE` gate.

### Practical takeaway for the next hardware test

A DART-only Linux test (`dart_apcie1` enabled, `pcie` left disabled, no
`iommu-map` consumer) is simpler to build than any of the PCIe test
payloads so far -- it just needs the DT status flip, no custom driver code
at all, since it only needs to exercise the stock Linux DART/IOMMU driver
already in the pinned kernel. But interpreting its result cleanly depends
on the two open points above: confirm (from the Hoolock kernel's own PMGR
driver source) whether enabling `ps_pcie` already implies all three gates,
and be explicit that this test says nothing about the
`_manualAvailabilityEnabled` question, which has no equivalent concept in
mainline Linux's IOMMU/DART driver model at all -- that gap is specific to
Apple's own closed-source "available on demand" DART design, not something
a Linux DART probe would need to replicate.

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
