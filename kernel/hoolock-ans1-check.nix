# Isolated compile-only check for Hoolock's `ans1` branch (ANS1/ASP
# internal-storage controller support), per research/j81-long-term-
# subsystems.md's "Internal NAND storage" section. Deliberately builds
# ans1's own source completely unmodified by this project's own patches
# (UART3/UART5/SPI3/touch/charger) -- this answers "does Hoolock's own
# community ANS1 work compile under our cross-toolchain", not "do our
# other patches also apply on top of a divergent tree", which is a
# separate, later question. Not wired into m1n1-hoolock-control; nothing
# here is flashed or booted. See that research doc for why: the driver
# (drivers/block/asp.c) unconditionally unlocks writes to every storage
# namespace during probe with no config-time opt-out, which is real,
# confirmed-in-source danger this project's own plan requires patching
# to observation-only before any hardware boot -- not attempted here.
{ buildLinux
, runCommand
, source
, ansConfig
, ...
} @ args:

let
  configuredSource = runCommand "linux-hoolock-ans1-t7001-source" {} ''
    mkdir -p "$out"
    cp -R ${source}/. "$out/"
    chmod -R u+w "$out"
    cp ${ansConfig} "$out/arch/arm64/configs/ipad_t7001_ans1_check_defconfig"

    # Same pre-existing GCC-cross-toolchain gap kernel/hoolock.nix already
    # fixes for the same reason (apple_pmic_bl_get_brightness()'s switch
    # over enum apple_pmic_type has no default case, so this project's GCC
    # can't prove every path returns -Werror=return-type) -- unrelated to
    # ANS1/asp.c, just an unrelated driver compiled along the way in any
    # full kernel build on this source lineage. Same minimal, behavior-
    # preserving fix, not a workaround specific to this check.
    file="$out/drivers/video/backlight/apple_pmic_bl.c"
    grep -q 'return ((cmd\[1\] & 7) << 8) | (cmd\[0\] & 0xff);' "$file"
    sed -i \
      's/return ((cmd\[1\] \& 7) << 8) | (cmd\[0\] \& 0xff);/&\n\t\tdefault:\n\t\t\treturn -EINVAL;/' \
      "$file"
  '';
  buildArgs = builtins.removeAttrs args [ "source" "ansConfig" "runCommand" ];
in
buildLinux (buildArgs // {
  # Same real version string kernel/hoolock.nix uses -- ans1 is 27 commits
  # ahead of the same 7.3-rc1 base, not a different kernel version. nixpkgs'
  # buildLinux uses this to decide which of its own generic infra patches
  # (e.g. randstruct-provide-seed) to auto-apply; a placeholder non-numeric
  # string here broke that selection against unrelated files.
  version = "7.3.0-rc1";
  modDirVersion = "7.3.0-rc1";

  src = configuredSource;

  defconfig = "ipad_t7001_ans1_check_defconfig";
  enableCommonConfig = false;
  autoModules = false;
  ignoreConfigErrors = true;
  buildDTBs = true;

  extraMeta = {
    branch = "ans1-check";
    description = "Compile-only check of Hoolock's ans1 branch (ANS1/ASP storage) for iPad Air 2 (A8X/T7001) -- not wired into any boot payload";
    platforms = [ "aarch64-linux" ];
  };
} // (args.argsOverride or {}))
