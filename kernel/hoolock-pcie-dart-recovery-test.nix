# Everything kernel/hoolock.nix has (BT-1, BAT-1/2/3, CHG-1, TOUCH-1/2
# groundwork) PLUS the DART recovery-write evidence gate
# (docs/plans/2026-09-13-j81-wifi-pcie.md,
# research/t7000-pcie-hardware-findings.md): patch 0025 (DART enabled via
# the stock apple-dart driver, no iommu-map) hung on real hardware. Offline
# Ghidra tracing of the exact 12B410 kernelcache found Apple's own
# AppleS5L8960XDART calls _dartRecoverFromPowerdown() as part of becoming
# available, writing DART+0x24 *before* restoring any other configuration
# -- while Linux's stock apple-dart driver instead begins
# apple_dart_hw_reset() with a *read* of DART+0x00, never performing this
# write.
#
# This payload redirects dart_apcie1's compatible string to a brand-new,
# dedicated test driver (drivers/iommu/apple-dart-t7000-recovery-test.c,
# patch 0027) that performs only that one recovered write -- DART+0x24 =
# 0x0020ffff, the real J81 ADT's "error-reflector" value right-shifted 12
# bits, matching Apple's own formula exactly -- then aborts probe. No
# reset sequence, no IRQ registration, no IOMMU domain setup, no
# iommu-map consumer. The stock apple-dart driver never binds to this
# node for this test.
#
# PCIe itself is still 0019's exact inert PMGR-only probe, unchanged.
{ buildLinux
, runCommand
, source
, hoolockConfig
, ...
} @ args:

let
  configuredSource = runCommand "linux-hoolock-pcie-dart-recovery-test-t7001-source" {} ''
    mkdir -p "$out"
    cp -R ${source}/. "$out/"
    chmod -R u+w "$out"
    cp ${hoolockConfig} "$out/arch/arm64/configs/ipad_t7001_hoolock_pcie_dart_recovery_test_defconfig"

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

    # PCIe DART recovery-write evidence gate
    # (docs/plans/2026-09-13-j81-wifi-pcie.md): 0016 first (the inert
    # compile-only skeleton), then 0027 on top -- NOT 0018 through 0026.
    # 0027 flips both pcie AND dart_apcie1 to "okay" (pcie's own driver
    # probe() unchanged from 0019/0025 -- inert, no MMIO, no PCI core),
    # redirects dart_apcie1's compatible string away from the stock
    # apple-dart driver, and adds the new dedicated recovery-write test
    # driver.
    patch -d "$out" -p1 < ${./patches/0016-pcie-apple-t7000-compile-only-skeleton.patch}
    patch -d "$out" -p1 < ${./patches/0027-pcie-apple-t7000-dart-recovery-write-test.patch}
  '';
  buildArgs = builtins.removeAttrs args [ "source" "hoolockConfig" "runCommand" ];
in
buildLinux (buildArgs // {
  version = "7.3.0-rc1";
  modDirVersion = "7.3.0-rc1";

  src = configuredSource;

  defconfig = "ipad_t7001_hoolock_pcie_dart_recovery_test_defconfig";
  enableCommonConfig = false;
  autoModules = false;
  ignoreConfigErrors = true;
  buildDTBs = true;

  extraMeta = {
    branch = "hoolock-pcie-dart-recovery-test";
    description = "Hoolock kernel for iPad Air 2 (A8X/T7001) with everything kernel/hoolock.nix has plus the DART recovery-write evidence gate: a dedicated test driver performs only Apple's recovered DART+0x24 write before aborting probe, PCIe itself still an inert PMGR-only probe -- a dedicated diagnostic payload, not the default";
    platforms = [ "aarch64-linux" ];
  };
} // (args.argsOverride or {}))
