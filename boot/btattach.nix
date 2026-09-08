# Minimal, dependency-free build of BlueZ's btattach tool for the
# postmarketOS debug initramfs -- BT-1 (docs/plans/2026-09-08-j81-bluetooth-
# battery-adt.md) confirmed UART3's hardware description is correct. The
# transport-only DT deliberately has no Bluetooth child, so this tool attaches
# the HCI UART line discipline and lets us test the raw UART independently.
#
# btattach.c itself only needs libc + BlueZ's own "src/shared/*" helper
# code (confirmed by reading Makefile.tools:
# `tools_btattach_LDADD = src/libshared-mainloop.la`) -- but BlueZ's
# top-level `./configure` unconditionally requires glib and dbus even to
# configure at all, no matter which tools you actually want (checked
# configure.ac directly: `PKG_CHECK_MODULES(GLIB, ...)` / `(DBUS, ...)`
# have no enabling `if` guard). Building the real package would pull in
# that whole dependency chain just to throw it away -- confirmed painfully
# slow in practice (killed after 24+ minutes with zero visibility into
# what it was even doing). This compiles the exact source list
# `libshared-mainloop.la` uses directly instead, bypassing
# autotools/configure entirely. The C file list is mechanically derived
# from Makefile.am's `shared_sources` variable, not hand-transcribed.
{ stdenvCross, bluezSrc, bluezVersion }:

stdenvCross.mkDerivation {
  pname = "btattach";
  # Tracks whatever BlueZ version this nixpkgs pin actually carries (5.84 as
  # of this nixpkgs revision, not the 5.87 seen during earlier interactive
  # testing against a different <nixpkgs>) rather than a value that can
  # silently drift from the real source.
  version = bluezVersion;
  src = bluezSrc;

  dontConfigure = true;

  buildPhase = ''
    runHook preBuild
    # Only the files btattach.c's own #include list actually touches --
    # not the whole shared_sources bundle libshared-mainloop.la builds
    # for every tool (most of it is unrelated LE GATT/audio-profile code
    # that pulls in its own further dependencies, like lib/uuid.c, for
    # functionality btattach never calls). Found this exact minimal set
    # iteratively against real linker errors, not guessed in one shot.
    # -static: the postmarketOS debug initramfs's musl build is a
    # separate, externally-sourced artifact (not built by this project),
    # so its ABI isn't guaranteed to match this Nix-built musl exactly --
    # avoid the whole question by not dynamically linking against it.
    $CC -O2 -Wall -static -DVERSION="\"$version\"" -I. -Ilib \
      tools/btattach.c \
      src/shared/util.c src/shared/queue.c src/shared/hci.c \
      src/shared/mainloop.c src/shared/mainloop-notify.c \
      src/shared/io-mainloop.c src/shared/timeout-mainloop.c \
      -o btattach
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    mkdir -p "$out/bin"
    cp btattach "$out/bin/btattach"
    runHook postInstall
  '';
}
