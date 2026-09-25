# Everything kernel/hoolock.nix has (BT-1, BAT-1/2/3, CHG-1, TOUCH-1/2
# groundwork) PLUS Charging Stage 2: a real, writable
# input_current_limit power-supply property on the J81 D2207 charger
# driver (docs/plans/2026-09-13-pmic-pcie-execution.md).
#
# CHG-1's read-only driver is already in kernel/hoolock.nix. This test
# adds the write path -- exposing the same 0x04c0 register write
# boot/ipad_console.py's console tool already validated live on real
# hardware across all five tested tiers -- through the standard sysfs
# interface. Deliberately its own separate file and flake output
# (m1n1-hoolock-charging-writable-test), not merged into
# kernel/hoolock.nix, matching this project's own established pattern
# (kernel/hoolock-ans1-test.nix) of cross-build verifying a new
# capability in isolation before it's ever considered for the default
# payload.
{ buildLinux
, runCommand
, source
, hoolockConfig
, ...
} @ args:

let
  configuredSource = runCommand "linux-hoolock-charging-writable-test-t7001-source" {} ''
    mkdir -p "$out"
    cp -R ${source}/. "$out/"
    chmod -R u+w "$out"
    cp ${hoolockConfig} "$out/arch/arm64/configs/ipad_t7001_hoolock_charging_writable_test_defconfig"

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

    # Charging Stage 2: adds set_property/property_is_writeable for
    # POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT to CHG-1's driver, using the
    # exact encode formula boot/ipad_console.py's own
    # _charging_current_code() already validated live (round-trip
    # tested against all five tiers) -- not independently re-derived.
    # Updates the DTS node's own comment to match (it previously
    # documented "no PMIC writes are exposed", which this makes stale).
    patch -d "$out" -p1 < ${./patches/0017-j81-d2207-charger-writable-input-current-limit.patch}
  '';
  buildArgs = builtins.removeAttrs args [ "source" "hoolockConfig" "runCommand" ];
in
buildLinux (buildArgs // {
  version = "7.3.0-rc1";
  modDirVersion = "7.3.0-rc1";

  src = configuredSource;

  defconfig = "ipad_t7001_hoolock_charging_writable_test_defconfig";
  enableCommonConfig = false;
  autoModules = false;
  ignoreConfigErrors = true;
  buildDTBs = true;

  extraMeta = {
    branch = "hoolock-charging-writable-test";
    description = "Hoolock kernel for iPad Air 2 (A8X/T7001) with everything kernel/hoolock.nix has plus a writable input_current_limit property on the D2207 charger driver -- a dedicated test payload, not the default";
    platforms = [ "aarch64-linux" ];
  };
} // (args.argsOverride or {}))
