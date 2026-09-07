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
