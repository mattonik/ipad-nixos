# TEST ONLY. This never changes the control payload or accesses the iPad.
{ repo }:
let
  packages = (builtins.getFlake ("git+file://" + toString repo)).packages.x86_64-linux;
  base = packages.hoolock-wifi-kmod-kernel;
  control = builtins.storePath "/nix/store/7mcs6gjidim1p2zbfxjdbibfm45kknnr-ipad-air2-m1n1-hoolock-wifi";
  testKernel = base.overrideAttrs (old: {
    patches = (old.patches or []) ++ [
      (builtins.path { path = ../patches/0123-apple-pmgr-pwrstate-stop-on-errors.patch; name = "gpu-pmgr-errors.patch"; })
      (builtins.path { path = ../patches/0124-j81-gpu-pmgr-test-node.patch; name = "gpu-pmgr-test-node.patch"; })
    ];
  });
  testModule = packages.j81-kmod-spi-apple.overrideAttrs (old: {
    src = builtins.path { path = ./.; name = "gpu-pmgr-once-src"; };
    makeFlags = map (flag: builtins.replaceStrings [ "${base.dev}" ] [ "${testKernel.dev}" ] flag) old.makeFlags;
  });
  testPayload = packages.m1n1-hoolock-wifi.overrideAttrs (old: {
    name = "j81-gpu-pmgr-test-payload";
    buildCommand = ''
      mkdir -p "$out"
      control=${control}
      for part in Pongo.bin m1n1.bin bootargs initramfs.gz; do
        cp "$control/$part" "$out/$part"
      done
      gzip -n -c ${testKernel}/Image > "$out/Image.gz"
      dtc -I dtb -O dts ${testKernel}/dtbs/apple/t7001-j81.dtb \
        | sed -e '/^\tchosen {$/,/^\t};$/ s/framebuffer@0 {/framebuffer {/' \
        | dtc -I dts -O dtb -p 0x10000 -o "$out/t7001-j81.dtb"
      cat "$out/m1n1.bin" "$out/bootargs" "$out/t7001-j81.dtb" \
        "$out/Image.gz" "$out/initramfs.gz" > "$out/m1n1-linux.bin"
      sha256sum "$out/Pongo.bin" "$out/m1n1.bin" "$out/m1n1-linux.bin" > "$out/SHA256SUMS"
    '';
  });
in {
  kernel = testKernel;
  module = testModule;
  payload = testPayload;
}
