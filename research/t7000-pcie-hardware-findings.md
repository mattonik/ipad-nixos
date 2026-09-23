# T7000 PCIe: hardware test findings, 2026-09-21 to 2026-09-23

Consolidated reference for every real hardware result from the J81 PCIe
host-controller investigation. The dated narrative (why each test was
designed the way it was, and the reasoning between rounds) lives in
[`docs/plans/2026-09-13-j81-wifi-pcie.md`](../docs/plans/2026-09-13-j81-wifi-pcie.md);
this file exists so the raw evidence -- what was actually run, and exactly
what came back -- is in one place rather than spread across six dated
sections.

## The conclusion, stated first

Six real hardware boots, each changing exactly one variable versus the
previous clean one:

| # | Patch | What it did | Result |
| --- | --- | --- | --- |
| 1 | `0018` (write-capable) | Full enable sequence: shared-window writes (`REFCLK_EN`, `PERST_INTERNAL`, `0x10c`, `LINK_ENABLE`, LTSSM start) + `reset-gpios` DT node + DART/`iommu-map` + full `pci_host_common_init()` | **Hung.** Black screen, backlight on, no console, no USB. Two attempts, identical. |
| 2 | `0018` ("read-only", later found not actually passive) | Same as above minus the shared-window writes and `reset-gpios`, but still called `pci_host_common_init()` (full ECAM + bus scan) | **Hung**, identically. |
| 3 | `0019` (PMGR-only) | Only the DT `status = "okay"` flip + automatic `power-domains = <&ps_pcie>` genpd power-up. No MMIO, no PCI core, no DART. | **Clean.** |
| 4 | `0020` (shared-window read) | `0019` + one bounded `readl()` of the shared register window (port 1 LTSSM offset) | **Clean.** `ltssm=0x00000000`. |
| 5 | `0021` (ECAM read) | `0019` + one bounded `readl()` of ECAM offset 0 (bus0/dev0/fn0), via raw `devm_ioremap_resource()`, no `pci_ecam_create()` | **Clean.** `vendor/device=0xffffffff`. |
| 6 | `0022` (multi-offset ECAM read) | Same as `0021`, three reads: bus 0, bus 1, bus 4 | **Clean.** All three `0xffffffff`. |
| 7 | `0023` (isolated `pci_host_common_init()`) | The *exact* call both `0018` attempts made -- `devm_pci_alloc_host_bridge()` + `pci_host_common_init()` with a bare ECAM ops struct -- and nothing else. No shared-window writes, no PERST, no DART. | **Clean.** Returns `0`; full generic bus scan completes. |

Every individual piece `pci_host_common_init()` touches has now been
proven safe in isolation: the DT status flip, the power-domain attachment,
raw MMIO reads of both the shared window and ECAM at multiple points, and
the complete generic PCI bus scan itself (including its BAR-sizing
config-space writes and bus-number programming).

**The only thing either hanging `0018` attempt did that no clean test did
is the hardware enable-sequence writes** to the shared window: `REFCLK_EN`
(offset `0x100`), `PERST_INTERNAL` (`0x108`), the undocumented `0x10c`,
`LINK_ENABLE` (`0x118`), and the final LTSSM-start write
(`writel(3, ...)` at `0x820 + port*0x40`) -- traced from the real
`AppleT7000PCIe::_enablePortHardware`/`AppleEmbeddedPCIEPort::enableGated`
kernelcache functions. That write sequence is the sole remaining,
well-evidenced suspect. It has never been tested in isolation.

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

All `0xffffffff` results are the ordinary, correct PCI "no device present"
response -- not faults, not garbage, not hangs. Consistent with the real
enable sequence (which deasserts PERST# and starts LTSSM) never having
run, so no endpoint has ever actually been link-trained or visible to any
of these tests.

## Next step

Test the enable-sequence writes in isolation: shared-window write access
only (no ECAM, no `pci_host_probe()`, no DART), staged one write at a
time in the same graduated style `0022` used for multiple reads, to
localize which specific write in the sequence -- if any -- is what
actually hangs the boot. Not yet implemented as of this writing.

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
