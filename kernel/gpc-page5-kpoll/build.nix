# Build against the exact kernel tree of the booted PMGR cycle payload.
# The flake's kernel has moved on since that payload was built, so its
# current .dev output no longer matches the payload's /sys/kernel/notes
# (82ff70e8...). The matching tree is pinned by store path instead; check it
# with: python3 boot/kernel_notes_sha256.py <kernelDev>/vmlinux
{ repo }:
let
  packages = (builtins.getFlake ("git+file://" + toString repo)).packages.x86_64-linux;
  base = packages.hoolock-wifi-kmod-kernel;
  kernelDev = builtins.storePath "/nix/store/qwrk3jddqk96792s1k5aasxw2mkxc8gw-linux-aarch64-unknown-linux-gnu-7.3.0-rc1-dev";
in packages.j81-kmod-spi-apple.overrideAttrs (old: {
  pname = "j81-kmod-gpc-page5-kpoll";
  src = builtins.path { path = ./.; name = "gpc-page5-kpoll-src"; };
  makeFlags = map (flag: builtins.replaceStrings [ "${base.dev}" ] [ "${kernelDev}" ] flag) old.makeFlags;
})
