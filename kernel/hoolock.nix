# Hoolock-tracked Linux 7.3-rc1 kernel -- a newer-kernel candidate for the
# T7001 USB device-to-host TX fault found in Round 8 (see
# research/t7001-usb-next.md's "Decision, 2026-09-07"). Restores a real
# dwc2 DMA hardware-capability check instead of the historical (5.19-rc1)
# fork's hardcoded PIO fallback, and uses a configfs-only USB gadget setup
# rather than the legacy g_ether Kconfig knobs the historical/modern
# kernels use.
{ buildLinux
, runCommand
, source
, hoolockConfig
, ...
} @ args:

let
  # Same pattern as kernel/historical.nix: buildLinux accepts a named
  # defconfig, so install the (patched) published config in the source
  # tree rather than translating it into Nix's structuredExtraConfig.
  configuredSource = runCommand "linux-hoolock-7.3-t7001-source" {} ''
    mkdir -p "$out"
    cp -R ${source}/. "$out/"
    chmod -R u+w "$out"
    cp ${hoolockConfig} "$out/arch/arm64/configs/ipad_t7001_hoolock_defconfig"

    # drivers/video/backlight/apple_pmic_bl.c's apple_pmic_bl_get_brightness()
    # switches on enum apple_pmic_type (PMIC_TYPE_ANYA, PMIC_TYPE_ARIA) with
    # no default case, so GCC can't prove every path returns a value and
    # fails the build under -Werror=return-type (this project's GCC cross
    # toolchain; Hoolock's own recommended Clang/LLVM apparently doesn't
    # flag it). Previously worked around by disabling
    # CONFIG_BACKLIGHT_APPLE_PMIC entirely, since backlight wasn't needed
    # for the USB investigation this kernel was first built for. This
    # driver already has a full, matching, enabled DT node
    # (i2c@20a110000/pmic@3c/backlight@600, "apple,arabela-pmic-bl",
    # status="okay") and no other issue, so it's now fixed properly with
    # the standard, minimal correction instead: an explicit unreachable
    # default case, which changes no behavior for the two real enum values.
    file="$out/drivers/video/backlight/apple_pmic_bl.c"
    grep -q 'return ((cmd\[1\] & 7) << 8) | (cmd\[0\] & 0xff);' "$file"
    sed -i \
      's/return ((cmd\[1\] \& 7) << 8) | (cmd\[0\] \& 0xff);/&\n\t\tdefault:\n\t\t\treturn -EINVAL;/' \
      "$file"

    # BT-1 (docs/plans/2026-09-08-j81-bluetooth-battery-adt.md): describe
    # and enable UART3, the BCM43540 Bluetooth combo chip's HCI UART
    # transport. Register base, IRQ, clock gate, and the TX/RTS pinmux
    # were independently decoded from a real J81 ADT capture and confirmed
    # byte-for-byte against the T7001-family J82 sibling reference (see
    # the plan doc's "J81 ADT evidence" section) -- not guessed. As real
    # DTS patches (not sed) since the insertions are multi-line and this
    # is much easier to review as a diff.
    patch -d "$out" -p1 < ${./patches/0001-t7001-add-uart3-node.patch}
    patch -d "$out" -p1 < ${./patches/0002-t7001-air2-enable-uart3.patch}

    # BAT-1 (docs/plans/2026-09-08-j81-bluetooth-battery-adt.md,
    # research/j81-battery-hdq.md): a later audit found the "Samsung UART
    # has no serdev support" conclusion behind BT-1's transport-only DTS
    # above was wrong -- uart_add_one_port() already registers a serdev
    # controller through the common serial core whenever the UART's DT
    # node has a child. TI HDQ needs 2 stop bits, which the generic
    # serdev API has no way to request even though the underlying tty
    # layer already honors CSTOPB; this adds that one missing operation,
    # mirroring the existing set_parity op exactly (same three-file
    # shape: enum + controller op + public helper in serdev.h, the
    # helper's dispatch in core.c, the real ktermios-based
    # assert-then-verify implementation in serdev-ttyport.c).
    patch -d "$out" -p1 < ${./patches/0003-serdev-add-stop-bit-selection.patch}

    # BAT-2: the HDQ-over-UART frontend driver itself, reusing the
    # existing bq27xxx core (struct bq27xxx_device_info,
    # bq27xxx_battery_setup/teardown) rather than duplicating its
    # power-supply property handling. Identifies the real chip via a
    # live TI Control() DEVICE_TYPE readback at probe rather than
    # trusting the ADT's "bq27540" compatible string, which is a chip
    # *family* hint, not a specific silicon revision.
    patch -d "$out" -p1 < ${./patches/0004-add-bq27xxx-hdq-uart-frontend.patch}

    # BAT-3: describe and enable UART5 and the gauge child. Register
    # base, IRQ, clock gate and the single AP GPIO34 pinmux entry were
    # decoded from the same real J81 ADT capture and the same
    # byte-identical-to-uart5-function-tx cross-check as BT-1's UART3
    # numbers. Unlike serial3, the gauge ships as a real serdev child
    # from the start -- BAT-2's driver needs one to bind to, and the
    # serdev correction above means it will actually probe.
    patch -d "$out" -p1 < ${./patches/0005-t7001-add-uart5-node.patch}
    patch -d "$out" -p1 < ${./patches/0006-t7001-air2-enable-uart5-battery.patch}

    # CHG-1: expose the D2207's already-decoded charger settings through the
    # standard power-supply class. This is read-only until an external meter
    # and a controlled write test establish the safe charging path.
    patch -d "$out" -p1 < ${./patches/0010-j81-d2207-readonly-charger.patch}

    # TOUCH-1 (docs/plans/2026-09-09-j81-touch-spi3.md): the older Apple SPI
    # controller variant this SoC uses, ported from Hoolock's tests/kat-spi
    # (c065201) -- the more complete of that repository's two SPI branches,
    # checked directly rather than taken from the bring-up plan's citation of
    # the thinner tests/spi. Two real defects were dropped rather than
    # carried: a dev_info() on every transfer completion and poll iteration,
    # and a bare global `bool defered` that forced the first probe of the
    # module's life to return -EPROBE_DEFER unconditionally. A later review
    # fixed four more: reversed MC/S5L bit-order selection, a normal
    # completion IRQ returning IRQ_NONE, completion reinitialization after
    # IRQ enable, and an uninitialized S5L RX word count.
    # kernel/test_spi_s5l_patch.py guards those invariants.
    #
    # CONFIG_SPI_APPLE is already =y in the pinned upstream config_16k, so
    # unlike BAT-2 this needs no patchedHoolockConfig entry.
    patch -d "$out" -p1 < ${./patches/0007-spi-apple-add-s5l8960x-support.patch}

    # TOUCH-1's DTS half: describe SPI3 (0008, added disabled) and enable it
    # on J81 (0009). Register window, IRQ 155, clock gate and the CS0 pin
    # were decoded byte-exact from the same real J81 ADT capture as BT-1's
    # and BAT-3's numbers. `power-domains = <&ps_spi3>` was confirmed against
    # the built DTB to resolve to a real, distinct PMGR power-controller
    # (@20198, label "spi3"), not an alias of another peripheral's domain --
    # this matters because genpd powers the domain before probe, and an
    # Apple SoC faults or hangs on register access to an unpowered block.
    #
    # No touch child node yet: the child's packed multi-word `reg` and its
    # "KLCT" PMGR clock arguments are still undecoded, and TOUCH-2 owns them.
    # The CS0 pinmux APPLE_PINMUX(51, 1) is still provisional -- BAT-4
    # disproved the ADT-flags-low-byte theory that first suggested it,
    # without contradicting function 1 itself -- so a bounded live A/B test
    # remains a TOUCH-1 hardware gate.
    patch -d "$out" -p1 < ${./patches/0008-t7001-add-spi3-node.patch}
    patch -d "$out" -p1 < ${./patches/0009-t7001-air2-enable-spi3.patch}
  '';
  buildArgs = builtins.removeAttrs args [ "source" "hoolockConfig" "runCommand" ];
in
buildLinux (buildArgs // {
  version = "7.3.0-rc1";
  modDirVersion = "7.3.0-rc1";

  src = configuredSource;

  defconfig = "ipad_t7001_hoolock_defconfig";
  enableCommonConfig = false;
  autoModules = false;
  ignoreConfigErrors = true;
  buildDTBs = true;

  extraMeta = {
    branch = "hoolock";
    description = "Hoolock-tracked Linux 7.3-rc1 kernel for iPad Air 2 (A8X/T7001): restored dwc2 DMA capability check, configfs-only USB gadget";
    platforms = [ "aarch64-linux" ];
  };
} // (args.argsOverride or {}))
