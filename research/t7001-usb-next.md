# T7001 USB: diagnostics and upgrade candidates

**RESOLVED, 2026-09-08.** `m1n1-hoolock-control` booted completely on its
first hardware attempt and USB networking works bidirectionally: 0% ping
loss, working telnet, genuine interactive remote shell access to the live
device. The two overnight-bundled drivers (Apple PMIC RTC, backlight)
were also confirmed working on real hardware in the same session (RTC set
the system clock from real hardware time; backlight physically dimmed the
screen on command, visually confirmed). Full transcript in
`docs/software-only-control.md`'s "Round 10." Everything below this point
is the research and implementation trail that led there -- kept as the
record of how the fix was found, not superseded or deleted.

Reviewed 2026-09-07, after Round 7. **Update, same day: the diagnostic ran
on hardware (see "Hardware result" below) and found the fault is
asymmetric -- device RX works, device-to-host TX does not reach the FIFO.
Hardware diagnosis continues, now narrowed to one direction.**

**Decision, same day:** pursue a newer kernel (Hoolock's tree, tracking
Linux 7.3-rc1) on `main` regardless of how the trace investigation turns
out -- tag `usb-diagnostic-round8-2026-09-07` marks the branch point, and
`usb-dwc2-pio-trace` carries the low-level PIO-fill tracing forward
independently. See "Decision, 2026-09-07" below for the full reasoning,
verified version/file facts, and the concrete implementation plan.

