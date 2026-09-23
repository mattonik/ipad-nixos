# Everything kernel/hoolock.nix has (BT-1, BAT-1/2/3, CHG-1, TOUCH-1/2
# groundwork) PLUS a strictly minimal T7000 PCIe probe test: the DT node
# flips to status = "okay" (triggering the platform-device/genpd power-up
# of power-domains = <&ps_pcie> automatically, before any driver code
# runs), but the matching driver maps no MMIO and calls no PCI/ECAM/DART
# code at all -- it only logs that probe() was reached. DART stays
# disabled and the pcie node's iommu-map is removed, so nothing here
# touches DART either.
#
# This exists because two real hardware attempts with
# kernel/hoolock-pcie-test.nix's driver (0018, both a write-capable
# version and a version documented at the time as a "read-only
# diagnostic") hung identically, and a post-attempt source review found
# neither attempt actually isolated the platform power-domain attachment
# from PCI-core/ECAM/DART activity -- both called pci_host_common_init(),
# which maps ECAM and runs a full generic PCI bus scan regardless of what
# the driver's own code does. This payload is the corrected, genuinely
# minimal next diagnostic step. See docs/plans/2026-09-13-j81-wifi-pcie.md's
# "Post-attempt implementation review" section for the full analysis.
#
# Deliberately its own separate file and flake output
# (m1n1-hoolock-pcie-pmgr-test), never touching kernel/hoolock-pcie-test.nix
# or its own 0018 patch, which is retained as a historical record of the
# earlier, inconclusive attempts -- not a candidate for another hardware run.
{ buildLinux
, runCommand
, source
, hoolockConfig
, ...
} @ args:

let
  configuredSource = runCommand "linux-hoolock-pcie-pmgr-test-t7001-source" {} ''
    mkdir -p "$out"
    cp -R ${source}/. "$out/"
    chmod -R u+w "$out"
    cp ${hoolockConfig} "$out/arch/arm64/configs/ipad_t7001_hoolock_pcie_pmgr_test_defconfig"

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

    # PCIe PMGR-only test (docs/plans/2026-09-13-j81-wifi-pcie.md): 0016
    # first (the inert compile-only skeleton -- Kconfig/Makefile wiring,
    # the driver source file, and the disabled DT node/DART), then 0019
    # on top -- NOT 0018. 0019 flips only the pcie node to "okay" and
    # replaces the driver's probe() with a bare dev_info() log; it does
    # not touch dart_apcie1, iommu-map, or any MMIO/PCI-core path.
    patch -d "$out" -p1 < ${./patches/0016-pcie-apple-t7000-compile-only-skeleton.patch}
    patch -d "$out" -p1 < ${./patches/0019-pcie-apple-t7000-pmgr-only-test.patch}
  '';
  buildArgs = builtins.removeAttrs args [ "source" "hoolockConfig" "runCommand" ];
in
buildLinux (buildArgs // {
  version = "7.3.0-rc1";
  modDirVersion = "7.3.0-rc1";

  src = configuredSource;

  defconfig = "ipad_t7001_hoolock_pcie_pmgr_test_defconfig";
  enableCommonConfig = false;
  autoModules = false;
  ignoreConfigErrors = true;
  buildDTBs = true;

  extraMeta = {
    branch = "hoolock-pcie-pmgr-test";
    description = "Hoolock kernel for iPad Air 2 (A8X/T7001) with everything kernel/hoolock.nix has plus a strictly minimal T7000 PCIe PMGR-only probe test (no MMIO, no PCI core, no DART) -- a dedicated diagnostic payload, not the default";
    platforms = [ "aarch64-linux" ];
  };
} // (args.argsOverride or {}))
