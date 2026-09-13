# J81 ANS1 storage: observation-only safety patch

Date: 2026-09-13

Target: iPad Air 2 Wi-Fi, J81/J81AP, A8X/T7001

Base: Hoolock's `ans1` Linux branch, pinned at `ed8528f482a526371e59711645794c91fafb2b42`
(the same commit already compile-verified in isolation, see
`research/j81-long-term-subsystems.md`'s "Internal NAND storage" section and
`kernel/hoolock-ans1-check.nix`).

**Status: first hardware test passed, 2026-09-13.** All ten ASP namespaces
probed and registered read-only on real J81 hardware, a real single-block
read succeeded, and no crash indicator of any kind appeared. See "First
hardware test result" below for the full evidence.

**Status (superseded by the above): combined bootable test payload cross-build verified, 2026-09-13.**
The six-item observation-only hardening below is implemented as
`kernel/patches/0012-ans1-asp-observation-only.patch` and cross-build
verified in isolation (`hoolock-ans1-check-kernel`). ANS1 has since been
reconciled onto this project's own working tree (not ans1's source
directly) as a **separate, dedicated payload**
(`packages.x86_64-linux.m1n1-hoolock-ans1-test`, built from
`kernel/hoolock-ans1-test.nix`) -- deliberately not merged into
`kernel/hoolock.nix`/`m1n1-hoolock-control`, so ANS1 is only ever exercised
when this specific test payload is chosen, never as a side effect of
routine touch/battery work on the default payload. The full combined tree
(BT-1, BAT-1/2/3, CHG-1, TOUCH-1/2 groundwork, plus the hardened ANS1
storage driver, all together) now cross-builds successfully. No hardware
has been touched.

## Combined cross-build result, 2026-09-13

`nix build .#packages.x86_64-linux.m1n1-hoolock-ans1-test` succeeds and
produces a complete payload (`Pongo.bin`, `m1n1.bin`, `Image.gz`,
`t7001-j81.dtb`, `initramfs.gz`, `m1n1-linux.bin`, `SHA256SUMS`), same
structure as `m1n1-hoolock-control`. Verified, not assumed:

- `apple_asp_probe`, `apple_asp_start_disk`, and `apple_asp_of_match` are
  present in the built kernel's `System.map` (exposed for direct
  inspection as the new `packages.x86_64-linux.hoolock-ans1-test-kernel`
  output) -- the ANS1 driver is genuinely compiled in. The smaller static
  helpers the hardening patch touches (`asp_setup_cmd`, `asp_setup_rw`,
  `apple_asp_submit_cmd`) don't appear as separate symbols because GCC
  inlines them at `-O2`; this is expected for small single-caller static
  functions, not a sign they were dropped.
- The rest of the payload is intact in the same build: `bq27xxx_battery_*`
  (battery/HDQ) and `apple_z2_probe`/`apple_s5l_spi_irq` (touch/SPI3) are
  all still present in `System.map`, and the DTB carries both
  `t7001-j81.dtb` device nodes as before.
- The default `m1n1-hoolock-control` payload was rebuilt from the same
  `flake.nix` afterward and its `m1n1-linux.bin` SHA-256
  (`2acd7c1719b3425f47cc77a1db9c663351f6896005ac3540aede1d331c9f2345`)
  matches the value recorded before any of this session's ANS1 work --
  byte-for-byte unaffected, confirming the isolated-payload approach
  actually holds in practice, not just by inspection of the Nix
  expressions.

**Build bug hit and fixed**: the first two build attempts failed
reproducibly with `Permission denied` trying to write to
`patchedHoolockAns1TestConfig`'s own output path. Root cause:
that derivation used `cp ${patchedHoolockConfig} "$out"` to seed the
config from an existing Nix store path, and plain `cp` preserves the
source's permission bits -- Nix store paths are read-only
(`-r--r--r--`), so `$out` came out read-only and the following
`echo ... >> "$out"` line failed. Fixed by using
`cat ${patchedHoolockConfig} > "$out"` instead: shell redirection always
opens/creates the destination fresh (subject to umask, not the source's
mode), so the file is writable for the following line. Not a problem with
the patches or the kernel tree at all -- purely a Nix plumbing detail in
how this one config derivation was assembled.

