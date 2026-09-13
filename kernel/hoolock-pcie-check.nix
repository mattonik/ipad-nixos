# Isolated compile-only check for the inert T7000 PCIe host skeleton. This
# kernel is exposed as its own flake package and is not used by any payload.
{ buildLinux
, runCommand
, source
, pcieConfig
, ...
} @ args:

let
  configuredSource = runCommand "linux-hoolock-pcie-check-t7001-source" {} ''
    mkdir -p "$out"
    cp -R ${source}/. "$out/"
    chmod -R u+w "$out"
    cp ${pcieConfig} "$out/arch/arm64/configs/ipad_t7001_pcie_check_defconfig"

    # The same unrelated GCC return-type fix required by every Hoolock build
    # in this repository.
    file="$out/drivers/video/backlight/apple_pmic_bl.c"
    grep -q 'return ((cmd\[1\] & 7) << 8) | (cmd\[0\] & 0xff);' "$file"
    sed -i \
      's/return ((cmd\[1\] \& 7) << 8) | (cmd\[0\] \& 0xff);/&\n\t\tdefault:\n\t\t\treturn -EINVAL;/' \
      "$file"

    patch -d "$out" -p1 < ${./patches/0016-pcie-apple-t7000-compile-only-skeleton.patch}
  '';
  buildArgs = builtins.removeAttrs args [ "source" "pcieConfig" "runCommand" ];
in
buildLinux (buildArgs // {
  version = "7.3.0-rc1";
  modDirVersion = "7.3.0-rc1";
  src = configuredSource;
  defconfig = "ipad_t7001_pcie_check_defconfig";
  enableCommonConfig = false;
  autoModules = false;
  ignoreConfigErrors = true;
  buildDTBs = true;

  extraMeta = {
    branch = "pcie-check";
    description = "Compile-only inert T7000 PCIe host skeleton for iPad Air 2; not wired into any boot payload";
    platforms = [ "aarch64-linux" ];
  };
} // (args.argsOverride or {}))
