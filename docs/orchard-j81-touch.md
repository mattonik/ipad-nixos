# J81 touch in the Orchard kernel payload

`m1n1-orchard-touch` builds Orchard's J81 kernel with the bounded T7000 SPI
transfer and N1 touch fixes from Orchard PRs
[#57](https://github.com/OrchardLinux/orchard/pull/57) and
[#60](https://github.com/OrchardLinux/orchard/pull/60). The Orchard Linux source
is pinned in `flake.lock`; the four local patches keep this image reproducible
until those PRs are merged. The existing `m1n1-hoolock-wifi` image stays separate.

The public payload contains `apple_z2.ko`, four Wi-Fi modules, and the J81 DT
node. Its boot hook loads those modules. The 15.8.8 touch firmware is private.
The assembler checks its size and
SHA-256 against the firmware that yielded continuous contacts on the live iPad.
It places that firmware in the private initramfs overlay alongside the Wi-Fi
assets and credentials. No firmware or credentials enter Git or the Nix store.

Build the public payload with the shared VM lock:

```sh
BUILDER_DIR=/path/to/ipad-nixos tools/builder.sh build --wait --who j81-touch \
  .#packages.x86_64-linux.m1n1-orchard-touch -o artifacts/live/gcroot-orchard-touch
```

Then assemble it with the existing private Wi-Fi assets and the exact J81 15.8.8
touch firmware (the `.z2fw` output of Orchard's `devices/j81/firmware.json` recipe):

```sh
python3 boot/assemble_private_wifi_payload.py \
  --public artifacts/live/gcroot-orchard-touch \
  --assets /path/to/private/wifi-assets \
  --production \
  --touch-firmware /path/to/private/j81-fwstart.z2fw \
  --out artifacts/live/private/j81-orchard-touch
python3 boot/assemble_private_wifi_payload.py --verify \
  artifacts/live/private/j81-orchard-touch
```

Boot the verified private image with `boot/run_m1n1_debug.sh` after a fresh boot
go. Check `/proc/bus/input/devices`, `/proc/interrupts`, and `evtest` for contacts.
The prior live module test measured 2,914 `SYN_REPORT` events during 30 seconds
of swiping, about 97 reports/s, with no new frame errors. The rebuilt image still
needs a physical boot test, including Wi-Fi; that measurement was from a live module swap.
