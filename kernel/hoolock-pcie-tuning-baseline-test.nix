# Everything kernel/hoolock.nix has (BT-1, BAT-1/2/3, CHG-1, TOUCH-1/2
# groundwork) PLUS Stage 5A of the real PCIe host-controller
# implementation: the full recovered enable sequence (Stages 1-4b v2,
# hardware-confirmed safe end to end) plus a read-only baseline capture
# of the seven ADT-selected `apcie-config-tunables`/`dbi-overrides`
# offsets and the DBI write-enable gate, all within port 1's
# already-proven controller window -- no new writes this stage
# (docs/plans/2026-09-13-j81-wifi-pcie.md,
# research/t7000-pcie-hardware-findings.md).
#
# Motivation: Stage 4b v2 confirmed the link-start write genuinely
# takes, but no downstream BCM4350 endpoint enumerated after three scan
# attempts. A longer delay alone is not a credible fix (a manual rescan
# ~5s after boot was still empty). The captured J81 ADT supplies the
# exact controller records Apple's own driver applies through this same
# window before enumeration; this stage establishes their real
# before-state on J81 hardware, following this project's own
# read-before-write discipline, before Stage 5B ever applies the actual
# RMW records.
{ buildLinux
, runCommand
, source
, hoolockConfig
, ...
} @ args:

let
  configuredSource = runCommand "linux-hoolock-pcie-tuning-baseline-test-t7001-source" {} ''
    mkdir -p "$out"
    cp -R ${source}/. "$out/"
    chmod -R u+w "$out"
    cp ${hoolockConfig} "$out/arch/arm64/configs/ipad_t7001_hoolock_pcie_tuning_baseline_test_defconfig"

    # Same pre-existing GCC-cross-toolchain gap kernel/hoolock.nix already
    # fixes (apple_pmic_bl.c -Werror=return-type). Identical fix, applied
    # here too since this is a separate source copy.
    file="$out/drivers/video/backlight/apple_pmic_bl.c"
    grep -q 'return ((cmd\[1\] & 7) << 8) | (cmd\[0\] & 0xff);' "$file"
    sed -i \
      's/return ((cmd\[1\] \& 7) << 8) | (cmd\[0\] \& 0xff);/&\n\t\tdefault:\n\t\t\treturn -EINVAL;/' \
      "$file"

    # Everything kernel/hoolock.nix applies (BT-1, BAT-1/2/3, CHG-1,
    # TOUCH-1/2 groundwork) -- same patches, same order, same reasoning;
    # see that file's own comments for why each one exists.
    patch -d "$out" -p1 < ${./patches/0001-t7001-add-uart3-node.patch}
    patch -d "$out" -p1 < ${./patches/0002-t7001-air2-enable-uart3.patch}
    patch -d "$out" -p1 < ${./patches/0003-serdev-add-stop-bit-selection.patch}
    patch -d "$out" -p1 < ${./patches/0004-add-bq27xxx-hdq-uart-frontend.patch}
    patch -d "$out" -p1 < ${./patches/0005-t7001-add-uart5-node.patch}
    patch -d "$out" -p1 < ${./patches/0006-t7001-air2-enable-uart5-battery.patch}
    patch -d "$out" -p1 < ${./patches/0010-j81-d2207-readonly-charger.patch}
    patch -d "$out" -p1 < ${./patches/0007-spi-apple-add-s5l8960x-support.patch}
    patch -d "$out" -p1 < ${./patches/0008-t7001-add-spi3-node.patch}
    patch -d "$out" -p1 < ${./patches/0009-t7001-air2-enable-spi3.patch}
    patch -d "$out" -p1 < ${./patches/0011-touchscreen-apple-z2-add-j81.patch}

    # PCIe full recovered enable sequence plus read-only controller-tuning
    # baseline test (docs/plans/2026-09-13-j81-wifi-pcie.md): 0016 first
    # (the inert compile-only skeleton), then 0040 on top -- a clean
    # branch, not stacked on 0033-0039 or any other PCIe/DART test.
    patch -d "$out" -p1 < ${./patches/0016-pcie-apple-t7000-compile-only-skeleton.patch}
    patch -d "$out" -p1 < ${./patches/0040-pcie-apple-t7000-tuning-baseline-test.patch}
  '';
  buildArgs = builtins.removeAttrs args [ "source" "hoolockConfig" "runCommand" ];
in
buildLinux (buildArgs // {
  version = "7.3.0-rc1";
  modDirVersion = "7.3.0-rc1";

  src = configuredSource;

  defconfig = "ipad_t7001_hoolock_pcie_tuning_baseline_test_defconfig";
  enableCommonConfig = false;
  autoModules = false;
  ignoreConfigErrors = true;
  buildDTBs = true;

  extraMeta = {
    branch = "hoolock-pcie-tuning-baseline-test";
    description = "Hoolock kernel for iPad Air 2 (A8X/T7001) with everything kernel/hoolock.nix has plus Stage 5A of the real PCIe driver: the full recovered enable sequence plus a read-only baseline capture of the seven ADT-selected controller-tuning/DBI offsets -- no new writes";
    platforms = [ "aarch64-linux" ];
  };
} // (args.argsOverride or {}))
