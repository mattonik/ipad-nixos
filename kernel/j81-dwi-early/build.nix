# Two RAM payloads share one instrumented kernel and differ only in bootargs.
{ repo }:
let
  packages = (builtins.getFlake ("git+file://" + toString repo)).packages.x86_64-linux;
  base = packages.hoolock-wifi-kmod-kernel;
  control = builtins.storePath "/nix/store/xp08mmic2ggla3hw03xddabr8k119vz5-j81-gpu-pmgr-test-payload";
  testKernel = base.overrideAttrs (old: {
    patches = (old.patches or []) ++ [
      (builtins.path { path = ../patches/0123-apple-pmgr-pwrstate-stop-on-errors.patch; name = "gpu-pmgr-errors.patch"; })
      (builtins.path { path = ./early.patch; name = "j81-dwi-early.patch"; })
    ];
  });
  payload = hold: packages.m1n1-hoolock-wifi.overrideAttrs (old: {
    name = "j81-dwi-early-${if hold then "hold" else "control"}";
    buildCommand = ''
      mkdir -p "$out"
      for part in Pongo.bin m1n1.bin initramfs.gz; do cp "${control}/$part" "$out/$part"; done
      printf '%s j81_dwi_hold=${if hold then "1" else "0"}\n' "$(cat ${control}/bootargs)" > "$out/bootargs"
      gzip -n -c ${testKernel}/Image > "$out/Image.gz"
      dtc -I dtb -O dts ${testKernel}/dtbs/apple/t7001-j81.dtb \
        | sed -e '/^\tchosen {$/,/^\t};$/ s/framebuffer@0 {/framebuffer {/' \
        | dtc -I dts -O dtb -p 0x10000 -o "$out/t7001-j81.dtb"
      cat "$out/m1n1.bin" "$out/bootargs" "$out/t7001-j81.dtb" "$out/Image.gz" "$out/initramfs.gz" > "$out/m1n1-linux.bin"
      sha256sum "$out"/* > "$out/SHA256SUMS"
    '';
  });
in { kernel = testKernel; control = payload false; hold = payload true; }
