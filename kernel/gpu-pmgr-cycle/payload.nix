{ pkgs }:
let base = builtins.storePath "/nix/store/xp08mmic2ggla3hw03xddabr8k119vz5-j81-gpu-pmgr-test-payload";
in pkgs.stdenvNoCC.mkDerivation {
  pname = "j81-gpu-pmgr-cycle-payload";
  version = "1";
  dontUnpack = true;
  nativeBuildInputs = [ pkgs.dtc ];
  installPhase = ''
    mkdir -p "$out"
    for part in Pongo.bin m1n1.bin bootargs Image.gz initramfs.gz; do cp "${base}/$part" "$out/$part"; done
    dtc -I dtb -O dts "${base}/t7001-j81.dtb" \
      | sed '/experimental,j81-gpu-test-no-poweroff;/d' \
      | dtc -I dts -O dtb -p 0x10000 -o "$out/t7001-j81.dtb"
    cat "$out/m1n1.bin" "$out/bootargs" "$out/t7001-j81.dtb" \
      "$out/Image.gz" "$out/initramfs.gz" > "$out/m1n1-linux.bin"
    sha256sum "$out"/* > "$out/SHA256SUMS"
  '';
}
