# Build only against the exact fail-stop kernel used by the PMGR cycle payload.
{ repo }:
let
  packages = (builtins.getFlake ("git+file://" + toString repo)).packages.x86_64-linux;
  base = packages.hoolock-wifi-kmod-kernel;
  testKernel = base.overrideAttrs (old: {
    patches = (old.patches or []) ++ [
      (builtins.path { path = ../patches/0123-apple-pmgr-pwrstate-stop-on-errors.patch; name = "gpu-pmgr-errors.patch"; })
    ];
  });
in packages.j81-kmod-spi-apple.overrideAttrs (old: {
  pname = "j81-kmod-mcc-read-once";
  src = builtins.path { path = ./.; name = "mcc-read-once-src"; };
  makeFlags = map (flag: builtins.replaceStrings [ "${base.dev}" ] [ "${testKernel.dev}" ] flag) old.makeFlags;
})
