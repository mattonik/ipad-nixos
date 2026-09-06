# Known-working June 2022 kernel branch for the T7001 software-only control.
{ buildLinux
, runCommand
, source
, historicalConfig
, ...
} @ args:

let
  # buildLinux accepts a named defconfig, so install the published config in
  # the source tree rather than translating thousands of options into Nix.
  configuredSource = runCommand "linux-apple-5.19-t7001-source" {} ''
    mkdir -p "$out"
    cp -R ${source}/. "$out/"
    chmod -R u+w "$out"
    cp ${historicalConfig} "$out/arch/arm64/configs/ipad_t7001_defconfig"
  '';
  buildArgs = builtins.removeAttrs args [ "source" "historicalConfig" "runCommand" ];
in
buildLinux (buildArgs // {
  version = "5.19.0-rc1";
  modDirVersion = "5.19.0-rc1";

  src = configuredSource;

  # Preserve the config published with the historical HOWTO. It selects 4 KiB
  # pages, ARCH_APPLE, AIC, simplefb, watchdog, and DWC2.
  defconfig = "ipad_t7001_defconfig";
  enableCommonConfig = false;
  autoModules = false;
  ignoreConfigErrors = true;
  buildDTBs = true;

  extraMeta = {
    branch = "apple/v5.19-rc1";
    description = "June 2022 linux-apple control kernel for iPad Air 2";
    platforms = [ "aarch64-linux" ];
  };
} // (args.argsOverride or {}))
