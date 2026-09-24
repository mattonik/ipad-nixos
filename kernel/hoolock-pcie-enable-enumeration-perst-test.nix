# Everything kernel/hoolock.nix has (BT-1, BAT-1/2/3, CHG-1, TOUCH-1/2
# groundwork) PLUS Stage 3 of the real PCIe host-controller
# implementation: Stage 2's enable-sequence write + generic ECAM
# enumeration, now with PERST# deasserted via a pci@0,0/reset-gpios DT
# child node
# (docs/plans/2026-09-13-j81-wifi-pcie.md,
# research/t7000-pcie-hardware-findings.md).
#
# `0034` (Stage 2: the write sequence + generic bus scan, PERST left
# untouched) is cross-build verified and awaiting its own hardware
# result. This test adds the pci@0,0/reset-gpios DT child node AND the
# driver code that actually uses it: probe() explicitly calls
# pci_host_common_parse_ports() (pci_host_common_init() does not do this
# automatically -- confirmed against the real pinned
# drivers/pci/controller/pci-host-common.c source, correcting an
# assumption carried over from the original 0018 commit message) and the
# .init callback explicitly walks the resulting port list to deassert
# PERST# itself, after the recovered enable sequence.
{ buildLinux
, runCommand
, source
, hoolockConfig
, ...
} @ args:

let
  configuredSource = runCommand "linux-hoolock-pcie-enable-enumeration-perst-test-t7001-source" {} ''
    mkdir -p "$out"
    cp -R ${source}/. "$out/"
    chmod -R u+w "$out"
    cp ${hoolockConfig} "$out/arch/arm64/configs/ipad_t7001_hoolock_pcie_enable_enumeration_perst_test_defconfig"

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

    # PCIe enable-sequence + generic-enumeration + PERST test
    # (docs/plans/2026-09-13-j81-wifi-pcie.md): 0016 first (the inert
    # compile-only skeleton), then 0035 on top -- a clean branch, not
    # stacked on 0033/0034 or any other PCIe/DART test.
    patch -d "$out" -p1 < ${./patches/0016-pcie-apple-t7000-compile-only-skeleton.patch}
    patch -d "$out" -p1 < ${./patches/0035-pcie-apple-t7000-enable-enumeration-perst-test.patch}
  '';
  buildArgs = builtins.removeAttrs args [ "source" "hoolockConfig" "runCommand" ];
in
buildLinux (buildArgs // {
  version = "7.3.0-rc1";
  modDirVersion = "7.3.0-rc1";

  src = configuredSource;

  defconfig = "ipad_t7001_hoolock_pcie_enable_enumeration_perst_test_defconfig";
  enableCommonConfig = false;
  autoModules = false;
  ignoreConfigErrors = true;
  buildDTBs = true;

  extraMeta = {
    branch = "hoolock-pcie-enable-enumeration-perst-test";
    description = "Hoolock kernel for iPad Air 2 (A8X/T7001) with everything kernel/hoolock.nix has plus Stage 3 of the real PCIe driver: Stage 2's shared-window enable sequence + generic ECAM enumeration, now with PERST# deasserted via reset-gpios (still no per-port link-start) -- a dedicated diagnostic payload, not the default";
    platforms = [ "aarch64-linux" ];
  };
} // (args.argsOverride or {}))
