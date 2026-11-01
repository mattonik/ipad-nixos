# m1n1 from source

Since 2026-11-01 the J81 base payloads (everything built through
`mkJ81BasePayload` in `flake.nix`: `m1n1-hoolock-wifi`, `-wifi-touch`,
`-wifi-nixos` and the rest) use an m1n1 built from source by
`boot/m1n1/default.nix`, instead of the prebuilt `m1n1.bin` from the Hoolock
nightly zip. This follows OrchardLinux (`orchard/boot/m1n1/build`), as
recommended by the [OrchardLinux org review](../research/2026-11-01-orchardlinux-org-review.md).

The older one-off test payloads (`m1n1-control`, `m1n1-hoolock-control`, the
PCIe/ANS1/charging test payloads) still copy the nightly binary
(`inputs.hoolockM1n1`). They are records of what ran on the iPad, so they stay
as they were.

## What is built

| Part | Value |
|---|---|
| Source | `github:HoolockLinux/m1n1/d5a10ac52a6468484854419a6c5130f1d62073eb` (`inputs.hoolockM1n1Src`), the same commit as the nightly zip |
| Patches | `boot/m1n1/patches/0001` and `0002`, copied unchanged from Orchard `boot/m1n1/patches/orchard/0001` and `0003-Forward-touchscreen-proximity-calibration` (Orchard `949a06b`) |
| Toolchain | clang/lld with `USE_CLANG=1`, `CHAINLOADING=1`, Rust 1.90.0 with `aarch64-unknown-none-softfloat` (from `rust-overlay`), as in Orchard's `install-toolchain` |
| Build host | the Mac (`packages.aarch64-darwin.m1n1`); the Linux builder VM is not needed |
| Outputs | `m1n1.bin`, `m1n1-idevice.macho`, `monitor-stub.macho` |
| Version string | `hoolock-d5a10ac-ipad-nixos` (shows up in `/chosen` as `asahi,m1n1-stage1-version` and `asahi,m1n1-stage2-version`) |

```bash
nix build .#m1n1
```

m1n1 is a freestanding aarch64 image, so it is the same kind of binary on any
build host. Building on the Mac also means the cargo crates are fetched with
the Mac's network access. The x86_64-linux payload derivations take the
Darwin-built `m1n1.bin` as an ordinary input.

The binary is not byte-identical to the nightly: the nightly CI used GCC, and
this build uses clang like Orchard does. The source tree, except for the two
patches, is the same.

## What the two patches change

1. **`0001` Fill in A9-A11 device data generically.** Finds `wlan`,
   `bluetooth` and `multi-touch` either directly below `/arm-io` or one level
   down (J81 has `/arm-io/uart2/wlan` and `/arm-io/spi3/multi-touch`). Adds
   `dt_set_touchscreen()`: when the DTB has a `touchscreen0` alias, m1n1 copies
   the ADT multi-touch calibration properties into that node
   (`multi-touch-calibration` becomes `apple,z2-cal-blob`, plus the other
   `apple,z2-*-cal-blob` properties). Values that only say `syscfg/...` are
   skipped. It also makes the Wi-Fi antenna SKU optional, and adds an NVMe
   host-memory-buffer step that runs only when the DTB has an `nvme-hmb` node
   (ours has none).
2. **`0002` Forward proximity calibration.** Adds `prox-calibration` to
   `apple,z2-prox-cal-blob` in the same table.

Side effects for J81, from the source and our earlier ADT notes:

- Wi-Fi: m1n1 now finds `/arm-io/uart2/wlan`, and `wifi0` exists. J81 has no
  `wifi-antenna-sku-info` and no `wifi-calibration-msf`
  ([private firmware assets](../research/j81-private-firmware-assets.md)), so
  nothing new gets written. Before, the lookup failed and m1n1 skipped it.
  The MAC address still comes from the `/chosen` loop, as before.
- Bluetooth: m1n1 now finds the bluetooth node, but our DTB has no
  `bluetooth0` alias, so nothing is written.
- Touch: only the touch payloads (`touchSpidev = true`) get the
  `touchscreen0` alias, pointing at `/soc/spi@20a08c000/touch-diag@0`. Other
  payloads have no alias, so m1n1 skips the step.

## Calibration without files

With the alias in place, the calibration from this iPad's own ADT reaches the
booted kernel as properties of the touch node, readable at
`/proc/device-tree/soc/spi@20a08c000/touch-diag@0/apple,z2-cal-blob`. Nothing
calibration-related has to be extracted, kept in `artifacts/` or committed.
This is the injection point that `docs/plans/2026-09-09-j81-touch-spi3.md`
named in September.

There were no calibration files in the build to remove. The touch tools so
far send no calibration at all (`boot/touch-diag.c`: "no calibration"). The
touch firmware (`firmware/j81-12B410/touch/J81.mtprops` and the upload packets)
is firmware, not calibration, and is still needed.

The `apple_z2` driver reads `apple,z2-cal-blob` once it binds to an
`apple,j81-touchscreen` node. That node is not enabled yet: touch is parked
on the transport question (memory note `touch-status`).

## Hardware check (open)

Nothing here has run on the iPad yet. The first run should:

1. Boot `m1n1-hoolock-wifi-touch` (or the usual production payload) as usual
   and confirm it reaches the same state as the nightly-m1n1 payload: screen,
   USB ECM, ssh, Wi-Fi.
2. Confirm the m1n1 version in
   `/proc/device-tree/chosen/asahi,m1n1-stage2-version` reads
   `hoolock-d5a10ac-ipad-nixos`.
3. On the touch payload, check that
   `/proc/device-tree/soc/spi@20a08c000/touch-diag@0/apple,z2-cal-blob` exists
   and record only its size, never its bytes.

If step 1 fails, the earlier nightly-m1n1 builds of the same payloads are the
control.
