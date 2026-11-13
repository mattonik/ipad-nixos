# Build against the exact kernel used in the early-DWI hold payload.
{ repo }:
let
  packages = (builtins.getFlake ("git+file://" + toString repo)).packages.x86_64-linux;
  base = packages.hoolock-wifi-kmod-kernel;
  kernelDev = builtins.storePath "/nix/store/w3w2652ya32c3471ayrayspyws03i7xa-linux-aarch64-unknown-linux-gnu-7.3.0-rc1-dev";
  module = name: source: packages.j81-kmod-spi-apple.overrideAttrs (old: {
    pname = name;
    src = builtins.path { path = source; name = name + "-src"; };
    makeFlags = map (flag:
      if builtins.match ".*-linux-aarch64-unknown-linux-gnu-7[.]3[.]0-rc1-dev/.*" flag != null
      then builtins.replaceStrings [ (builtins.unsafeDiscardStringContext "${base.dev}") ] [ "${kernelDev}" ] (builtins.unsafeDiscardStringContext flag)
      else flag) old.makeFlags;
  });
in {
  cycle = module "j81-dwi-gpu-pmgr-cycle" ../gpu-pmgr-cycle;
  kpoll = module "j81-dwi-gpc-page5-kpoll" ../gpc-page5-kpoll;
}
