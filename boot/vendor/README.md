# Vendored third-party binaries

Not committed (see `.gitignore`) -- this file is the tracked record of what
should be here and why, so it can be replaced if lost.

## `palera1n-macos-arm64`

The standalone macOS arm64 palera1n CLI used for the project's real boot
recipe (`sudo boot/vendor/palera1n-macos-arm64 --pongo-shell --override-pongo
...`, see `README.md`'s "Boot status" section).

- **Version**: v2.4
- **SHA-256**: `950c357b6ae5df36128f6e42a3c6d371e55aeb69a5afcde276f096276210d0c9`
- **Why here, not `/tmp`**: it lived in `/tmp` until 2026-09-12, when a Mac
  reboot cleared it mid-project and the boot recipe silently broke
  (`command not found`) right when hardware testing was about to start.
  `/tmp` is cleared on reboot; this directory is not.
- **Source**: the official palera1n releases
  (https://github.com/palera1n/palera1n), arm64 macOS build. If this file is
  ever missing, redownload the matching release build and verify against the
  hash above before using it -- this tool runs a bootrom exploit against
  connected hardware, don't run an unverified binary for that.
- Must be `chmod +x` after any fresh download; GitHub release downloads and
  browser downloads don't preserve the executable bit.
