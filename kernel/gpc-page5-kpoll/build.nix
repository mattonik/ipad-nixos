# Match the fail-stop PMGR cycle payload's kernel, as for the MCC probe.
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
  pname = "j81-kmod-gpc-page5-kpoll";
  src = builtins.path { path = ./.; name = "gpc-page5-kpoll-src"; };
  makeFlags = map (flag: builtins.replaceStrings [ "${base.dev}" ] [ "${testKernel.dev}" ] flag) old.makeFlags;
})
