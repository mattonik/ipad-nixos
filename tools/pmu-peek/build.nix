# Static aarch64 musl build of pmu-peek without editing flake.nix: overrides the existing pmgr-words-peek derivation.
{ repo }:
let
  packages = (builtins.getFlake ("git+file://" + toString repo)).packages.x86_64-linux;
in packages.pmgr-words-peek-static.overrideAttrs (old: {
  name = "pmu-peek";
  buildPhase = "$CC -static -O2 -Wall -Wextra -Werror -o pmu-peek ${./pmu-peek.c}";
  installPhase = "mkdir -p $out/bin && cp pmu-peek $out/bin/pmu-peek";
})
