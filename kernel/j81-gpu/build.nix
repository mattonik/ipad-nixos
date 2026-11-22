# Build against the exact kernel tree of the observer payload (kernel notes sha256 a2dda2719fef771c...; the always-on observer Image is byte-identical).
{ repo }:
let
  packages = (builtins.getFlake ("git+file://" + toString repo)).packages.x86_64-linux;
  base = packages.hoolock-wifi-kmod-kernel;
  kernelDev = builtins.storePath "/nix/store/nmjby96k2aqp3yzkbi9qmazk1wmvr1mr-linux-aarch64-unknown-linux-gnu-7.3.0-rc1-dev";
in packages.j81-kmod-spi-apple.overrideAttrs (old: {
  pname = "j81-kmod-gpu";
  src = builtins.path { path = ./.; name = "j81-gpu-src"; };
  makeFlags = map (flag: builtins.replaceStrings [ "${base.dev}" ] [ "${kernelDev}" ] flag) old.makeFlags;
})