## Reconciling ans1 onto this project's own tree

`ans1` is 27 commits ahead of this project's pinned `hoolockLinux` base and
touches 19 files. Rather than build it as isolated source (as
`kernel/hoolock-ans1-check.nix` does for the compile-only check), getting a
*bootable* payload means merging those changes onto this project's own
already-patched tree. Verified this empirically before writing anything,
using a real local clone and the actual `patch` tool, not assumed:

- **17 of 19 files apply cleanly with zero conflicts** on top of this
  project's full existing patch stack (0001-0011) -- the new driver
  (`drivers/block/asp.c`), the shared RTKit/AKF-mailbox/macsmc framework
  changes it needs, the new devicetree binding doc, and unrelated SoC/board
  dtsi files this project doesn't otherwise touch. Written as
  `kernel/patches/0015-ans1-storage-driver-and-core-support.patch`.
- **Only `t7001.dtsi` and `t7001-air2.dtsi` needed reconciliation**, and
  only one line was a genuine conflict: both `ans1` and this project's own
  `0001` patch add an entry to the same short SoC-level `aliases` block.
  Not a semantic conflict -- two community patches happened to touch the
  same short list -- resolved by hand and re-verified by re-running the
  full 15-patch stack from a clean checkout with zero rejects anywhere.
  Written as `kernel/patches/0013-t7001-add-ans1-node.patch` (SoC-level,
  disabled -- same pattern as this project's own UART3/UART5/SPI3 patches)
  and `0014-t7001-air2-enable-ans1.patch` (board-level enable).
- Applied in the order 0001-0011, 0013, 0014, 0015, then 0012 (the
  hardening, last, so it patches the driver 0015 just introduced) --
  `kernel/hoolock-ans1-test.nix` mirrors `kernel/hoolock.nix` exactly for
  the first eleven, differing only in adding the last four.

## What this is for, in plain terms

The upstream `asp.c` driver (Nick Chan's ANS1/ASP storage-controller work)
is real and compiles cleanly, but its default behavior on real hardware is
to unlock writes to the iPad's actual internal storage -- the same NAND
that holds real iOS data -- as an unconditional side effect of a successful
probe, with no config-time way to turn that off. This document's job is to
turn that default off before this driver is ever run against real J81
hardware. It does **not** make storage usable, and nothing in it is tested
against the device -- this is a code-only, compile-verified change, the
same rigor already used for TOUCH-1's controller port.

## Exact changes, matching `research/j81-long-term-subsystems.md`'s
"patch ASP into observation-only mode" list item by item

Status column updated as each lands.

| # | Requirement | Status |
| --- | --- | --- |
| 1 | Remove the `WRITE_UNLOCK` command | **done** -- the submission is deleted outright, not gated behind a flag |
| 2 | Reject all block writes/flushes that could mutate media | **done** -- centralized in `asp_setup_cmd()`, one dispatch point every namespace's requests pass through |
| 3 | Mark the user area and every auxiliary namespace read-only | **done** -- `USERAREA` added to the existing `set_disk_ro()` block; every namespace this driver exposes is now covered, no exceptions |
| 4 | Replace reachable fatal assertions with errors that offline the disk | **done** -- all 3 `BUG()`/`BUG_ON()` call sites now `WARN_ON()` plus a graceful `blk_status_t` error (or an early return before the actual out-of-bounds write, for the one that returns `void`) |
| 5 | Omit any format path from the test build | **confirmed already inert** -- checked directly, not assumed from the TODO comment: no format path exists in this source at all, only a `// TODO support auto reformat` describing something never implemented; unformatted media is already refused with an error |
| 6 | Cross-build verify (isolated, same as the unmodified compile check) | **done**, 2026-09-13 -- `apple_asp_probe`/`apple_asp_start_disk`/`apple_asp_of_match` all confirmed present in the hardened build's `System.map`; the driver is still genuinely compiled in, not stubbed out by the safety changes |

## Why each one, specifically -- read directly from `drivers/block/asp.c`

- **`WRITE_UNLOCK`** (~line 816 in the pinned commit): `apple_asp_probe()`
  unconditionally issues `ASP_CMD_WRITE_UNLOCK` for every namespace as part
  of normal probe, immediately followed by the driver's own comment
  admitting "putting the wrong things in some of them could cause
  persistent controller crashes." This is the single most important line
  to remove -- without it, the controller itself should refuse writes at
  the firmware level regardless of what Linux's block layer does above it.
- **Block-layer write rejection**: defense in depth in case (1) alone
  doesn't hold for some reason not yet understood (this is unfamiliar,
  externally-authored code) -- the driver's own request-submission path
  should refuse to even construct a write command.
- **`set_disk_ro()` on every namespace**: currently only the LLB namespace
  gets this after probe; the user-data area and every auxiliary namespace
  (firmware, util-DM, DM, ctrl-bits, efface, NVRAM, syscfg, panic-log) do
  not. A third, independent layer.
- **`BUG()`/`BUG_ON()` -> graceful errors**: three `BUG()` calls sit in
  default-case switch branches on internal enum values (queue type,
  command classification) -- "should be unreachable" assertions, not
  something normal read-only operation would trip, but a real kernel panic
  if ever wrong. Downgrading these to a logged error plus offlining the
  disk means a driver bug degrades to "this disk stopped working," not
  "this kernel is now unusable."
- **No format path**: `apple_asp_probe()` already refuses unformatted media
  with an error (`!identify->util_formatted` check) rather than offering to
  format it, and the only format-related code is a `// TODO support auto
  reformat` comment describing something not yet implemented. Checking
  this is really as inert as it looks, not assuming it from the TODO text
  alone.

## First hardware test procedure (read-only only)

Written before running it, per this project's own discipline. Uses the
standard boot recipe (README.md's "Boot status") with the ANS1 test
payload in place of `m1n1-hoolock-control`:

```bash
nix build .#packages.x86_64-linux.m1n1-hoolock-ans1-test -o result -L
shasum -a 256 result/m1n1-linux.bin
sudo boot/vendor/palera1n-macos-arm64 --pongo-shell \
  --override-pongo "$PWD/result/Pongo.bin" --debug-logging
# reconnect the cable once at Checkmate!, once at the Pongo logo
nix develop -c python3 boot/load_m1n1.py result/m1n1-linux.bin
```

Once the telnet shell answers, `boot/ipad_console.py` gained two actions
for this test:

- **"Storage (ANS1): probe status + ro flags"** -- dmesg for the ASP
  probe, then reads `/sys/block/asp0n{1..10}/ro` for every namespace
  (USERAREA through PANICLOG). All ten must read `1`; anything else means
  the hardening isn't actually in effect on this boot and the test stops
  there.
- **"Storage (ANS1): safe single-block read test"** -- refuses to touch a
  device at all unless its own `ro` sysfs entry already reads `1`, then
  reads exactly one 4096-byte logical block (`dd bs=4096 count=1
  if=/dev/asp0nN of=/dev/null`) -- never anything larger, never to a real
  file, never a write.

**Stop conditions** -- do not go further than the two actions above if any
of these show up; note it, revert to the known-good payload, and treat it
as a real finding, not something to push past:

- any `ro` value other than `1` on any of the ten namespace devices;
- a kernel panic, oops, or `BUG`/`WARN_ON` splat during or after probe;
- the read test hanging past its 10-second timeout instead of returning;
- anything reachable in dmesg mentioning `WRITE_UNLOCK` outside of a
  comment (there should be none at all -- the command was deleted, not
  gated).

**Pass criterion**: `apple_asp_probe` completes, all ten `asp0n*` devices
appear with `ro=1`, and the single-block read on at least one of them
(USERAREA, `asp0n1`, is the most interesting namespace) returns real data
with no new dmesg errors. That would be the first real evidence this
driver and its hardening behave as designed against actual J81 hardware,
not just in cross-compilation.

## First hardware test result: passed, 2026-09-13

Booted `m1n1-hoolock-ans1-test` (`m1n1-linux.bin` SHA-256
`bc448757e849080c185d2717094a452ea7db23785f0808382426580a302b6e05`) on
the real J81. Every check above passed cleanly:

- `apple-asp 208040000.block` (the ASP node `0013`/`0014` add) came up and
  its RTKit firmware channel is genuinely live -- dmesg shows real
  `Util_Host` syslog traffic from the firmware itself identifying every
  namespace (EFFACE, NVRAM, SYSCFG, PANICLOG, LLB, UTILDM, CTRLBITS, FW,
  DM), including expected boundary responses ("LBA offset beyond end",
  "not yet written") for empty/unformatted regions -- this is the
  firmware's own identify-time protocol chatter, not driver error paths.
- **All ten `asp0n{1..10}` block devices registered with `ro=1`** --
  confirmed by reading `/sys/block/asp0nN/ro` directly on the device, not
  inferred. `asp0n1` (USERAREA) reports a capacity of 250,000,000
  512-byte sectors = 128 GB, a real, plausible capacity for this iPad Air
  2 model -- further evidence the identify sequence is reading genuine
  device state, not stub/zero values.
- **Zero occurrences of `WRITE_UNLOCK` anywhere in dmesg** -- confirms the
  command really was never issued, not just absent from the visible log
  tail.
- **Zero real crash indicators** -- a targeted dmesg search for `kernel
  panic`, `oops`, `call trace`, `WARNING: CPU`, and exception strings
  returned nothing. (An earlier broad `grep -i panic` had matched only
  the substring inside `PANICLOG` -- a false positive from the search
  itself, not a near-miss; worth noting so it isn't mistaken for a close
  call in hindsight.)
- **The gated safe read test passed**: the test script re-checks
  `ro=1` on `asp0n1` itself immediately before reading (not just trusting
  the earlier status check), then reads exactly one 4096-byte logical
  block with `dd if=/dev/asp0n1 of=/dev/null bs=4096 count=1` --
  `1+0 records in / 1+0 records out`, no I/O error, no new dmesg lines at
  all afterward (expected: successful block reads aren't logged by
  default, only errors are). The actual returned bytes were deliberately
  never inspected or printed anywhere -- proving the read path works
  doesn't require handling the disk's real content, and USERAREA is real
  user data.
- System remained stable throughout: 3 minutes uptime, no crash loop, no
  repeated USB re-enumeration beyond the one expected reconnect during
  the kernel's own gadget bring-up.

**This closes the ANS1 storage line of work at its currently intended
scope**: the driver is confirmed to probe cleanly, expose every namespace
read-only, never issue the unlock command, and service a real read
against actual J81 hardware, all without a single crash indicator. Making
the storage actually *usable* (a real filesystem, write support, is a
different and much larger undertaking than this project has scoped) is
future work, not implied by this result.

## What this explicitly does not include

- No write support, and no attempt to make the storage actually usable
  (filesystem mount, etc.) -- the entire point so far is proving the
  read-only path is safe and functional, not building a usable storage
  stack. That remains future work if ever wanted.
- No change to whether ANS1 is wired into any actual *default* boot
  payload -- `m1n1-hoolock-control`/`kernel/hoolock.nix` are untouched;
  ANS1 only exists in the dedicated `m1n1-hoolock-ans1-test` payload,
  confirmed not to affect the default payload's build output at all.
