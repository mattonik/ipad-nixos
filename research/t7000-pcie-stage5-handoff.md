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

Do **not** implement the three `+0x100/+0x104/+0x114` writes yet. First
finish offline decompilation of `FUN_ffffff8002befa14`,
`FUN_ffffff8002befb10`, the callback at the object stored in `port+0x100`,
and the controller's `+0x570` slot. Those calls may be load-bearing and are
not safe to replace with a delay. The local Ghidra installation currently
lacks a Java runtime, so this remaining decompile is recorded as an explicit
research prerequisite rather than guessed around.

### Findings removed from the candidate list

- **Second DBI list:** ruled out for J81. The port-init trace and raw ADT
  inspection already establish one controller-level three-record list and
  no port-local `dbi-overrides` property. The earlier suggestion to check it
  again was stale.
- **MSI programming:** cannot make an absent endpoint answer its first
  configuration read. It becomes relevant only after link-up and enumeration
  are established, so it should not be included in Stage 5D or the first
  missing-tail experiment.

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
