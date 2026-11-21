# Build against the exact kernel tree of the observer payload: kernel notes sha256 a2dda2719fef771c... (the paired bundle j81-observer-paired-20261119-v1).
# Check with: python3 boot/kernel_notes_sha256.py <kernelDev>/vmlinux
{ repo }:
let
  packages = (builtins.getFlake ("git+file://" + toString repo)).packages.x86_64-linux;
  base = packages.hoolock-wifi-kmod-kernel;
  kernelDev = builtins.storePath "/nix/store/nmjby96k2aqp3yzkbi9qmazk1wmvr1mr-linux-aarch64-unknown-linux-gnu-7.3.0-rc1-dev";
in packages.j81-kmod-spi-apple.overrideAttrs (old: {
  pname = "j81-kmod-gpc-page5-kpoll-crumbs";
  src = builtins.path { path = ./.; name = "gpc-page5-kpoll-crumbs-src"; };
  makeFlags = map (flag: builtins.replaceStrings [ "${base.dev}" ] [ "${kernelDev}" ] flag) old.makeFlags;
})
