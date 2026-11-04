{ buildLinux, runCommand, git, orchard, upstream, ... } @ args:

# Orchard's own apple-4k kernel, reproduced without its Podman toolchain: the upstream commit pinned in
# kernel/upstream.lock, every *.patch of each layer in kernel/series/apple-4k applied with `git apply` in path order
# (as kernel/build does), and kernel/configs/apple-4k/config. No local patches, so a hardware result on this kernel
# is a result for that Orchard revision (docs/touchdemo.md).
let
  configuredSource = runCommand "linux-orchard-main-apple-4k-source" { nativeBuildInputs = [ git ]; } ''
    mkdir -p "$out"
    cp -R ${upstream}/. "$out/"
    chmod -R u+w "$out"
    grep -q '^commit=${upstream.rev}$' ${orchard}/kernel/upstream.lock

    n=0
    for layer in $(grep -v '^#' ${orchard}/kernel/series/apple-4k | sed '/^[[:space:]]*$/d'); do
      for p in $(cd ${orchard}/kernel && find "$layer" -name '*.patch' | LC_ALL=C sort); do
        git -C "$out" apply --whitespace=nowarn "${orchard}/kernel/$p"
        n=$((n + 1))
      done
    done
    echo "applied $n Orchard patches"
    test "$n" -gt 100

    cp ${orchard}/kernel/configs/apple-4k/config "$out/arch/arm64/configs/orchard_main_defconfig"

    # GCC needs the same exhaustive return as the Hoolock kernel recipes (Orchard builds with clang).
    file="$out/drivers/video/backlight/apple_pmic_bl.c"
    if grep -q 'return ((cmd\[1\] & 7) << 8) | (cmd\[0\] & 0xff);' "$file"; then
      sed -i \
        's/return ((cmd\[1\] \& 7) << 8) | (cmd\[0\] \& 0xff);/&\n\t\tdefault:\n\t\t\treturn -EINVAL;/' \
        "$file"
    fi
  '';
  buildArgs = builtins.removeAttrs args [ "orchard" "upstream" "runCommand" "git" ];
in
buildLinux (buildArgs // {
  version = "7.3.0-rc1";
  modDirVersion = "7.3.0-rc1";
  src = configuredSource;
  defconfig = "orchard_main_defconfig";
  enableCommonConfig = false;
  autoModules = false;
  ignoreConfigErrors = true;
  buildDTBs = true;
  extraMeta = {
    branch = "orchard-main";
    description = "Orchard main's apple-4k kernel (upstream pin + full patch series + config), no local patches";
    platforms = [ "aarch64-linux" ];
  };
} // (args.argsOverride or {}))
