# Everything kernel/hoolock.nix has (BT-1, BAT-1/2/3, CHG-1, TOUCH-1/2
# groundwork) PLUS Hoolock's ans1 branch (ANS1/ASP internal-storage
# controller), hardened to observation-only. Deliberately its own separate
# file and flake output (m1n1-hoolock-ans1-test), not merged into
# kernel/hoolock.nix -- enabling ANS1 by default in the main payload would
# mean every future boot, including routine touch/battery work, runs a
# storage driver against real NAND. This file exists so that only a
# deliberate, separate test payload does.
#
# See docs/plans/2026-09-13-j81-ans1-observation-only.md for the full
# reasoning behind the hardening (patch 0012) and the DTS/driver
# integration (0013/0014/0015) this adds on top of everything already in
# kernel/hoolock.nix.
{ buildLinux
, runCommand
, source
, hoolockConfig
, ...
} @ args:

let
  configuredSource = runCommand "linux-hoolock-ans1-test-t7001-source" {} ''
    mkdir -p "$out"
    cp -R ${source}/. "$out/"
    chmod -R u+w "$out"
    cp ${hoolockConfig} "$out/arch/arm64/configs/ipad_t7001_hoolock_ans1_test_defconfig"

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

    # ANS1 (research/j81-long-term-subsystems.md's "Internal NAND storage",
    # docs/plans/2026-09-13-j81-ans1-observation-only.md): Hoolock's ans1
    # branch (ed8528f482a526371e59711645794c91fafb2b42, 27 commits ahead of
    # this project's pinned hoolockLinux base), reconciled onto this
    # project's own tree rather than built from ans1's source directly (as
    # kernel/hoolock-ans1-check.nix does for an isolated compile-only
    # check) -- this is the combined, bootable version.
    #
    # 0013/0014 add and enable the disabled ans/ans_mbox SoC nodes exactly
    # as ans1 wrote them (register windows, mailbox IRQs 36-39, PMGR power
    # domain), the same disabled-at-SoC/enabled-at-board split this
    # project's own UART3/UART5/SPI3 patches already use. One line
    # genuinely conflicted with this project's own tree (both ans1 and
    # patch 0001 add an entry to the same short t7001.dtsi aliases block)
    # -- reconciled by hand, verified byte-for-byte against a real patch
    # stack test before being written as these two clean patches; not a
    # semantic conflict, just two community patches both touching one
    # short list.
    patch -d "$out" -p1 < ${./patches/0013-t7001-add-ans1-node.patch}
    patch -d "$out" -p1 < ${./patches/0014-t7001-air2-enable-ans1.patch}

    # 0015: the driver itself (drivers/block/asp.c, new) plus the shared
    # RTKit/AKF-mailbox/macsmc framework changes ans1 needed underneath it
    # (drivers/soc/apple/rtkit.c, rtkit-crashlog.c, mailbox.c, and
    # drivers/mfd/macsmc.c) -- verified to apply cleanly on top of this
    # project's own patches above with no conflicts at all (17 files, zero
    # rejects).
    patch -d "$out" -p1 < ${./patches/0015-ans1-storage-driver-and-core-support.patch}

    # 0012: the observation-only safety hardening -- removes
    # ASP_CMD_WRITE_UNLOCK outright, forces every namespace including
    # user data read-only, adds a central write/flush rejection, and
    # turns three BUG()/BUG_ON() calls into graceful errors. The exact
    # same patch already cross-build verified in isolation by
    # kernel/hoolock-ans1-check.nix, applied here a second time against
    # the real, combined tree.
    patch -d "$out" -p1 < ${./patches/0012-ans1-asp-observation-only.patch}
  '';
  buildArgs = builtins.removeAttrs args [ "source" "hoolockConfig" "runCommand" ];
in
buildLinux (buildArgs // {
  version = "7.3.0-rc1";
  modDirVersion = "7.3.0-rc1";

  src = configuredSource;

  defconfig = "ipad_t7001_hoolock_ans1_test_defconfig";
  enableCommonConfig = false;
  autoModules = false;
  ignoreConfigErrors = true;
  buildDTBs = true;

  extraMeta = {
    branch = "hoolock-ans1-test";
    description = "Hoolock kernel for iPad Air 2 (A8X/T7001) with everything kernel/hoolock.nix has plus observation-only-hardened ANS1 storage -- a dedicated test payload, not the default";
    platforms = [ "aarch64-linux" ];
  };
} // (args.argsOverride or {}))
