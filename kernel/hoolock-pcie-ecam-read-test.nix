# Everything kernel/hoolock.nix has (BT-1, BAT-1/2/3, CHG-1, TOUCH-1/2
# groundwork) PLUS a bounded T7000 PCIe ECAM-window read test: the driver
# maps only the ECAM config-space window (reg index 0) directly via
# devm_ioremap_resource(), performs a single readl() at config-space offset
# 0 (bus0/dev0/fn0), and logs it -- no pci_ecam_create(), no pci_ops, no
# pci_host_probe() bus scan, no DART.
#
# Next diagnostic step after kernel/hoolock-pcie-shared-read-test.nix
# (patch 0020) hardware-verified clean, 2026-09-23: that test proved the
# shared register window is safely readable. Two clean tests in a row now
# (0019 PMGR-only, 0020 shared-window read) leave only
# pci_host_common_init()'s two remaining pieces as suspects -- ECAM mapping
# and the generic pci_host_probe() bus scan -- both of which the earlier
# hanging 0018 attempts called and neither working test does. This test
# adds back a real ECAM MMIO read to isolate ECAM mapping from the bus-scan
# logic itself. See docs/plans/2026-09-13-j81-wifi-pcie.md's "Bounded
# shared-window read test: hardware-verified clean" section for the full
# reasoning and the concrete hypothesis this isolates (the controller's
# ECAM decode path may need the recovered enable-sequence writes, never
# executed by any test so far, before its address range answers cleanly).
#
# Deliberately its own separate file and flake output
# (m1n1-hoolock-pcie-ecam-read-test), never touching
# kernel/hoolock-pcie-test.nix (0018), kernel/hoolock-pcie-pmgr-test.nix
# (0019), or kernel/hoolock-pcie-shared-read-test.nix (0020) -- patch 0021
# is layered on 0016 directly, a clean branch, same as 0019/0020 were.
{ buildLinux
, runCommand
, source
, hoolockConfig
, ...
} @ args:

let
  configuredSource = runCommand "linux-hoolock-pcie-ecam-read-test-t7001-source" {} ''
    mkdir -p "$out"
    cp -R ${source}/. "$out/"
    chmod -R u+w "$out"
    cp ${hoolockConfig} "$out/arch/arm64/configs/ipad_t7001_hoolock_pcie_ecam_read_test_defconfig"

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

    # PCIe bounded ECAM-window read test
    # (docs/plans/2026-09-13-j81-wifi-pcie.md): 0016 first (the inert
    # compile-only skeleton -- Kconfig/Makefile wiring, the driver source
    # file, and the disabled DT node/DART), then 0021 on top -- NOT 0018,
    # 0019, or 0020. 0021 flips only the pcie node to "okay" (same DT shape
    # as 0019/0020) and replaces the driver's probe() with a bare ECAM
    # window map + single readl() + dev_info() log; it does not touch
    # dart_apcie1, iommu-map, pci_ecam_create(), or pci_host_probe().
    patch -d "$out" -p1 < ${./patches/0016-pcie-apple-t7000-compile-only-skeleton.patch}
    patch -d "$out" -p1 < ${./patches/0021-pcie-apple-t7000-ecam-window-read-test.patch}
  '';
  buildArgs = builtins.removeAttrs args [ "source" "hoolockConfig" "runCommand" ];
in
buildLinux (buildArgs // {
  version = "7.3.0-rc1";
  modDirVersion = "7.3.0-rc1";

  src = configuredSource;

  defconfig = "ipad_t7001_hoolock_pcie_ecam_read_test_defconfig";
  enableCommonConfig = false;
  autoModules = false;
  ignoreConfigErrors = true;
  buildDTBs = true;

  extraMeta = {
    branch = "hoolock-pcie-ecam-read-test";
    description = "Hoolock kernel for iPad Air 2 (A8X/T7001) with everything kernel/hoolock.nix has plus a bounded T7000 PCIe ECAM-window read test (no pci_ecam_create, no bus scan, no DART) -- a dedicated diagnostic payload, not the default";
    platforms = [ "aarch64-linux" ];
  };
} // (args.argsOverride or {}))
