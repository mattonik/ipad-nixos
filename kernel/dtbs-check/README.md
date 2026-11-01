# dtbs_check: the J81 device tree against dt-schema

Builds `apple/t7001-j81.dtb` with `CHECK_DTBS=y`, which runs dtc's own checks
and `dt-validate` against the bindings in the same kernel tree. It catches
missing required properties, wrong cell counts, unknown compatibles and
similar mistakes before a DTB ever boots.

```bash
tools/builder.sh status        # the builder must be up; see docs/build-infrastructure.md
nix build .#packages.aarch64-linux.j81-dtbs-check -o result-j81-dtbs-check -L
```

- The source is the patched tree of the Wi-Fi base kernel
  (`hoolock-pcie-j81-wifi-h1b-kernel.src`), so all of our DT patches are
  checked, configured with that kernel's own defconfig. It builds natively
  on the aarch64-linux builder in about a minute.
- Every warning is normalized (build paths stripped, duplicates merged) and
  compared with `t7001-j81.known-warnings`. A warning that isn't on that list
  fails the build. A listed warning that has gone away is printed, so the
  list can be trimmed.
- `result-j81-dtbs-check/` holds `warnings.txt` (everything reported now),
  `new-warnings.txt`, `gone-warnings.txt`, `raw.log` and the DTB.

To accept a warning on purpose, copy its line from `warnings.txt` into
`t7001-j81.known-warnings`, with a comment line above it saying why.
