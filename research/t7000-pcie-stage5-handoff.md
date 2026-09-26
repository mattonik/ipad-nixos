# T7000/J81 PCIe: research handoff, 2026-09-25

Purpose: a self-contained summary of the PCIe/WiFi bring-up investigation
for a fresh research pass (human or agent). It distills
`research/t7000-pcie-hardware-findings.md` (2,200+ lines, full
chronological history with every intermediate hardware test) down to
what's actually load-bearing right now. Read this first; use the full
history file only if you need the derivation trail behind a specific
claim below (each section says where to look).

## Goal

Get the BCM4350 WiFi chip (on PCIe port 1, the only populated port on
J81/iPad Air 2) to enumerate under Linux. Currently: the PCIe link
sequence is fully implemented and hardware-confirmed safe end-to-end
(enable, PERST, link-start write, DBI overrides, config tunables), but
the endpoint still never appears on the bus.

## Current status in one paragraph

The Linux implementation has hardware-confirmed that port-hardware enable,
generic ECAM host-bridge init, PERST# deassertion, the per-port link-start
write, DBI-overrides RMW, and `apcie-config-tunables` RMW are individually
tolerated. **It has not yet reproduced Apple's ordering or the remaining
port-controller programming immediately before and while the link trains.**
No downstream PCIe device has enumerated on bus 01 in any test.
The root port itself (`106b:1002`, Apple's own vendor ID) always
self-identifies correctly. This is the open problem.

## Hardware / boot chain (for reproducing any test yourself)

- Target: iPad Air 2 (A8X/T7001, iPad5,3, `j81ap`).
- Chain: checkm8 → `palera1n --pongo-shell --override-pongo <Pongo.bin>`
  → PongoOS → `boot/load_m1n1.py <payload>/m1n1-linux.bin` (sends a
  `bootm\n` command over a USB control transfer) → m1n1 → Linux
  (postmarketOS debug initramfs) → USB networking at `172.16.42.1`,
  telnet on port 23.
- **Known footgun, fixed 2026-09-25**: `boot/Pongo.bin` must be an
  m1n1-aware build (has a `bootm` command). It was stale for a long time
  (stock PongoOS, no `bootm` at all) and every documented recipe pointed
  at it, causing three consecutive silent boot failures before being
  caught. Now fixed in place (`docs/project-status.md`'s "`boot/Pongo.bin`
  replaced with an m1n1-aware build" section) -- if you rebuild the repo
  from an older checkout, verify `strings boot/Pongo.bin | grep bootm`
  finds something before assuming a hang means a code bug.
- Nix build: `nix build .#packages.x86_64-linux.m1n1-hoolock-<test-name>
  --no-link -L` from inside `ipad-nixos/` (never bare
  `nix run nixpkgs#darwin.linux-builder-vz`).
- Reading `dmesg` on the booted device:
  `(printf 'dmesg | tail -100\r\n'; sleep 5) | nc 172.16.42.1 23`

## The driver, as it exists today

`drivers/pci/controller/pcie-apple-t7000.c`, assembled via
`kernel/patches/0016` (inert skeleton) + `0040` (Stage 5A baseline reads)
+ `0041` (Stage 5B DBI gate read) + `0042` (Stage 5C DBI/tunables RMW).
Current full source is these four patches applied in order on top of
the pinned `HoolockLinux/linux` commit `6831bc701a6ce059e71e5aaa9488c9195bea6927`.
Nix wiring: `kernel/hoolock-pcie-dbi-tunables-write-test.nix`,
flake output `m1n1-hoolock-pcie-dbi-tunables-write-test`.

Register windows used (ADT `reg` indices on the `apcie`/`pcie@610000000`
node):

| Window | ADT reg index | Physical base | Size | Mapping |
| --- | --- | --- | --- | --- |
| Shared root-complex (per-port enable/PERST/LTSSM) | 9 | `0x600000000` | `0x2000` | exclusive `devm_ioremap_resource()` |
| ECAM / config space | 0 | `0x610000000` | `0x1000000` (16 MiB) | mapped by generic `pci_host_common_init()`, exposed as `cfg->win` |
| Per-port controller window, port 1 | `2*port+1` = 3 | `0x602004000` | `0x1000` | **non-exclusive** `devm_ioremap()` -- physically overlaps `dart_apcie1`'s own MMIO region (`0x602002000`, 2 MiB), so exclusive mapping fails with `-EBUSY` (found the hard way in Stage 4a, fixed in 4a-v2) |

PERST# GPIO: OIPG pin 179, via the DT's `pci@0,0`/`reset-gpios` child
node and `pci_host_common_parse_ports()` + manual
`gpiod_direction_output(desc, 0)` (mainline's automatic PERST handling
via that helper is opt-in only, not automatic -- a wrong assumption
caught before Stage 3 was built, see history doc).

## The two register-access mechanisms (the key mechanical finding)

Apple's `AppleEmbeddedPCIEPort::enableGated()` applies two different
record lists via two genuinely different hardware access paths. This
was the main open question resolved this session, via fresh Ghidra
decompile of the real iPad5,3 12B410 kernelcache
(`AppleEmbeddedPCIE.kext`), independently cross-checked against the
real captured J81 ADT.

**Order confirmed**: `dbi-overrides` applied first, then
`apcie-config-tunables`. (Decompiled `enableGated`,
`FUN_ffffff8002bee6cc`, and its dispatch chain directly -- see history
doc's "Independent verification of the Stage 5B trace" section, 2026-09-25.)

### `apcie-config-tunables`: direct per-port MMIO window

Uses the same per-port controller window (`0x602004000` for port 1,
above) our own driver already maps. Primitives `FUN_ffffff8002befd78`
(read) / `FUN_ffffff8002bef92c` (write) are plain `readl`/`writel` at
`port_base + offset`. No new mechanism needed -- our driver already does
this correctly.

### `dbi-overrides`: separate ECAM-relative accessor

Uses **two vtable calls** on the *controller* object (not the port):
slot `0x5e0` = read, `0x5e8` = write, signature
`(controller, selector, low_offset[, value])`.

Found via string xrefs to real debug strings `configRead32`/
`configWrite32`/`configRead16`/etc. in the kext:
`configRead32` referenced only from `FUN_ffffff8002bece24`,
`configWrite32` only from `FUN_ffffff8002becef0`. Decompiled both in
full -- they compute:

```
addr_offset = (selector >> 0x10 & 0xf00) | low_offset
            | ((selector << 4) & 0x7000)
            | ((selector << 4) & 0xf8000)
            | ((selector << 4) & 0xff00000)

value = *(u32 *)(controller_base + addr_offset)     // read
*(u32 *)(controller_base + addr_offset) = value      // write
```

where `controller_base` is a field at `controller+0xb0` (a separate
pointer from the direct per-port window's own base at `+0xd0`). This is
a classic ECAM-style `bus<<20 | dev<<15 | func<<12 | reg` bitfield
composition. **`controller_base` was traced to the same ECAM region
already mapped as `cfg->win`** (ADT reg index 0, `0x610000000`) by
checking the real J81 ADT's own `apcie` node resource list -- not a
second, unmapped window (confirmed in Martin's own `a72fd2c` research
commit, independently cross-checked).

**Selector composition**:

- Gate access: `selector = (port_selector_base & 0xf0ffffff) | 0x08000000`,
  `low_offset = 0xbc`.
- Per-record access (no gate bit): `selector = (port_selector_base &
  0xf0ffffff) | ((record_offset_field & 0xf00) << 16)`, `low_offset =
  record_offset_field & 0xff`.
- `port_selector_base`: independently confirmed by decompiling the
  port-init function (`FUN_ffffff8002bed5bc`, offset `0x1b4` assignment)
  -- it's `(apcie_port_adt_property & 0x1f) << 11`. For J81's port 1
  (`apcie-port = 1`), that's `1<<11 = 0x800`.

**Worked example (port 1's DBI gate), independently verified twice
(hand arithmetic + real hardware read)**:

```
selector    = 0x00000800 | 0x08000000 = 0x08000800
low_offset  = 0xbc
addr_offset = (0x08000800>>16 & 0xf00) | 0xbc | ((0x08000800<<4)&0x7000)
            | ((0x08000800<<4)&0xf8000) | ((0x08000800<<4)&0xff00000)
            = 0x800 | 0xbc | 0 | 0x8000 | 0
            = 0x88bc
```

So port 1's DBI gate lives at `ECAM_base + 0x88bc`, i.e.
`cfg->win + 0x88bc`. **Hardware-confirmed 2026-09-25**: reads
`0x00000000` cleanly, no fault (Stage 5B). The three `dbi-overrides`
records for port 1 resolve the same way to `0x8024`, `0x807c`, `0x8b44`.

## ADT-recovered records (the actual values Apple applies)

From the real J81 ADT's `apcie-config-tunables`/`dbi-overrides`
properties on the `pci-bridge1` node (12-byte little-endian
`(offset, clear-mask, set-value)` triples; `new = (old & ~clear_mask) |
set_value`):

| List | Raw ADT offset field | Resolved address | Clear mask | Set value |
| --- | --- | --- | --- | --- |
| `apcie-config-tunables` | `0x090` | direct window `+0x090` | `0x000000ff` | `0x00000028` |
| `apcie-config-tunables` | `0x130` | direct window `+0x130` | `0x00000003` | `0x00000003` |
| `apcie-config-tunables` | `0x134` | direct window `+0x134` | `0x00000001` | `0x00000001` |
| `dbi-overrides` | `0x024` | `ECAM + 0x8024` | `0x00000001` | `0x00000001` |
| `dbi-overrides` | `0x07c` | `ECAM + 0x807c` | `0x00000400` | `0x00000000` |
| `dbi-overrides` | `0xb44` | `ECAM + 0x8b44` | `0x00000003` | `0x00000002` |

(Earlier, pre-Stage-5B-trace baseline reads at the *raw* offsets
`0x024`/`0x07c`/`0xb44` inside the direct per-port window -- done in
Stage 5A -- were reading unrelated registers, not the real DBI targets;
this was a corrected misconception, see history doc.)

## Raw hardware results, most recent stages (verbatim dmesg)

**Stage 5B (read-only DBI gate probe, `0041`), 2026-09-25 -- clean:**

```
[0.231567] pcie-apple-t7000 610000000.pcie: t7000-pcie dbi-ecam-read-test: port 1 selector=0x08000800 ecam+0x088bc dbi_control=0x00000000
```

**Stage 5C (actual gated RMW, `0042`), 2026-09-25 -- clean write, still no endpoint:**

```
[0.130364] ...before port 1 refclk_en=0x11010100 perst_internal=0x00000100 unknown_10c=0x00000001 link_enable=0x00000000 ltssm=0x00000000
[0.130580] ...after port 1 refclk_en=0x11110101 perst_internal=0x00000001 unknown_10c=0x00000000 link_enable=0x00000001 ltssm=0x00000000
[0.233023] ...port 1 controller window after: 0x00=0x00000000 0x80=0x00000001
[0.233113] ...port 1 tuning baseline: 0x024=0x00000000 0x07c=0x00000000 0x090=0x00000004 0x0bc=0x00000000 0x130=0x00000004 0x134=0x00000000 0xb44=0x00000000
[0.233162] ...dbi-ecam-read-test: port 1 selector=0x08000800 ecam+0x088bc dbi_control=0x00000000
[0.233195] ...dbi-write-test: dbi gate saved=0x00000000, setting saved|1
[0.233228] ...dbi-write-test: dbi-override 0x08024: 0x00000000 -> 0x00010001   <-- ANOMALY, see below
[0.233263] ...dbi-write-test: dbi-override 0x0807c: 0x00733c12 -> 0x00733812   (matches formula exactly)
[0.233299] ...dbi-write-test: dbi-override 0x08b44: 0x000000d3 -> 0x000000d2   (matches formula exactly)
[0.233330] ...dbi-write-test: dbi gate restored to 0x00000000 (readback 0x00000000)
[0.233361] ...dbi-write-test: config-tunable 0x00090: 0x00000004 -> 0x00000028 (matches formula exactly)
[0.233391] ...dbi-write-test: config-tunable 0x00130: 0x00000004 -> 0x00000007 (matches formula exactly)
[0.233427] ...dbi-write-test: config-tunable 0x00134: 0x00000000 -> 0x00000001 (matches formula exactly)
[0.233691] pcie-apple-t7000 610000000.pcie: PCI host bridge to bus 0000:00
[0.233856] pci 0000:00:01.0: [106b:1002] type 01 class 0x060400 PCIe Root Port
[0.242088] pci 0000:00:01.0: PCI bridge to [bus 01]
[63.159961] pci_bus 0000:01: busn_res: [bus 01] end is updated to 01   <-- after manual rescan, still nothing on bus 01
```

Full boot otherwise clean: USB networking up, RTC set, HDQ battery
gauge probed (one unrelated, likely-transient HDQ timeout this boot --
known-flaky protocol, separate bus, unrelated to PCIe). No PCIe-related
dmesg errors beyond the benign, always-present `no iommu-map translation
for id 0x8` notice.

## The one open anomaly

`0x8024`'s write computed `(0x00000000 & ~0x1) | 0x1 = 0x00000001`, but
the immediate readback shows `0x00010001` -- an extra bit 16 set that
the driver never wrote. The gate save/restore bracketing this write
succeeded cleanly (`saved` reads back unchanged afterward), so this
isn't a gate-timing artifact. Most plausible explanation: a real
hardware-driven status/side-effect bit at this specific ECAM offset
(raw ADT offset `0x024`, plausibly a DesignWare-PCIe "port logic"
link/PHY status register) reacting to something in the write sequence.
**Not yet explained.**

## Stage 5D research correction and next experiment design, 2026-09-25

The initial handoff overstated the scope of Stage 5C. Re-reading the saved
decompile of `AppleEmbeddedPCIEPort::enableGated()` shows that Apple applies
the DBI lists and tunables, then performs this further ordered sequence
before it marks the port as enabled:

```
port + 0x114 = 0
port + 0x104 = 0xff70afff
port + 0x100 = 0x008f5000
invoke the callback object cached at port + 0x100
call FUN_ffffff8002befa14(port)
if applicable, call controller vtable slot + 0x570
advance the port state to 1
...
call FUN_ffffff8002befb10(port, 0)
port + 0x80 |= 1
advance the port state to 2
```

Stage 5C only contains the final `port + 0x80 |= 1` part of that tail, and
currently performs it **before** its DBI/tunable RMWs. Apple performs the
DBI/tunable RMWs first and `+0x80 |= 1` last. Stage 5C therefore proves the
individual writes are tolerated, but not that their sequencing matches
Apple. The fixed value at `+0x104` is not inferred: port initialization assigns
`0xff70afff` to its cached `+0x1b0` field. The three preceding direct writes
and their callbacks are therefore the best-supported missing work, ahead of
any new guessed gate, DART, MSI, or firmware change.

There is already strong evidence for a non-invasive link-state probe. In the
same Apple driver, `waitForLinkUpGated()` repeatedly calls the direct-window
read helper at `+0x88` and treats bit 6 as its completion condition. Its
disable path also polls `+0x8c` bit 0 and records bit 5 as an error/timeout
condition. The pinned upstream DesignWare header supplies a secondary,
independent diagnostic candidate: DBI `+0x728` exposes LTSSM state in bits
0:5 (L0 is `0x11`), while `+0x72c` has link-up bit 4 and training bit 29.
The DesignWare addresses are useful only as read-only corroboration until
their relation to this Apple port's ECAM/DBI view is verified.

**Recommended next payload: Stage 5D, read-only only.** Keep the existing
Stage 5C write order for this diagnostic-only build and add no new writes.
Sample direct-window `+0x088`,
`+0x08c`, `+0x100`, `+0x104`, and `+0x114` at the current post-enable point,
then after 10 ms, 100 ms, and 1 s. If the existing ECAM mapping can read
them without a new access mechanism, also log the port-1 DBI candidates at
`ECAM + 0x8728` and `ECAM + 0x872c`; otherwise omit those two reads. The
result distinguishes a link that never leaves reset/detect from one that
trains and fails, without changing hardware state.

Do **not** implement the three `+0x100/+0x104/+0x114` writes as an isolated
delay experiment. Their callbacks and the exact PERST/MSI sequencing must be
understood first; the resulting analysis is recorded immediately below.

### Callback decompilation result, 2026-09-25

That prerequisite is now substantially closed. The preserved Ghidra project
was reopened using an isolated JDK environment; no payload was built and no
device state was changed.

- `FUN_ffffff8002befa14()` is not an unknown link helper. It programs the
  port's MSI controller registers: `+0x124` encodes the number of MSI
  vectors and `+0x128` receives `msi-vector-base | (msi-vector-base << 16)`.
  The J81 port properties are eight vectors and base eight, so Apple's exact
  writes are `+0x124 = 0x31` and `+0x128 = 0x00080008`.
- `FUN_ffffff8002befb10(port, value)` stores the requested state and calls
  the cached `function-perst` platform function. `enableGated()` calls it
  with zero immediately before `+0x80 |= 1`; this is Apple’s ordered PERST#
  deassertion. Linux currently deasserts PERST# much earlier, before its
  DBI/tunable writes.
- `FUN_ffffff8002bef400()` only serializes and records Apple’s internal port
  state transition. It has no hardware register action and does not need a
  Linux equivalent.
- The callback object stored at `port+0x100` owns
  `FUN_ffffff8002bee0ac()`, Apple’s PCIe interrupt handler. Its `+0xa8`
  method enables that event source after `+0x100 = 0x008f5000`; it is needed
  for Apple’s asynchronous link-up/link-down handling, but is not a hidden
  controller register write. A first Linux experiment can use bounded
  polling of the already identified status registers instead.
- The optional object at `port+0xb0` is now identified: it is the PCI nub
  assigned by `AppleEmbeddedPCIEPort::setNub(IOPCIDevice *)`, not a PCIe
  controller helper or a DART object. Apple conditionally calls vtable slot
  `+0x570` on that root-port `IOPCIDevice` with argument zero. The exact
  `IOPCIDevice` virtual-method name is stripped from the iOS 8.1 kernelcache,
  so its semantic effect remains unlabelled. This is an Apple PCI-framework
  call on the already-created root-port object, not evidence for another
  unknown controller register write. Linux's PCI core owns the equivalent
  root-port object; do not imitate this opaque Apple vtable call directly.

This changes the practical next write-stage design. After the read-only
Stage 5D baseline, a minimal Stage 5E should: keep PERST asserted; apply the
already validated DBI overrides then tunables; write `+0x114 = 0`,
`+0x104 = 0xff70afff`, `+0x100 = 0x008f5000`, `+0x124 = 0x31`, and
`+0x128 = 0x00080008`; deassert PERST; set `+0x80` bit 0; then poll `+0x88`
bit 6 with a bounded timeout and log `+0x8c`. It must keep the unimplemented
Apple interrupt event source explicitly out of scope. The opaque
`IOPCIDevice` vtable call is Linux PCI-core territory and must not be copied
as a controller MMIO operation.

### Findings removed from the candidate list

- **Second DBI list:** ruled out for J81. The port-init trace and raw ADT
  inspection already establish one controller-level three-record list and
  no port-local `dbi-overrides` property. The earlier suggestion to check it
  again was stale.
- **Generic MSI/capability work:** cannot make an absent endpoint answer its
  first configuration read and remains out of scope. This does not exclude
  the two exact Apple MSI-controller writes above: they belong to the
  recovered port-enable sequence and are now a bounded Stage 5E item.

### Live-session confirmation

Read-only USB-network inspection on 2026-09-25 confirmed that the iPad is
currently running the Stage 5C test image: its log contains all three gated
DBI RMWs and all three direct tunable RMWs, followed by a root port at
`0000:00:01.0` and an empty bus 01. `/sys/bus/pci/devices` contains only the
root port. A 64-byte root config dump identifies it as `106b:1002`, class
`060400`, consistent with the boot log. No device state was changed during
this check.

## Leading hypotheses for why no endpoint enumerates (not yet tested)

1. **Missing Apple port-controller tail.** The exact writes at `+0x114`,
   `+0x104`, and `+0x100`, and their callbacks, are absent from Stage 5C.
   Stage 5C also starts the link before its DBI/tunable records, the reverse
   of Apple's order. This is the leading hypothesis; resolve the callbacks
   before a write-stage payload is made.
2. **Link-state evidence is missing.** The driver has no measured signal for
   whether the endpoint is held in reset/detect, training, or has reached
   L0. Stage 5D is designed to obtain that evidence without adding writes.
3. **The `0x8024` anomaly is itself diagnostic** of some link/PHY state
   machine this driver isn't accounting for -- e.g., if bit 16 is a
   "link training active" or "waiting for something" status bit, that
   might mean the link genuinely started training but got stuck, which
   a register dump immediately after (rather than a fixed delay + poll)
   might catch mid-transition.
4. **Other Apple callbacks in the missing tail.** The callback object at
   `port+0x100`, `FUN_ffffff8002befa14`, and controller vtable slot `+0x570`
   could contain a required readiness action. This is a narrower and more
   testable question than adding general MSI or capability code.

## Stage 5E hardware result, 2026-09-26

Implemented exactly the design above: DBI overrides, tunables, the three
port-tail writes, the two MSI registers, PERST# deassertion, link-start
last, then a bounded 500ms poll of `+0x88` bit 6. `kernel/patches/0044-...`.
Cross-build verified, then hardware-tested.

**Clean boot, no crash, no regression on anything already validated** --
DBI overrides, tunables, MSI registers (`+0x124`/`+0x128`), and the
link-start write all took exactly as expected. **But two of the three
port-tail writes did not take as written**:

- `+0x114 = 0`: took cleanly.
- `+0x104 = 0xff70afff`: readback was `0x0070afff` -- the top byte
  (`0xff`) silently didn't stick.
- `+0x100 = 0x008f5000`: readback was `0x00000000` -- **no effect at
  all**, as if the write never happened.

`+0x88` still reads `0x0000000c` after the full poll window; bit 6
(link-up) never sets. This isn't a crash or fault in either case --
both are silent write-doesn't-take behavior, the same general shape as
the earlier `0x8024` DBI-override anomaly (Stage 5C).

**Review correction, 2026-09-26:** the two observations do not yet
establish failed writes. `+0x104` retained all requested low 24 bits;
the zero upper byte is most likely reserved/read-as-zero. Apple’s own
interrupt handler reads `+0x100` as event status and writes handled bits
back through the same helper, making a write-one-to-clear/self-clearing
interpretation consistent with its zero readback. The direct window is
confirmed by that helper itself, so retrying a different width, window,
or link-start order would be blind.

**Next offline research, before another hardware payload:** recover the
conditional link-speed/internal helpers immediately before the tail
(`FUN_ffffff8002bef7c8`, `FUN_ffffff8002bef8d8`, and optional
`FUN_ffffff8002bf09a0`); trace all direct accesses to `+0x100` and
`+0x104`; then map Apple's port power/clock-gate-active requirement to
Linux PMGR/genpd. Stage 5E begins after those Apple prerequisites, so
they are now the leading explanation for a link still stuck at `0x0c`.

### Follow-up helper trace, 2026-09-26

The focused decompile closes two parts of that proposed research. The
captured J81 ADT contains `maximum-link-speed = 1`, so Apple's conditional
`FUN_ffffff8002bef7c8()` is active on this board. It uses the controller's
ECAM/config accessor to update the low 16 bits of a link-speed-related
configuration word. Stage 5E does not reproduce that operation.

The two following calls are no longer unknown: `FUN_ffffff8002bef8d8()`
applies the controller and optional port `dbi-overrides` lists, while
`FUN_ffffff8002bf09a0()` applies `apcie-config-tunables` through the
direct port window. Stage 5E already reproduces J81's one controller DBI
list and its tunables; their remaining gap is the Apple gate/availability
prefix and its ordering, not another record list.

Apple's interrupt handler reads `+0x100` as an event/status word and
writes handled bits back through the direct-window helper. This strongly
supports treating Stage 5E's `0x008f5000 -> 0` readback as a
write-one-to-clear or self-clearing event acknowledgement, rather than a
failed configuration write.

The remaining offline priorities are to fully decode the J81
maximum-link-speed RMW and map Apple's port power/clock-gate-active
requirement to Linux PMGR/genpd. Only then should a narrow Stage 5F be
designed around the recovered missing operation(s).

### Build gate after the next trace, 2026-09-26

The helper trace establishes the required scope but does **not** yet
authorize a Stage 5F write payload. Apple gates the link-speed operation
on a value returned through the same controller call that follows its
power/clock/DART prefix. The decompiler shows the subsequent RMW preserves
the upper 16 bits of that returned configuration word and replaces its
lower 16 bits according to `maximum-link-speed`; it does not yet recover
the capability-relative address or final J81 value with enough certainty
to copy it into Linux.

The later concrete-vtable trace corrects the shorthand used here: the port
passes `apcie-port = 1`, not gate ID `0x39`, to its controller hooks. The
`AppleT7000PCIe` `+0x6b8` hook then explicitly enables clock-gate entries
0, 1, and 2 and power-gate entry 0 through its `AppleARMIODevice` provider.
For J81 those are PCIE (`0x39`), PCIE_AUX (`0x3a`), PCIE_REF (`0x38`), and
PCIE power (`0x39`). Linux still attaches only `ps_pcie`, so the two sibling
domains remain an evidence gap rather than a reason to enable them blindly.

The exact next research deliverable is therefore a short address/dataflow
trace for that controller return value, paired with a PMGR-gate ownership
trace. It must answer: which configuration word is changed, what J81's
final low-16-bit value is, and whether Linux's existing `ps_pcie` is the
equivalent gate transition. If either answer remains unresolved, the next
build is read-only instrumentation only; it must not add a guessed write
or additional power domain.

### Stage 5F build instructions: recovered maximum-link-speed RMW, 2026-09-26

The exact Apple code path is now recovered sufficiently for one bounded
write-stage experiment. The earlier controller virtual call at `+0x618`
is a standard PCI capability lookup: it receives capability ID `0x10`
(PCI Express) and returns that capability's offset for port 1. It is not
a PMGR gate-ready query. J81's `maximum-link-speed = 1` is passed to
`FUN_ffffff8002bef7c8()`.

That helper performs the following standard root-port configuration RMW:

1. locate PCI capability `0x10` on root port `00:01.0` (ECAM device-one
   offset `0x8000`), using a bounded standard capability-list walk rather
   than a hard-coded capability offset;
2. read PCIe `Link Capabilities 2` at `cap + 0x2c`; require supported-link-
   speeds-vector bit 1 (Gen1) to be set, otherwise log and make no write;
3. read the 16-bit PCIe `Link Control 2` word at `cap + 0x30`;
4. write `new = (old & 0xfff0) | 1` with a 16-bit ECAM configuration
   write, then log the immediate 16-bit readback;
5. continue the already hardware-verified Stage 5E ordering unchanged:
   DBI overrides, direct tunables, `+0x114/+0x104/+0x100`, MSI setup,
   PERST# release, and `+0x80` link start last.

This is directly supported by the Apple assembler: the helper reads
`cap+0x2c`, checks the requested speed against bits 1:7, reads
`cap+0x30`, clears only bits 0:3, and invokes the controller's 16-bit
config writer with the requested speed. It is also a single missing
operation relative to Stage 5E. It must add no PMGR domain, no clock-gate
write, no DART reset, and no retry or rescan logic. If capability lookup,
the Gen1 bit check, or readback differs from the expected shape, it must
skip the write and leave Stage 5E behavior intact.

The Apple power/clock-gate prefix remains a separate unresolved
production-driver concern. It is deliberately excluded from this test:
`ps_pcie` and the DART consumer are already hardware-proven clean, while
the link-speed RMW is independently exact and has a before/after guard.

## Stage 5F hardware result, 2026-09-26

Implemented exactly the design above. Cross-build verified, then
hardware-tested. `kernel/patches/0045-...`.

**Clean boot, no crash. Capability walk found PCI Express capability at
`cap@0x70`; `lnkctl2` read `0x0002` (Target Link Speed field = Gen2) and
was written to `0x0001` (Gen1), confirmed by immediate readback.**
Everything from Stage 5E (DBI overrides, tunables, port-tail writes, MSI
registers, PERST#, link-start) continued to behave identically -- no
regression.

**New signal, not seen in any prior stage**: Linux's own generic PCI
core printed, during the post-`.init()` bus scan:

```
pci 0000:00:01.0: removing 2.5GT/s downstream link speed restriction
pci 0000:00:01.0: retraining failed
```

This is **not** Apple- or J81-specific -- it's mainline's own generic
erratum workaround, `pcie_failed_link_retrain()` in
`drivers/pci/quirks.c`. It fires on *any* downstream port whose Target
Link Speed field reads exactly Gen1 (`PCI_EXP_LNKCTL2_TLS_2_5GT`) at
scan time and which supports Link Active reporting -- exactly the state
our own write left the port in. Linux assumed this might be a leftover
firmware-imposed restriction, tried to lift it back to the port's own
reported max speed capability, and retrained. **That retrain also
failed.**

This is genuinely informative despite being an unrelated code path:
Linux's own generic retry, at the port's own advertised maximum
capability (not our chosen Gen1 value), *also* couldn't bring the link
up. That weakens "wrong link-speed encoding" as the remaining blocker --
the link doesn't fail to train because of *which* speed is requested,
it fails to train at all, at any requested speed. This shifts weight
back toward the Apple power/clock-gate translation question. The subsequent
concrete-vtable trace shows that Apple enables all three controller clock
gates while Linux still only has `ps_pcie`; it also exposes a second
comparison point in the `+0x6d0` hook: for port 1 Apple clears bit 0 at
shared offset `0x180` and sets bit 0 at `0x198` before continuing. Stage 5F
leaves `0x180` bit 0 set through its older shared sequence. `+0x88` still
reads `0x0000000c` after the poll; bit 6 (link-up) never sets.

**Next, not yet built**: keep these two changes separable. First verify the
active T7001 PMGR-domain graph and design an AUX/REF-only attachment test;
then decide whether the exact `+0x6d0` shared-register transition deserves
a separate one-RMW experiment. Combining them would make either result
ambiguous.

## Post-Stage-5F gate trace: concrete Apple controller path, 2026-09-26

The remaining gate question is now narrower than the old “does `ps_pcie`
cover `0x39`?” framing. `AppleEmbeddedPCIEPort::init()` stores the port
number (`apcie-port`, J81 value `1`) at `port+0xa8`; it does not store
`power-gates`. The active `AppleT7000PCIe` subclass vtable resolves:

| Hook | Target | Effect relevant to J81 |
| --- | --- | --- |
| `+0x6b8` | `FUN_ffffff8002e6e038` | Enables `clock-gates[0..2]` and `power-gates[0]` through `AppleARMIODevice`, then delays 10 µs. This is the exact PCIE/AUX/REF evidence above. |
| `+0x6d0` | `FUN_ffffff8002e6e3e4` | With port 1, clears shared `0x180` bit 0 and sets shared `0x198` bit 0. Its two surrounding reads are at `0x844` and `0x854`; no additional write was found in this hook. |

This establishes two independently testable deltas from Stage 5F. It does
not establish that either one alone will train the link. No Stage 5G
implementation follows from this note: its pre-build review must verify the
current T7001 PMGR nodes and choose one delta only.

## Stage 5G hardware result, 2026-09-26

Per Martin's own research-agent recommendation (test AUX/REF first,
alone; test `0x180`/`0x198` second, alone -- combining them would make
either result ambiguous): implemented the first delta in isolation.
`kernel/patches/0046-...` extends `pcie`'s `power-domains` to
`<&ps_pcie>, <&ps_pcie_aux>, <&ps_pcie_ref>` and adds explicit
`genpd_dev_pm_attach_by_id()` + `pm_runtime_get_sync()` calls for
indices 1/2 (automatic genpd attach only covers index 0). No
register-level changes versus Stage 5F.

**Clean boot, both domains attached and held on with no error --
`+0x88` still identical, `0x0000000c`, bit 6 never sets. No downstream
device.** This is a clean negative result: powering `ps_pcie_aux`/
`ps_pcie_ref` alone does not bring the link up. It rules out "simply
unpowered sibling gates" as a standalone explanation.

**Next, not yet built: Stage 5H**, testing the second delta alone --
`+0x6d0`'s exact register transition for port 1 (clear shared offset
`0x180` bit 0, set `0x198` bit 0) -- on top of Stage 5F, without the
AUX/REF attach, so this second result stays equally unambiguous.

Full verbatim dmesg and record in
`research/t7000-pcie-hardware-findings.md`'s "Real PCIe host-controller
driver, Stage 5G" section.

## Stage 5H hardware result, 2026-09-26

Second delta, tested alone (built on Stage 5F, not 5G). `dmesg`:

```
port 1 0x180: 0x11010100 -> 0x11010100 (clear bit0)
port 1 0x198: 0x00000000 -> 0x00000001 (set bit0)
link_up=0 0x088=0x0000000c 0x08c=0x00000000
```

**Genuinely uninformative delta**: `0x180`'s bit 0 was already clear at
this early point, so the write changed nothing; `0x198`'s early
`0->1` doesn't change anything either since the existing enable
sequence already sets that same bit later regardless. No observable
difference from Stage 5F -- same link result, same no-device outcome.

**Both Post-Stage-5F deltas are now individually ruled out.** Neither
the AUX/REF gate attach (Stage 5G) nor the `+0x6d0` register transition
(Stage 5H), tested alone, changes anything. This significantly narrows
the remaining explanation space to one of:

1. The two deltas need to be combined (an interaction effect not
   visible from either alone) -- lowest-confidence, since neither
   showed even a partial effect on its own.
2. A genuinely different Apple operation, not yet decompiled, is the
   real prerequisite -- specifically worth revisiting the `+0x570`
   opaque `IOPCIDevice` vtable call and the interrupt event source at
   `port+0x100`, both previously set aside as "Linux PCI-core/IRQ
   territory, not controller MMIO." That assumption itself hasn't been
   tested.
3. Something outside the enable/gate/DBI/tunables/tail sequence
   entirely -- firmware, NVRAM, or a hardware condition/precondition
   this investigation hasn't identified yet.

**Next is research, not another blind register-level test.**

Full verbatim dmesg and record in
`research/t7000-pcie-hardware-findings.md`'s "Real PCIe host-controller
driver, Stage 5H" section.

## Where everything lives

- Full chronological history (every stage, every hardware result, every
  wrong turn and correction): `research/t7000-pcie-hardware-findings.md`.
- Driver source: `drivers/pci/controller/pcie-apple-t7000.c` (via patches
  `kernel/patches/0016`, `0040`, `0041`, `0042`).
- Real J81 ADT capture (private, git-ignored, never commit):
  `artifacts/adt/20260908T082112Z-j81.adt`.
- Ghidra project used for all decompile work (private, not in git):
  `/private/tmp/claude-501/.../scratchpad/dart-research/ghidra-proj`,
  project `prelinktext`, process `PRELINK_TEXT.raw`, from the real
  iPad5,3 iOS 8.1 (12B410) kernelcache pulled via `blacktop/ipsw` (no
  multi-GB download, remote kernelcache extraction only).
- Priority/status tracking: `docs/plans/2026-09-15-active-work-priority.md`,
  `CLAUDE.md`'s own dated status log, `docs/project-status.md`.