**Progress, same day: the newer kernel builds, and now boots-ready.**
After one narrow, unrelated GCC compile fix (a missing `default:` case in
the Apple PMIC backlight driver -- disabled via config, since backlight
isn't needed for this investigation), `kernel/hoolock.nix` produces a
clean `Image` and `dtbs/apple/t7001-j81.dtb`. That DTB already has the
`cpu-release-addr` and `enable-method` placeholders Rounds 3-5 had to
hand-patch onto the historical kernel's DTB -- only the framebuffer-node
rename (proven in Round 3) was still needed, and is now applied. Wired
into a new `m1n1-hoolock-control` payload (framebuffer patch, plus a
`deviceinfo_usb_rndis_function="ecm.usb0"` override so the initramfs's
existing configfs gadget setup targets a function this kernel actually
has compiled in). Builds cleanly and passes every static check available;
no hardware boot attempt yet -- that's next. See "Implementation
progress" and "Wired into a bootable payload" under the decision section
below.

## Hardware result (2026-09-07, Round 8 in `docs/software-only-control.md`)

Ran `m1n1-usb-diagnostic` per the procedure below. Steps 1-2 of the resume
checklist are complete: PongoOS/`load_m1n1.py` handoff succeeded normally,
and the user photographed all three diagnostic pages (four photos across
two page-1/page-3 cycles, since the hook loops forever).

**Page 1** (~2 min uptime): `usb0` shows `rx_packets: 304`, zero
errors/drops, and a **complete** ARP entry for `172.16.42.2` with the
exact MAC address of the Mac's `en10` from the same round
(`ca:03:00:00:3f:72`). Linux only completes an ARP entry like this by
processing a real incoming ARP request addressed to a local IP (RFC 826
merge behavior), so the Mac's broadcasts are provably reaching and being
parsed by the iPad's kernel. The device's own outbound ping to
`172.16.42.2` still shows 100% loss, matching the Mac-side symptom from
every prior round.

**Page 2**: the bulk IN endpoint (device-to-host, `ep1`) shows
`DIEPTSIZ=0x2008005a` -- a 90-byte, 1-packet transfer still marked
pending -- while `GINTSTS` reports `NPTxFEmp` (TX FIFO empty) asserted at
the same time. The transfer was programmed at the descriptor level but
never reached the physical FIFO for the host to read. `DAINTMSK` does
unmask EP1's completion interrupt, and `dwc2_hsotg_handle_generic_irq()`/
`dwc2_hsotg_irq_fifoempty()`/`dwc2_hsotg_trytx()` in this exact kernel
tree all read as unmodified, standard mainline PIO fill-on-`NPTxFEmp`
logic on inspection -- ruling out the simplest explanations (a masked
interrupt, an obviously Apple-patched fill routine) without yet pinning
the actual defect. Separately, `DAINT` shows the CDC notification
endpoint (`ep3`) has a pending, *unmasked-out* interrupt bit -- possibly
related, possibly a separate lower-stakes issue.

**Page 3**: `init ecm` / `activate ecm` fire within 0.5s of boot
(matching the `ecm_setup`/`ecm_set_alt` dyndbg trace this diagnostic
enables), and the host successfully drives `SET_ETHERNET_PACKET_FILTER`
through several values ending at `0x0e` (broadcast+directed+all-multicast
-- a normal "link is live" state), confirming macOS's ECM class-level
negotiation is completely healthy. The fault is specifically in the bulk
data path, not control-channel setup.

**Conclusion**: RX (host-to-device) is proven working end-to-end from
real device-side counters. TX (device-to-host) fails between the
software transfer-size register and the physical FIFO -- a real, narrow,
now-localized defect, not the "total, cause-unknown" failure Round 7
described. Leading hypothesis: a PIO fill/re-arm bug specific to this
forced-PIO (DMA hardcoded off) historical fork, not yet pinned to an
exact line. Full write-up in `docs/software-only-control.md`'s "Round 8".

**Next steps, not yet done**: trace `dwc2_hsotg_write_fifo()`'s handling
of a partial fill / FIFO-empty re-arm for the specific case where a
transfer doesn't complete in one write, since the generic dispatch logic
around it reads correctly. In parallel or as an alternative, the
"Hoolock kernel candidate" section below remains a live option -- it
restores real DMA hardware-capability detection instead of forcing PIO,
which could sidestep this exact class of bug rather than requiring it to
be found and fixed in the historical fork.

## Session handoff: completed work and exact resume point

The user authorized the diagnostic implementation and additional research.
Both are complete locally. **The diagnostic payload has not been uploaded or
booted on hardware yet.** The latest USB observation still showed the previous
Linux gadget. The user has been asked to enter DFU and run the PongoOS command
below; no response confirming that step has been received at this handoff.
`sudo -n true` returned `sudo: a password is required`, so the PongoOS launcher
must currently be run in the user's terminal. This is an authentication
requirement, not a new approval requirement for the already-authorized work.

At review start, Git was clean on `main` at
`51b85b159b39028a235294035bb18f8f6a66eb30`, matching a live `git ls-remote origin`
check. There were no stashes or extra worktrees. The existing
`linux-boots-2026-09-07` tag points to the earlier first-boot milestone.
This session's changes are **uncommitted and unpushed**; no new tag was created.
`git add -N` was used for `boot/usb-diagnostic.sh` so the Git-backed Nix flake
can include the new file; its content has not been staged for a commit.

| Changed file | Purpose |
| --- | --- |
| `flake.nix` | Adds the separate `m1n1-usb-diagnostic` package; the working control stays intact |
| `boot/usb-diagnostic.sh` | Replaces only the debug-shell hook with the display diagnostics |
| `boot/test_usb_diagnostic.py` | Runnable stdlib check of the actual built archive and assembled payload |
| `research/t7001-usb-next.md` | Evidence, source links, build/run instructions, decision table and this handoff |
| `docs/project-status.md`, `docs/software-only-control.md` | Point readers to the latest evidence and supersede the overconfident Round 7 diagnosis |
| `README.md`, `CLAUDE.md` | Refresh entry-point status so future work does not resume the obsolete black-screen or UART-only plan |

Completed validation:

- The Nix diagnostic build succeeded on the configured Linux builder. Only the
  diagnostic assembly derivation rebuilt; no kernel compilation was needed.
- The final `python3 boot/test_usb_diagnostic.py result-m1n1-control
  result-usb-diagnostic` check passed: PongoOS, m1n1, kernel and DTB are
  byte-identical to the control; the original uncompressed initramfs is intact;
  only the executable debug hook is overlaid; payload order and hashes match.
- ShellCheck passed after adding directives for the two sourced files that
  exist inside the initramfs rather than on the Mac. `sh -n` also passed.
- `shasum -a 256 -c result-usb-diagnostic/SHA256SUMS` passed for all three entries.
- `git diff --check` passed. Native macOS `nix flake check --no-build --offline`
  passed, explicitly excluding incompatible Linux outputs; it is not a full
  all-systems validation. The Linux diagnostic package itself was built.
- During the initial review, both existing uploader self-checks passed.

The builder printed cache DNS warnings, but all required inputs were available
and the builds completed. ShellCheck was fetched to the host's Nix store; no
new runtime dependency was added to the iPad image. The first diagnostic build
was replaced by a second build containing only ShellCheck comment additions.
The final artifact is:

```text
result-usb-diagnostic -> /nix/store/sibis0nwlpbn3kqfl4rwjxh7lna55hkc-ipad-air2-usb-diagnostic
m1n1-linux.bin SHA-256: 185f950260bf3dc8302a3df89f3ee00393579706b1dfaaeb295a369138d14e69
control -> /nix/store/2dk7jm1r3k1gjlmj9zgqszar105w1as2-ipad-air2-m1n1-control
```

Resume in this order:

1. Confirm DFU/PongoOS with the user and host USB enumeration. Run the existing
   uploader only once PongoOS (`05ac:4141`) is present, using the diagnostic
   artifact above. An accepted upload alone is not proof of Linux boot.
2. Confirm the three diagnostic pages appear. Record screenshots and exact
   page values; do not label this image hardware-tested until that happens.
3. Rediscover the Mac interface, verify `172.16.42.2/24`, then compare both
   endpoints' counters while probing. On the Mac, use `networksetup
   -listallhardwareports`, `ifconfig <interface>`, `netstat -I <interface> -b`,
   `arp -n 172.16.42.1`, `ping -c 4 -W 1000 172.16.42.1`, and
   `nc -vz -G 3 172.16.42.1 23`. If needed, capture ARP/ICMP with
   `sudo tcpdump -ni <interface> 'arp or icmp'` in the user's terminal.
4. Follow the observation/decision table below. If telnet works, collect
   `/tmp/usb-diagnostic/*` and `dmesg` before rebooting, since logs are in RAM.
   If the diagnostic fails to boot, return to the unchanged `m1n1-control`
   PongoOS/payload using the same DFU procedure and record the visible failure.
5. If the old stack still fails, prepare the separate matched Hoolock kernel
   and DTB experiment described below. It has been researched, **not built**.
   Keep touch, Wi-Fi and desktop work outside this USB investigation.
6. Append hardware outcomes, artifact identity, commands, and the revised next
   step to this record and refresh the status links after each experiment.

## What we actually know

The historical 5.19-rc1 kernel boots with the patched historical J81 DTB.
macOS binds CDC-ECM and creates `en10`, configured as `172.16.42.2/24`.
On the hub connection it reported 1,741 transmitted packets and zero received.
After moving the iPad directly onto the Mac's other USB controller (confirmed
by `ioreg`, no intervening hub), the fresh interface still reported 119 TX,
zero RX, incomplete ARP, four unanswered pings and a timeout on TCP port 23.

That rules out the hub as a sufficient explanation. It does **not** prove
that packets reached the iPad or that both USB directions are broken. Host
packet capture observes the host networking stack; device RX/TX counters,
endpoint state and USB transfer completions are still missing.

The old initramfs really does assign `172.16.42.1` before printing
`Using interface usb0`. That is useful evidence, but not a measurement of
the live controller. Likewise, the historical driver's forced `g_dma=false`
explains its warning; it does not establish that its PIO path works on T7001.
The categorical exclusions in the old Round 7 narrative are superseded here.

## First experiment: observe the device without changing its kernel

Build and verify:

```bash
nix build .#packages.x86_64-linux.m1n1-usb-diagnostic -o result-usb-diagnostic -L
python3 boot/test_usb_diagnostic.py result-m1n1-control result-usb-diagnostic
```

`m1n1-usb-diagnostic` copies the proven PongoOS, m1n1, DTB and kernel unchanged.
It adds a one-file CPIO overlay replacing the existing postmarketOS debug-shell
hook. The original `/init`, binaries, device nodes, USB setup and IP assignment
remain intact. The hook skips the debug splash, retains the RAM-only telnet
shell on `172.16.42.1:23`, and shows three pages for 12 seconds each:

1. `usb0` address/carrier, packet/error/drop counters, UDC state/speed,
   ARP entries, USB interrupt counts and a bounded ping toward the Mac.
2. DWC2 endpoint registers and effective DMA/FIFO parameters from debugfs.
3. Recent USB kernel messages, including ECM activation and packet-filter logs.

The latest snapshots overwrite `/tmp/usb-diagnostic/{link,controller,kernel,ping}`;
there is no growing userspace log. `ignore_loglevel` is removed so the hook can
keep asynchronous kernel messages from obscuring the display. A narrow boot-time
`dyndbg` query enables `ecm_setup`, `ecm_set_alt` and `gether_connect` messages.
Both DEBUG_FS and DYNAMIC_DEBUG are enabled in the **actual ECM kernel config**
(`/nix/store/byndrr6w3r5gxa2di0zsjp2p201jqhmi-linux-config-aarch64-unknown-linux-gnu-5.19.0-rc1`).
The older `result-historical-config` symlink still points to the pre-ECM config;
do not use that symlink to infer the currently booted kernel's configuration.

The [kernel initramfs format](https://docs.kernel.org/driver-api/early-userspace/buffer-format.html)
supports concatenated CPIO archives. Both archives are compressed as **one gzip
member**: the pinned [m1n1 payload loader](https://github.com/HoolockLinux/m1n1/blob/d5a10ac52a6468484854419a6c5130f1d62073eb/src/payload.c)
passes the complete decompressed byte count to Linux. The archive check verifies
the original bytes, the sole replacement entry, executable mode, payload order
and checksums. This is build validation, not a claim that the dashboard has run
on the iPad yet.

Boot with the established DFU/PongoOS procedure:

```bash
sudo /tmp/palera1n-arm64 --pongo-shell \
  --override-pongo "$PWD/result-usb-diagnostic/Pongo.bin" --debug-logging
# After PongoOS enumerates as 05ac:4141:
nix develop -c python3 boot/load_m1n1.py result-usb-diagnostic/m1n1-linux.bin
```

Retain the direct cable, rediscover the host interface after reboot, and use
`172.16.42.2/24`. Photograph each page while the host pings `172.16.42.1`.

| Observation | Next investigation |
| --- | --- |
| UDC not configured or carrier absent | ECM configuration/alternate setting and endpoint activation |
| iPad RX rises while Mac receives nothing | iPad response/TX path and host receive path |
| Neither device counter rises despite both peers probing | Endpoint activation, request queues, interrupts and controller configuration |
| iPad TX rises but host RX stays zero | Check USB completion/endpoint state; network TX counters alone do not prove delivery |
| Traffic works with this hook | Compare legacy debug-hook behavior; retain the old kernel until the difference is isolated |

## What a newer kernel could change

The [Hoolock A8/A8X support table](https://github.com/HoolockLinux/docs/blob/23ebe1fbc375599221553a7e1815e5de182a6b42/features/A8.md)
lists USB2 device mode as available in its patched tree. The
[build guide](https://github.com/HoolockLinux/docs/blob/23ebe1fbc375599221553a7e1815e5de182a6b42/tutorials/SETUP.md)
explicitly pairs that tree with Hoolock m1n1 and requires the 4 KiB page
configuration for these older SoCs. Its example userspace also describes USB
networking, serial and a RAM disk containing logs; this is project support
documentation, not a test transcript from our particular iPad.

The live `hoolock` branch resolved to `6831bc701a6ce059e71e5aaa9488c9195bea6927`
(commit date 2026-09-03). Inspection found relevant differences:

| Area | Historical control | Hoolock candidate |
| --- | --- | --- |
| DWC2 match | `apple,t7000-usb` | `apple,t7000-dwc2`, `apple,dwc2` |
| Gadget TX FIFO requested per FIFO | 256 words | 244 words; effective allocation still depends on hardware validation |
| DMA capability validation | Hardcoded false, forcing PIO | Hardware capability check restored; actual operating mode must be measured |
| USB hardware description | Legacy USB node, inherited setup | USB complex, explicit PHY, power domains, resets, peripheral mode, nonposted MMIO |
| Gadget setup in example config | Built-in legacy `g_ether` | Configfs ECM/ACM/NCM, legacy `g_ether` disabled |

Sources: [Apple DWC2 patch](https://github.com/HoolockLinux/linux/commit/6f725e0733950d172c7672759e509b6a7b5862da),
[current parameters](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/drivers/usb/dwc2/params.c),
[T7001 device tree](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/arch/arm64/boot/dts/apple/t7001.dtsi),
[AUSB PHY driver](https://github.com/HoolockLinux/linux/blob/6831bc701a6ce059e71e5aaa9488c9195bea6927/drivers/phy/apple/ausb.c),
[example configuration](https://github.com/HoolockLinux/docs/blob/23ebe1fbc375599221553a7e1815e5de182a6b42/config_16k).

The current PHY needs calibration properties supplied by m1n1. Our pinned
artifact is from Actions run `33380676898`, source commit
`d5a10ac52a6468484854419a6c5130f1d62073eb` (2026-08-31). Its history already
contains [the AUSB tunable handoff](https://github.com/HoolockLinux/m1n1/commit/ce0d81ae2aff).
An m1n1 update is therefore not the first missing prerequisite.

There are also subsequent generic DWC2 fixes for power-state recovery and
pull-up changes, for example
[recovery after power-domain off](https://github.com/HoolockLinux/linux/commit/ba6e518d136b)
and [exiting partial power down when changing pull-up](https://github.com/HoolockLinux/linux/commit/bf1e90189a98).
Neither establishes our failure's cause; the historical Apple settings already
disable some low-power modes. Avoid treating an unrelated fix title as proof.

## Recommendation after the diagnostic run

If the old stack still cannot transfer data, test a **separate, pinned Hoolock
kernel plus its matching J81 DTB**, keeping our working PongoOS/m1n1 and the
diagnostic display. Enable 4 KiB pages, `APPLE_USBCOMPLEX`, `PHY_APPLE_AUSB`,
DWC2, framebuffer, debugfs, and a deliberate ECM gadget configuration. Preserve
the existing result links as the rollback control. Plain mainline is not a
drop-in substitute for the Apple USB support advertised by Hoolock.

Do not transplant just the new DTB onto 5.19: its compatible strings, PHY,
power and bus dependencies changed. Do not merely flip DMA on in 5.19 without
auditing address translation and controller support. FIFO edits likewise need
the effective debugfs values first: this fork reads DT properties **before**
its Apple callback overwrites the FIFO values, and exposes no corresponding
`g_rx_fifo_size`/`g_tx_fifo_size` module parameters. Blind bootarg tuning would
not do what the old runbook suggested.

A physical Linux host remains a useful independent ECM test. USB ACM serial
would bypass Ethernet/IP, but shares DWC2 bulk transfers and is not an
independent UART; the historical config also lacks CONFIG_USB_CONFIGFS_ACM.
No inspected issue report established an exact fix for this iPad's zero-RX
symptom. GitHub eventually rate-limited the additional API reads; the concrete
findings above were obtained before that limit.

## Decision, 2026-09-07: pursue the newer kernel on `main`, keep tracing the old one on a branch

After Round 8 narrowed the fault (RX works, TX to host doesn't reach the
FIFO, exact defect not yet pinned), the user decided a newer kernel is
worth pursuing regardless of outcome -- "only positive in the long run" --
rather than treating it as a fallback contingent on the trace failing.
Two parallel paths, so neither blocks the other and neither risks losing
work:

- **`main`**: adopt a newer, actively-maintained kernel base (below).
- **`usb-dwc2-pio-trace`** branch (from tag `usb-diagnostic-round8-2026-09-07`,
  the last commit before this split): continue tracing
  `dwc2_hsotg_write_fifo()`'s partial-fill/re-arm logic on the *historical*
  5.19-rc1 kernel, in case the newer kernel turns out to have its own new
  problems, or simply as an independent confirmation of the root cause.

### Newest kernel available, verified today

Checked directly against the live repositories, not from memory or the
prior review's cached knowledge:

- Mainline `torvalds/linux` is at **v7.3-rc2** (`git ls-remote`/tags API,
  2026-09-07). Linux versioning passed 6.x sometime before this session;
  the jump from our historical 5.19-rc1 (June 2022) spans roughly four
  years and multiple major versions.
- `HoolockLinux/linux`'s `hoolock` branch HEAD is still
  `6831bc701a6ce059e71e5aaa9488c9195bea6927` (2026-09-03, "Merge branch
  'bits/090-dart' into hoolock") -- unchanged since the prior review, so
  no newer Hoolock commit has landed in the last four days. Its `Makefile`
  reads `VERSION=7 PATCHLEVEL=3 SUBLEVEL=0 EXTRAVERSION=-rc1` -- it tracks
  mainline **Linux 7.3-rc1**, one `-rc` behind current mainline tip. This
  remains the only actively-maintained tree with real Apple T7001 USB
  device-mode support; there is no reason to chase raw mainline instead,
  since mainline's own Apple SoC support is far less complete for this
  specific hardware (confirmed by this project's own earlier mainline-DTB
  attempts, which had no USB controller node at all -- see Round 3).

### What actually changes for our implementation, verified against the real files

- **A ready-made DTB for our exact board already exists**:
  `arch/arm64/boot/dts/apple/t7001-j81.dts` is present in the Hoolock tree
  at the current HEAD (confirmed via the GitHub contents API) -- unlike
  the Round 3 situation, no DTB patching from a sibling board is needed as
  a starting point, though the CDC-ECM/gadget bootargs work already done
  may still need to be re-applied or adapted.
- **DMA capability detection is genuinely restored**, confirmed by reading
  the actual file at HEAD: `bool dma_capable = !(hw->arch ==
  GHWCFG2_SLAVE_ONLY_ARCH);` (both call sites in `params.c`), replacing
  our historical fork's hardcoded `bool dma_capable = false;`. Whether the
  T7001's DWC2 instance's hardware register actually reports
  DMA-capable silicon (rather than the driver just being *allowed* to try)
  is an empirical question this project cannot answer without running it
  -- restoring the check makes real DMA *possible*, not guaranteed.
- **The gadget setup mechanism is structurally different, not just
  reconfigured**: confirmed by fetching the actual `config_16k` example
  config, `CONFIG_USB_ETH` (the legacy compile-time composite gadget this
  project has been tuning since Round 6) **is not set at all**. Instead:
  `CONFIG_USB_GADGET=y`, `CONFIG_USB_CONFIGFS=y` with
  `CONFIG_USB_CONFIGFS_ECM=y`, `_NCM=y`, `_ACM=y`, `_EEM=y`, and
  explicitly `# CONFIG_USB_CONFIGFS_RNDIS is not set`. This means the
  entire RNDIS-vs-EEM-vs-ECM Kconfig fight from Rounds 6-7 doesn't apply
  here at all -- the gadget function is assembled at runtime by userspace
  writing to `/sys/kernel/config/usb_gadget/`, not selected at compile
  time. It also means our own `debug_initrd.img`'s existing
  `setup_usb_network_configfs()` path (which already exists in
  `init_functions.sh` and already failed harmlessly in every round so far
  with `"UDC core: g1: couldn't find an available UDC or it's busy"`)
  would likely start actually succeeding on this kernel, since there is
  no legacy `g_ether` present to have already claimed the only UDC first.
  This needs verifying on hardware, not assumed.
- **4 KiB pages still applies, confirmed directly from the current setup
  guide** (not inferred): "if you use A7 - A8, then search for
  `CONFIG_ARM64_4K_PAGES` and enable that instead of
  `CONFIG_ARM64_16K_PAGES`." The `config_16k` filename is just the example
  config's name (defaults to 16K for A9-A11/T2); it is explicitly *not* a
  claim that A8X needs 16K pages. This matches, rather than contradicts,
  this project's already-established 4K-pages finding.
- **Toolchain**: the setup guide's Linux build instructions specify `make
  -j$(nproc) LLVM=1 ARCH=arm64 ...` -- a Clang/LLVM kernel build, not the
  GCC cross-toolchain this project's `buildLinux`-based Nix packages have
  used for every kernel so far (including the 5.19-rc1 historical one,
  which cross-compiles fine with GCC). Mainline aarch64 kernels generally
  support both toolchains, so GCC cross-compilation may well still work,
  but this is an unverified assumption inherited from copying the existing
  `kernel/historical.nix` pattern -- worth trying GCC first since it's the
  path of least Nix-side change, but switching the Nix kernel build to an
  LLVM-based toolchain (nixpkgs supports this) is the fallback if GCC
  build fails or produces something that doesn't boot.

### Concrete plan for the `main`-branch implementation

1. Add `hoolockLinux719` (name pending) as a proper flake input pinned to
   `6831bc701a6ce059e71e5aaa9488c9195bea6927`, fetched on the Mac like
   every other kernel-source input this project uses (`linuxApple519`
   already sets this precedent) -- never let the offline `x86_64-linux`
   builder try to resolve it itself.
2. Add a new `kernel/hoolock.nix`, modeled on `kernel/historical.nix`'s
   defconfig-installation pattern, but starting from `config_16k` with
   `CONFIG_ARM64_4K_PAGES` swapped in for `CONFIG_ARM64_16K_PAGES` (the
   same `sed`-on-a-derivation technique already used for
   `patchedHistoricalConfig` in `flake.nix`).
3. Point `m1n1-control`'s DTB source at this tree's own
   `t7001-j81.dts`/`.dtb` instead of the historical kernel's -- check
   first whether it needs the same `cpu-release-addr` treatment Round 5
   found necessary (mainline convention predeclares it, so this newer
   DTB may already be fine, but confirm rather than assume).
4. First build target: does it boot at all, to the same interactive shell
   milestone already proven on the historical kernel? This alone
   re-validates the whole boot chain (m1n1, PMGR power domains, AUSB PHY
   calibration handoff) against a very different kernel tree before
   USB networking is even in scope.
5. Only once that boots: adapt (or replace) the initramfs's USB gadget
   setup for the configfs-only mechanism this kernel expects, and re-run
   the same diagnostic methodology (ideally reusing
   `m1n1-usb-diagnostic`'s approach) to check whether TX to host actually
   works this time.
6. Keep the existing `historicalKernel`/`m1n1-control` outputs intact
   throughout as the working rollback control, exactly as
   `patchedHistoricalConfig` and `m1n1-usb-diagnostic` already do relative
   to each other.

### Implementation progress, 2026-09-07: steps 1-2 done, kernel builds cleanly

Executed steps 1-2 of the plan above, same day as the research and
decision. Working notes on what actually happened, including two build
failures and their fixes -- both real, both narrow, neither a dead end:

- Added `hoolockLinux` as a flake input, pinned to
  `6831bc701a6ce059e71e5aaa9488c9195bea6927` (the exact commit verified
  above), fetched on the Mac via `nix flake lock --update-input
  hoolockLinux` -- same pattern as every other kernel-source input.
- Added `kernel/hoolock.nix`, directly modeled on
  `kernel/historical.nix`'s named-defconfig pattern: copies the source
  tree, installs a config as `arch/arm64/configs/ipad_t7001_hoolock_defconfig`,
  builds with `buildLinux`. `version`/`modDirVersion` set to `7.3.0-rc1`
  (matching the `Makefile` fields read during research), `buildDTBs =
  true`.
- The `config_16k` example config is reused directly from the *existing*
  `hoolockDocs` flake input (already pinned for the PongoOS binaries) --
  no new input needed for it, just the same `sed`-on-a-derivation
  patching technique as `patchedHistoricalConfig`, applied to swap in
  `CONFIG_ARM64_4K_PAGES`.

**First build attempt failed immediately**, before any compilation: Nix's
git-tracked-flake evaluation couldn't see the new, not-yet-`git add`-ed
`kernel/hoolock.nix` file. Fixed with `git add -N kernel/hoolock.nix`
(intent-to-add, without actually staging content) -- a mechanical Nix/git
interaction issue, not a real bug.

**Second build attempt got much further -- compiled thousands of files
across most of the kernel tree (all of `net/*`, `arch/arm64/kernel`,
etc.) -- then failed with a generic, uninformative `make: ***
[Makefile:248: __sub-make] Error 2`.** The default `nix build -L` log
(and even `nix-store -l` on the failed derivation afterward) only
retained a small tail of the actual output -- entirely unrelated `net/*`
compile lines with no visible error text anywhere in what was kept,
because GNU Make's parallel job scheduler had already dispatched many
`net/*` compiles before the real failure occurred elsewhere in the tree,
and by the time the build aborted those already-in-flight jobs had pushed
the actual error out of whatever tail Nix retained. Retrying with `nix
build --cores 1` to get a serial, easy-to-read log was the wrong fix (far
too slow -- kernel builds without parallelism can run for hours); the
right fix was redirecting `nix build -L`'s own stdout/stderr directly to
a local file (`> build.log 2>&1`, capturing the client-side stream rather
than relying on post-hoc log retrieval) with a smaller-but-nonzero
`--cores 4`, which surfaced the real error cleanly:

```
../drivers/video/backlight/apple_pmic_bl.c:68:1: error: control reaches
end of non-void function [-Werror=return-type]
make[5]: *** [../scripts/Makefile.build:290: drivers/video/backlight/apple_pmic_bl.o] Error 1
```

Fetched the actual source: `apple_pmic_bl_get_brightness()`'s `switch
(data->type)` covers both enumerators of `enum apple_pmic_type`
(`PMIC_TYPE_ANYA`, `PMIC_TYPE_ARIA`) but has no `default:` case, so GCC
can't statically prove every path returns a value and flags it under
`-Werror=return-type`. This is exactly the class of GCC-vs-Clang
divergence the "Toolchain" note above was worried about (Hoolock's own
build guide recommends `LLVM=1`) -- but narrower and easier to fix than
switching this project's entire kernel toolchain: `apple_pmic_bl` is
backlight control, unrelated to the USB investigation this kernel is
being evaluated for. Rather than patch vendored driver source, disabled
it at the config level (`CONFIG_BACKLIGHT_APPLE_PMIC=y` ->
`# CONFIG_BACKLIGHT_APPLE_PMIC is not set`, found via `config_16k`'s own
`grep -i backlight` and the driver's `Kconfig` entry). GCC cross-compiles
the rest of the kernel without any other source-level issue found so far.

**Third build attempt succeeded completely**: `Image` (18 MB),
`System.map`, and a full `dtbs/apple/` directory, including
`t7001-j81.dtb` and `t7001-j82.dtb` for this project's exact board and
its cellular sibling. GCC cross-compilation is viable for this kernel
after all -- the earlier "may need to switch to LLVM" concern from the
research phase turned out to be a single fixable file, not a fundamental
toolchain incompatibility.

**Inspected the built `t7001-j81.dtb` directly** (`dtc -I dtb -O dts`,
not assumed): `#address-cells = <0x02>` with correct two-cell `reg`
values, and -- unlike the historical kernel's DTB, which needed all of
this hand-patched across Rounds 3-5 -- `cpu@0`/`cpu@1`/`cpu@2` already
carry both `cpu-release-addr = <0x00 0x00>` *and* `enable-method =
"spin-table"` as proper mainline-convention placeholders. None of the
CPU-related DTB patching this project spent three rounds developing is
needed for this kernel's own DTB. It does still have `/chosen/framebuffer@0`
(a unit address on the node name) rather than the exact `/chosen/framebuffer`
path m1n1's `dt_set_fb()` looks up via `fdt_path_offset()` -- the same
situation as the *modern mainline* DTB back in Round 3, which needs the
same one-line rename fix already proven there.

### Wired into a bootable payload, 2026-09-07: `m1n1-hoolock-control`

Added `m1n1-hoolock-control` to `flake.nix`, directly parallel to
`m1n1-control`: same `Pongo.bin`/`m1n1.bin` (kernel-agnostic, already
proven), this kernel's own `Image` and DTB, and the same
`debug_initrd.img` base as every other payload.

**DTB**: applied the one framebuffer-rename patch identified above
(`framebuffer@0 {` -> `framebuffer {`, scoped to the `chosen {}` block so
it can't collide with anything else) via the same
decompile/`sed`/recompile technique used throughout this project.
Confirmed by decompiling the built output: the node is `framebuffer {`
at the exact path m1n1 needs, with `cpu-release-addr`/`enable-method`
still intact from the kernel's own DTB (no CPU patching needed, as
established above).

**Gadget setup**: chose to override `deviceinfo_usb_rndis_function` to
`ecm.usb0` (was going to default to `rndis.usb0`, which needs
`CONFIG_USB_CONFIGFS_RNDIS` -- not compiled into this kernel) via a
one-line addition to `/etc/deviceinfo`, applied as a second cpio overlay
entry appended to the same `initramfs.cpio` stream (concatenated newc
archives, same mechanism `m1n1-usb-diagnostic` already uses for its debug
hook, just targeting a different file this time). The *original*
`etc/deviceinfo` is extracted from the pinned `debug_initrd.img` inside
the build itself rather than hardcoded, so this can't drift from
upstream if that input ever changes.

Two real, narrow build bugs hit and fixed while wiring the overlay,
both in the `cpio` invocation, not the underlying design:

1. First attempt: `cpio: etc/deviceinfo: Cannot open: No such file or
   directory`. GNU `cpio -i` does not create leading directories by
   default -- needs the `-d`/`--make-directories` flag, which the
   already-proven `m1n1-usb-diagnostic` overlay never needed because its
   target directory (`etc/postmarketos-mkinitfs/hooks/`) happens to
   already exist elsewhere in that archive by the time it's referenced.
   Extracting into a path whose parent doesn't exist yet needs `-d`
   explicitly. A wrong first guess (that the archive stored entries with
   a `./` prefix, based on misreading the archive-parsing Python script's
   *own* `removeprefix("./")` defensive normalization as evidence the
   prefix was actually present) briefly went down the wrong path before
   directly listing the archive's real contents (`cpio -t`) settled it:
   the entry is genuinely stored as `etc/deviceinfo`, no leading `./`.
2. Second attempt (fixed directory creation but reverted to the wrong
   `./`-prefixed pattern from the first wrong guess): silently extracted
   nothing (pattern matched no entries, no error printed), so the
   subsequent `cp` failed with a plain "No such file or directory."
   Fixed by using the confirmed-correct bare pattern (`etc/deviceinfo`)
   together with `-d`.

**Verified the override actually applies**, not just that the build
succeeds: parsed the built `initramfs.gz`'s concatenated cpio streams
with the same last-entry-wins logic `test_usb_diagnostic.py` already uses
(matching how the Linux kernel's own initramfs unpacker resolves
duplicate names -- confirmed distinct from plain userspace `cpio -i`,
which by default skips re-extracting a file it doesn't consider newer,
and gave a misleading "override missing" result on a first, wrong,
verification attempt using that tool directly). The parsed result
confirms `deviceinfo_usb_rndis_function="ecm.usb0"` is present in the
version that will actually land at boot.

**Kept the same bootargs baseline as `m1n1-control`**
(`PMOS_NO_OUTPUT_REDIRECT pd_ignore_unused clk_ignore_unused`, plus the
usual console/rdinit basics) -- this DTB's framebuffer node carries a
`power-domains` reference (unlike the historical kernel's DTB, which had
none), so the same PMGR genpd auto-shutdown risk Round 2 found plausibly
applies here too; kept as a safety net rather than assumed unnecessary.

**Status**: `m1n1-hoolock-control` builds cleanly and every static check
available without hardware passes. No hardware boot attempt yet -- that
is the immediate next step.

### Overnight, 2026-09-08: bundled build-ready RTC/backlight drivers on this same kernel -- unrelated to USB

While waiting for a hardware window, the project owner authorized
bundling any driver that's "already exists, needs to get bundled only or
similar low level effort," explicitly excluding new driver development
and anything that would disrupt this USB work. A full survey (see
`research/driver-gap.md`'s 2026-09-08 update for the complete
per-subsystem breakdown) found touch and WiFi both need genuine new
driver/controller work, and Bluetooth needs a new DT node plus firmware
extraction -- but RTC and backlight,
both on the same Apple PMIC, were already fully wired (enabled DT node,
matching in-tree driver) and only blocked by the exact same
`-Werror=return-type` class of GCC build bug already fixed once tonight
for the *different* PMIC backlight driver problem in Round 6-7's
research. Fixed properly this time (a 2-line `default: return -EINVAL;`
case added to `apple_pmic_bl_get_brightness()`'s switch in
`kernel/hoolock.nix`'s `configuredSource`, rather than disabling the
driver) and re-enabled `CONFIG_BACKLIGHT_APPLE_PMIC` in
`patchedHoolockConfig` (RTC's `CONFIG_RTC_DRV_APPLE_PMIC` was already `y`
in Hoolock's own published config, no change needed there).

Rebuilt `hoolockKernel` and `m1n1-hoolock-control` fully after this
change and re-ran every static check already established above: kernel
builds clean, both Kconfig symbols confirmed `=y` in the built `.config`,
and the framebuffer-rename/deviceinfo-override checks on the rebuilt DTB
and initramfs still pass identically. This changes the kernel `Image`
hash but touches nothing USB-related (backlight and RTC are unrelated
PMIC peripherals, not on the USB/DTB/CPU code paths this investigation
touches). The payload now includes RTC and backlight support at no cost to the
USB test it exists for. Neither peripheral is reported as working until the
payload is tested on the physical iPad. The broader driver work was authorized
later on 2026-09-08 and now follows the dated plan in `docs/plans/`.
