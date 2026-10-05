# 0052 + 0053 plus 0054: a behaviour-neutral clean-up of pcie-apple-t7000.c (durable log
# names, register dumps at debug level with their reads kept, comments rewritten). The write,
# read and delay sequence is pinned identical to 0053 by kernel/test_pcie_write_sequence.py.
# 0052 (board-gated J81 Wi-Fi REG_ON) plus 0053: the controller's link wait now polls
# the root port's Data Link Layer Link Active bit (LnkSta bit 13) instead of the
# undecoded +0x88 bit 6. 0053 adds no write of any kind. Same Stage-5F base as 0052.
# Stage 5F plus the board-bound J81 Wi-Fi REG_ON sequence. The PCIe node
# explicitly names its D2207 PMIC, so the driver never searches for a PMIC
# globally. It writes only D2207 GPIO3 (0x0403), verifies it, waits 100 ms,
# then proceeds with PCIe; Bluetooth GPIO2 is not part of this path.
{ buildLinux
, runCommand
, source
, hoolockConfig
, ...
} @ args:

let
  configuredSource = runCommand "linux-hoolock-pcie-j81-clean-t7001-source" {} ''
    mkdir -p "$out"
    cp -R ${source}/. "$out/"
    chmod -R u+w "$out"
    cp ${hoolockConfig} "$out/arch/arm64/configs/ipad_t7001_hoolock_pcie_j81_clean_defconfig"

    file="$out/drivers/video/backlight/apple_pmic_bl.c"
    grep -q 'return ((cmd\[1\] & 7) << 8) | (cmd\[0\] & 0xff);' "$file"
    sed -i \
      's/return ((cmd\[1\] \& 7) << 8) | (cmd\[0\] \& 0xff);/&\n\t\tdefault:\n\t\t\treturn -EINVAL;/' \
      "$file"

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

    # Build the known hardware-proven Stage 5F base, then replace its global
    # PMIC search with the J81-only board resource path. Do not stack 0050.
    # This intentionally retains Stage 5F's test-stage link wait; DLLLA,
    # rather than that poll, remains the hardware-proven success signal.
    patch -d "$out" -p1 < ${./patches/0016-pcie-apple-t7000-compile-only-skeleton.patch}
    patch -d "$out" -p1 < ${./patches/0040-pcie-apple-t7000-tuning-baseline-test.patch}
    patch -d "$out" -p1 < ${./patches/0041-pcie-apple-t7000-dbi-ecam-read-test.patch}
    patch -d "$out" -p1 < ${./patches/0042-pcie-apple-t7000-dbi-tunables-write-test.patch}
    patch -d "$out" -p1 < ${./patches/0043-pcie-apple-t7000-link-state-probe-test.patch}
    patch -d "$out" -p1 < ${./patches/0044-pcie-apple-t7000-link-wait-write-test.patch}
    patch -d "$out" -p1 < ${./patches/0045-pcie-apple-t7000-link-speed-write-test.patch}
    patch -d "$out" -p1 < ${./patches/0052-pcie-apple-t7000-j81-reg-on.patch}
    patch -d "$out" -p1 < ${./patches/0053-pcie-apple-t7000-link-wait-dllla.patch}
    patch -d "$out" -p1 < ${./patches/0054-pcie-apple-t7000-clean-up.patch}
  '';
  buildArgs = builtins.removeAttrs args [ "source" "hoolockConfig" "runCommand" ];
in
buildLinux (buildArgs // {
  version = "7.3.0-rc1";
  modDirVersion = "7.3.0-rc1";
  src = configuredSource;
  defconfig = "ipad_t7001_hoolock_pcie_j81_clean_defconfig";
  enableCommonConfig = false;
  autoModules = false;
  ignoreConfigErrors = true;
  buildDTBs = true;
  extraMeta = {
    branch = "hoolock-pcie-j81-clean";
    description = "Hoolock kernel for iPad Air 2 with board-declared BCM4350 Wi-Fi REG_ON";
    platforms = [ "aarch64-linux" ];
  };
} // (args.argsOverride or {}))
