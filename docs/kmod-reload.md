# Driver reload without a DFU cycle

Touch work changes one driver at a time, but every change used to cost a full
kernel build and a DFU boot. This loop rebuilds only the driver and swaps it on
the booted iPad. It follows what OrchardLinux does for module and DTB edits
(`src/orchard/kernel_sdk.py`: build against an exported kernel SDK, then
`orchard push`). Orchard has no live kernel replacement and avoids kexec on
purpose, and so do we. See `research/2026-11-01-orchardlinux-org-review.md`.

## Pieces

| Piece | Where |
|---|---|
| Modular kernel: the production Wi-Fi kernel plus `CONFIG_MODULE_UNLOAD=y`, `CONFIG_SPI_APPLE=m`, `CONFIG_TOUCHSCREEN_APPLE_Z2=m` | `hoolockWifiKmodKernel`, package `hoolock-wifi-kmod-kernel` |
| Payload: `m1n1-hoolock-wifi-touch` on that kernel (spidev child on SPI3, 64 KiB spidev buffer) | `m1n1-hoolock-wifi-touch-kmod` |
| Out-of-tree build of one module against the kernel's `dev` output; rebuilds the module only | `mkJ81Kmod`, packages `j81-kmod-spi-apple`, `j81-kmod-apple_z2` |
| The kernel's own module source (after all our patches), the starting point of a work copy | `j81-kmod-src-spi-apple`, `j81-kmod-src-apple_z2` |
| The loop | `tools/kmod.sh` |

Everything else, `brcmfmac` included, stays built in. Reloading `brcmfmac` after
a failed probe reset an iPad 6 once (Orchard `docs/integration/j71t.md`), and
`tools/kmod.sh` refuses it.

## Loop

Assemble and boot `m1n1-hoolock-wifi-touch-kmod` like `m1n1-hoolock-wifi-touch`
(`boot/assemble_private_wifi_payload.py`, then `boot/run_m1n1_debug.sh`). With the
SPI controller as a module, SPI3 and `/dev/spidev0.0` do not exist yet after boot.
Then:

```sh
tools/kmod.sh stock spi-apple      # first load: the unmodified driver; /dev/spidev0.0 appears
tools/kmod.sh extract spi-apple    # work copy in artifacts/kmod/spi-apple/ (git-ignored)
$EDITOR artifacts/kmod/spi-apple/spi-apple.c
tools/kmod.sh build spi-apple      # seconds once the kernel's dev output is built
tools/kmod.sh load spi-apple       # copy (SHA-256 checked), rmmod, insmod, print dmesg
# ... run touch-diag as before, edit, build, load again ...
tools/kmod.sh diff spi-apple       # the change, ready to become kernel/patches/NNNN-*.patch
tools/kmod.sh stock spi-apple      # back to the unmodified driver
```

A module only loads into the kernel it was built against, so the iPad must run a
payload built on `hoolockWifiKmodKernel`. The first `build` or `stock` builds that
kernel once; after that only the module is compiled. Measured 2026-11-01: a
`build` after an edit takes about 54 s, nearly all of it the round trip to the
builder VM (the flake evaluates in about 1 s). A full kernel build plus a DFU
cycle costs far more. The kernel `dev` output and the payload have GC roots
(`artifacts/live/gcroot-wifi-kmod-kernel-dev`, `artifacts/live/gcroot-wifi-touch-kmod`).

Verified at build time: the modules carry `vermagic=7.3.0-rc1 SMP preempt mod_unload
aarch64`, and the kernel's `System.map` has no `spi_apple` symbol, so the controller
really is a module. Not yet run on the iPad.

`load` uses the USB SSH link (`root@172.16.42.1`, key `artifacts/live/ssh/ipad_ed25519`;
override with `IPAD` and `IPAD_KEY`). It writes `/tmp/NAME.ko` on the iPad, which
lives in RAM.

## Rules

- A reloaded module is an **incremental** result (CLAUDE.md, fast loop step 4).
  When it matters, turn `diff` into a patch, add it to the kernel's patch list and
  do the reproducible Nix build before recording the result as evidence.
- Hardware results from the loop are still committed immediately, with the
  module's SHA-256 (printed by `load`) as the payload identity.
- Touch transport experiments (bit order, CFG word, PIO/DMA) are parked
  (`research/2026-10-12-touch-rom-states.md`). The loop makes them cheap, but
  running one still needs Martin's go-ahead.
