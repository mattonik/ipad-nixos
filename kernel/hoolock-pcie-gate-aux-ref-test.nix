# Everything kernel/hoolock.nix has (BT-1, BAT-1/2/3, CHG-1, TOUCH-1/2
# groundwork) plus the hardware-clean PCIe Stages 1-5F and Stage 5G's
# isolated PMGR gate test: explicitly attaches ps_pcie_aux/ps_pcie_ref
# (Apple's real +0x6b8 controller hook enables all three PCIE/AUX/REF
# clock gates plus PCIE power; Linux previously attached only ps_pcie).
# No register-level changes versus Stage 5F -- kept isolated from the
# other identified delta (the +0x6d0 hook's 0x180/0x198 transition) so
# either result stays unambiguous.
{ buildLinux
, runCommand
, source
, hoolockConfig
, ...
} @ args:

let
  configuredSource = runCommand "linux-hoolock-pcie-gate-aux-ref-test-t7001-source" {} ''
    mkdir -p "$out"
    cp -R ${source}/. "$out/"
    chmod -R u+w "$out"
    cp ${hoolockConfig} "$out/arch/arm64/configs/ipad_t7001_hoolock_pcie_gate_aux_ref_test_defconfig"

    # Same pre-existing GCC-cross-toolchain fix as kernel/hoolock.nix.
    file="$out/drivers/video/backlight/apple_pmic_bl.c"
    grep -q 'return ((cmd\[1\] & 7) << 8) | (cmd\[0\] & 0xff);' "$file"
    sed -i \
      's/return ((cmd\[1\] \& 7) << 8) | (cmd\[0\] \& 0xff);/&\n\t\tdefault:\n\t\t\treturn -EINVAL;/' \
      "$file"

    # Same non-PCIe groundwork as kernel/hoolock.nix.
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

    # PCIe clean branch: inert skeleton, Stage 5A baseline, Stage 5B's
    # read-only DBI ECAM mapping probe, Stage 5C's gated RMW, Stage 5D's
    # read-only link-state probe, Stage 5E's full reordered sequence,
    # Stage 5F's recovered maximum-link-speed RMW, then Stage 5G's
    # isolated PMGR gate test. Do not stack historic PCIe tests.
    patch -d "$out" -p1 < ${./patches/0016-pcie-apple-t7000-compile-only-skeleton.patch}
    patch -d "$out" -p1 < ${./patches/0040-pcie-apple-t7000-tuning-baseline-test.patch}
    patch -d "$out" -p1 < ${./patches/0041-pcie-apple-t7000-dbi-ecam-read-test.patch}
    patch -d "$out" -p1 < ${./patches/0042-pcie-apple-t7000-dbi-tunables-write-test.patch}
    patch -d "$out" -p1 < ${./patches/0043-pcie-apple-t7000-link-state-probe-test.patch}
    patch -d "$out" -p1 < ${./patches/0044-pcie-apple-t7000-link-wait-write-test.patch}
    patch -d "$out" -p1 < ${./patches/0045-pcie-apple-t7000-link-speed-write-test.patch}
    patch -d "$out" -p1 < ${./patches/0046-pcie-apple-t7000-gate-aux-ref-test.patch}
  '';
  buildArgs = builtins.removeAttrs args [ "source" "hoolockConfig" "runCommand" ];
in
buildLinux (buildArgs // {
  version = "7.3.0-rc1";
  modDirVersion = "7.3.0-rc1";
  src = configuredSource;
  defconfig = "ipad_t7001_hoolock_pcie_gate_aux_ref_test_defconfig";
  enableCommonConfig = false;
  autoModules = false;
  ignoreConfigErrors = true;
  buildDTBs = true;
  extraMeta = {
    branch = "hoolock-pcie-gate-aux-ref-test";
    description = "Hoolock kernel for iPad Air 2 (A8X/T7001) with the Stage 5G isolated ps_pcie_aux/ps_pcie_ref PMGR gate test";
    platforms = [ "aarch64-linux" ];
  };
} // (args.argsOverride or {}))
