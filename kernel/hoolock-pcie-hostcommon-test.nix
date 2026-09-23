# Everything kernel/hoolock.nix has (BT-1, BAT-1/2/3, CHG-1, TOUCH-1/2
# groundwork) PLUS an isolated pci_host_common_init() test: the driver
# calls devm_pci_alloc_host_bridge() + pci_host_common_init() with a bare
# ECAM ops struct and nothing else -- no shared-window register writes, no
# PERST/GPIO handling, no DART/iommu-map.
#
# Final diagnostic step after four clean hardware tests in a row (0019
# PMGR-only, 0020 shared-window read, 0021 ECAM offset-0 read, 0022 ECAM
# at bus 0/1/4) ruled out the DT status flip, the power-domain attachment,
# and every raw MMIO read tried anywhere on this controller. Both hanging
# 0018 attempts called pci_host_common_init(); this is the one remaining
# untested code path -- it sets PCI_REASSIGN_ALL_BUS and calls the real
# pci_host_probe() bus scan, which (unlike every bounded read tried so
# far) also performs config-space writes as part of standard resource
# discovery. See docs/plans/2026-09-13-j81-wifi-pcie.md's "Multi-offset
# ECAM read test: hardware-verified clean" section for the full reasoning.
#
# Real risk, unlike the four prior tests: this one calls the exact code
# path both hanging 0018 attempts called, so it may well reproduce the
# original hang -- which is itself a useful, confirming result.
#
# Deliberately its own separate file and flake output
# (m1n1-hoolock-pcie-hostcommon-test), never touching any earlier PCIe
# test payload -- patch 0023 is layered on 0016 directly, a clean branch,
# same as 0019/0020/0021/0022 were.
{ buildLinux
, runCommand
, source
, hoolockConfig
, ...
} @ args:

let
  configuredSource = runCommand "linux-hoolock-pcie-hostcommon-test-t7001-source" {} ''
    mkdir -p "$out"
    cp -R ${source}/. "$out/"
    chmod -R u+w "$out"
    cp ${hoolockConfig} "$out/arch/arm64/configs/ipad_t7001_hoolock_pcie_hostcommon_test_defconfig"

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

    # PCIe isolated pci_host_common_init() test
    # (docs/plans/2026-09-13-j81-wifi-pcie.md): 0016 first (the inert
    # compile-only skeleton -- Kconfig/Makefile wiring, the driver source
    # file, and the disabled DT node/DART), then 0023 on top -- NOT 0018,
    # 0019, 0020, 0021, or 0022. 0023 flips only the pcie node to "okay"
    # (same DT shape as 0019-0022) and replaces the driver's probe() with
    # a bare devm_pci_alloc_host_bridge() + pci_host_common_init() call;
    # it does not touch dart_apcie1, iommu-map, or any register window.
    patch -d "$out" -p1 < ${./patches/0016-pcie-apple-t7000-compile-only-skeleton.patch}
    patch -d "$out" -p1 < ${./patches/0023-pcie-apple-t7000-isolated-host-common-init-test.patch}
  '';
  buildArgs = builtins.removeAttrs args [ "source" "hoolockConfig" "runCommand" ];
in
buildLinux (buildArgs // {
  version = "7.3.0-rc1";
  modDirVersion = "7.3.0-rc1";

  src = configuredSource;

  defconfig = "ipad_t7001_hoolock_pcie_hostcommon_test_defconfig";
  enableCommonConfig = false;
  autoModules = false;
  ignoreConfigErrors = true;
  buildDTBs = true;

  extraMeta = {
    branch = "hoolock-pcie-hostcommon-test";
    description = "Hoolock kernel for iPad Air 2 (A8X/T7001) with everything kernel/hoolock.nix has plus an isolated pci_host_common_init() test (no register writes, no PERST, no DART) -- a dedicated diagnostic payload, not the default";
    platforms = [ "aarch64-linux" ];
  };
} // (args.argsOverride or {}))
