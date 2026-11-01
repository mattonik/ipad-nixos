# dt-schema check of the J81 device tree (kernel/dtbs-check/README.md).
#
# Builds apple/t7001-j81.dtb from the exact patched source tree of the Wi-Fi base kernel with CHECK_DTBS=y, so dtc and
# dt-validate check it against the bindings in that same tree. Every warning is normalized (build paths stripped) and compared
# with the reviewed list in t7001-j81.known-warnings: a warning not on the list fails the build. A listed warning that is gone
# is reported, so the list can be trimmed. Built natively on aarch64-linux; never part of a payload.
{ stdenv
, kernelSrc
, defconfig
, python3
, dtschema
, bc
, bison
, flex
, perl
, which
}:

let
  # dtschema 2025.12 crashes (KeyError in check_duplicate_property_types) while printing a "multiple incompatible types" warning
  # for a binding whose $id has no entry in its schema table, which the 7.3-rc1 bindings trigger. Print the id instead of crashing;
  # the warning itself is about upstream bindings, not about our DTB.
  dtschemaFixed = dtschema.overridePythonAttrs (old: {
    postPatch = (old.postPatch or "") + ''
      substituteInPlace dtschema/validator.py --replace-fail \
        "{self.schemas[sch_id]['\$filename']}" \
        "{self.schemas.get(sch_id, {}).get('\$filename', sch_id)}"
    '';
  });
in
stdenv.mkDerivation {
  name = "j81-dtbs-check";
  src = kernelSrc;

  nativeBuildInputs = [ python3 dtschemaFixed bc bison flex perl which ];

  dontConfigure = true;
  dontFixup = true;

  postPatch = ''
    patchShebangs scripts
  '';

  buildPhase = ''
    runHook preBuild
    mkdir -p "$out"
    make ARCH=arm64 ${defconfig} >/dev/null
    make ARCH=arm64 -j"$NIX_BUILD_CORES" CHECK_DTBS=y apple/t7001-j81.dtb 2> "$out/raw.log" || {
      cat "$out/raw.log" >&2
      echo "the J81 DTB did not build" >&2
      exit 1
    }
    cp arch/arm64/boot/dts/apple/t7001-j81.dtb "$out/"

    # Only diagnostics about the DTB: drop make's progress lines and dt-mk-schema's own complaints about upstream bindings
    # (lines starting with a schema URL), strip the build directory, fold dt-validate's indented "from schema $id" line into
    # the warning above it, merge duplicates.
    { grep -v -e '^  [A-Z]' -e '^make' -e 'yamllint' -e '^http://devicetree.org/schemas/' "$out/raw.log" || true; } \
      | sed -e "s|$PWD/||g" \
      | awk '/^[ \t]/ { sub(/^[ \t]+/, ""); prev = prev " [" $0 "]"; next }
             { if (prev != "") print prev; prev = $0 }
             END { if (prev != "") print prev }' \
      | LC_ALL=C sort -u > "$out/warnings.txt"
    { grep -v -e '^#' -e '^$' ${./t7001-j81.known-warnings} || true; } | LC_ALL=C sort -u > known.txt
    LC_ALL=C comm -23 "$out/warnings.txt" known.txt > "$out/new-warnings.txt"
    LC_ALL=C comm -13 "$out/warnings.txt" known.txt > "$out/gone-warnings.txt"

    echo "J81 dtbs_check: $(wc -l < "$out/warnings.txt") warning(s), $(wc -l < "$out/new-warnings.txt") new, $(wc -l < "$out/gone-warnings.txt") fixed"
    if [ -s "$out/gone-warnings.txt" ]; then
      echo "No longer reported (trim kernel/dtbs-check/t7001-j81.known-warnings):"
      cat "$out/gone-warnings.txt"
    fi
    if [ -s "$out/new-warnings.txt" ]; then
      echo "New dtbs_check warnings for t7001-j81.dtb:" >&2
      cat "$out/new-warnings.txt" >&2
      exit 1
    fi
    runHook postBuild
  '';

  installPhase = "true";

  meta = {
    description = "dt-schema check of the J81 device tree against a reviewed warning list";
    platforms = [ "aarch64-linux" ];
  };
}
