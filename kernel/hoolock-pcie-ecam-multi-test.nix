# Everything kernel/hoolock.nix has (BT-1, BAT-1/2/3, CHG-1, TOUCH-1/2
# groundwork) PLUS a multi-offset bounded T7000 PCIe ECAM read test: the
# driver maps only the ECAM config-space window (reg index 0), then does
# three independently bounded readl()s at bus 0/1/4 (device 0, function 0
# each), logging every step -- no pci_ecam_create(), no pci_ops, no
# pci_host_probe() bus scan, no DART.
#
# Next diagnostic step after kernel/hoolock-pcie-ecam-read-test.nix (patch
# 0021) hardware-verified clean, 2026-09-23: that test proved a single
# ECAM read at bus0/dev0/fn0 (offset 0) is safe. Three clean tests in a row
# now (0019 PMGR-only, 0020 shared-window read, 0021 ECAM offset-0 read)
# leave only pci_host_probe()'s full generic bus scan as an untested
# difference from the earlier hanging 0018 attempts. Leading hypothesis:
# only part of the declared 16 MiB ECAM window is genuinely mapped, safe
# silicon, and a full multi-bus scan reaches the unsafe part while a
# single offset-0 read does not. This test probes bus 1 (the most likely
# slot for the real populated port, given bus-range = <0 4> and the
# all-Fs "no device" result already seen at bus 0) and bus 4 (the far edge
# of the declared range) to try to localize a bad region before ever
# re-running the full scan. See docs/plans/2026-09-13-j81-wifi-pcie.md's
# "Bounded ECAM-window read test: hardware-verified clean" section for the
# full reasoning.
#
# Deliberately its own separate file and flake output
# (m1n1-hoolock-pcie-ecam-multi-test), never touching any earlier PCIe test
# payload -- patch 0022 is layered on 0016 directly, a clean branch, same
# as 0019/0020/0021 were.
{ buildLinux
, runCommand
, source
, hoolockConfig
, ...
} @ args:

let
  configuredSource = runCommand "linux-hoolock-pcie-ecam-multi-test-t7001-source" {} ''
    mkdir -p "$out"
    cp -R ${source}/. "$out/"
    chmod -R u+w "$out"
    cp ${hoolockConfig} "$out/arch/arm64/configs/ipad_t7001_hoolock_pcie_ecam_multi_test_defconfig"

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

    # PCIe multi-offset bounded ECAM read test
    # (docs/plans/2026-09-13-j81-wifi-pcie.md): 0016 first (the inert
    # compile-only skeleton -- Kconfig/Makefile wiring, the driver source
    # file, and the disabled DT node/DART), then 0022 on top -- NOT 0018,
    # 0019, 0020, or 0021. 0022 flips only the pcie node to "okay" (same DT
    # shape as 0019/0020/0021) and replaces the driver's probe() with
    # three bounded readl()s at bus 0/1/4 + dev_info() logs each; it does
    # not touch dart_apcie1, iommu-map, pci_ecam_create(), or
    # pci_host_probe().
    patch -d "$out" -p1 < ${./patches/0016-pcie-apple-t7000-compile-only-skeleton.patch}
    patch -d "$out" -p1 < ${./patches/0022-pcie-apple-t7000-multi-offset-ecam-read-test.patch}
  '';
  buildArgs = builtins.removeAttrs args [ "source" "hoolockConfig" "runCommand" ];
in
buildLinux (buildArgs // {
  version = "7.3.0-rc1";
  modDirVersion = "7.3.0-rc1";

  src = configuredSource;

  defconfig = "ipad_t7001_hoolock_pcie_ecam_multi_test_defconfig";
  enableCommonConfig = false;
  autoModules = false;
  ignoreConfigErrors = true;
  buildDTBs = true;

  extraMeta = {
    branch = "hoolock-pcie-ecam-multi-test";
    description = "Hoolock kernel for iPad Air 2 (A8X/T7001) with everything kernel/hoolock.nix has plus a multi-offset bounded T7000 PCIe ECAM read test (bus 0/1/4, no bus scan, no DART) -- a dedicated diagnostic payload, not the default";
    platforms = [ "aarch64-linux" ];
  };
} // (args.argsOverride or {}))
