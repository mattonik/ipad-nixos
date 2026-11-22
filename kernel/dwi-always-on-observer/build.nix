# TEST ONLY. Observer kernel (0123 + research/probes/j81-linux-gfx-request.patch, as kernel/gpu-pmgr-cycle with traceGfxRequests; notes sha a2dda27) (dwi always-on 0125 is now in the base kernel, kernel/hoolock-pcie-j81-wifi-h1b.nix). Keeps the PMGR "dwi" power domain on (apple,always-on) in the J81 device tree.
# Boot files (Pongo.bin, m1n1.bin, bootargs, initramfs) come from the same control payload as kernel/gpu-pmgr-once.
{ repo }:
let
  packages = (builtins.getFlake ("git+file://" + toString repo)).packages.x86_64-linux;
  base = packages.hoolock-wifi-kmod-kernel;
  control = builtins.storePath "/nix/store/7mcs6gjidim1p2zbfxjdbibfm45kknnr-ipad-air2-m1n1-hoolock-wifi";
  testKernel = base.overrideAttrs (old: {
    patches = (old.patches or []) ++ [
      (builtins.path { path = ../patches/0123-apple-pmgr-pwrstate-stop-on-errors.patch; name = "gpu-pmgr-errors.patch"; })
      (builtins.path { path = ../../research/probes/j81-linux-gfx-request.patch; name = "j81-linux-gfx-request.patch"; })
    ];
  });
  testPayload = packages.m1n1-hoolock-wifi.overrideAttrs (old: {
    name = "j81-dwi-always-on-observer-payload";
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
  payload = testPayload;
}
