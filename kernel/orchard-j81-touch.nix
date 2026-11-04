{ buildLinux, runCommand, source, ... } @ args:

let
  configuredSource = runCommand "linux-orchard-j81-touch-source" {} ''
    mkdir -p "$out"
    cp -R ${source}/. "$out/"
    chmod -R u+w "$out"

    patch -d "$out" -p1 < ${./orchard-touch-patches/0001-spi-apple-t7000-pio.patch}
    patch -d "$out" -p1 < ${./orchard-touch-patches/0002-apple-z2-optional-display-sync.patch}
    patch -d "$out" -p1 < ${./orchard-touch-patches/0003-apple-z2-j81-runtime-header.patch}
    patch -d "$out" -p1 < ${./orchard-touch-patches/0004-apple-z2-j81-family-22.patch}

    # GCC needs the same exhaustive return as the Hoolock kernel recipes.
    file="$out/drivers/video/backlight/apple_pmic_bl.c"
    grep -q 'return ((cmd\[1\] & 7) << 8) | (cmd\[0\] & 0xff);' "$file"
    sed -i \
      's/return ((cmd\[1\] \& 7) << 8) | (cmd\[0\] \& 0xff);/&\n\t\tdefault:\n\t\t\treturn -EINVAL;/' \
      "$file"
  '';
  buildArgs = builtins.removeAttrs args [ "source" "runCommand" ];
in
buildLinux (buildArgs // {
  version = "7.3.0-rc1";
  modDirVersion = "7.3.0-rc1";
  src = configuredSource;
  defconfig = "orchard_apple4k_defconfig";
  enableCommonConfig = false;
  autoModules = false;
  ignoreConfigErrors = true;
  buildDTBs = true;
  extraMeta = {
    branch = "orchard-j81-touch";
    description = "Orchard J81 kernel with bounded SPI and continuous touch reporting";
    platforms = [ "aarch64-linux" ];
  };
} // (args.argsOverride or {}))
