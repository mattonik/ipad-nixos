#!/usr/bin/env bash
# Run the complete DFU -> PongoOS -> m1n1 loop for one private payload.
# The only unavoidable manual action is a Lightning replug if macOS does not
# re-enumerate the device after one of the two USB identity changes.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAYLOAD="${1:-}"
PALERA1N="${PALERA1N:-$ROOT/boot/vendor/palera1n-macos-arm64}"
PONGO="${PONGO:-$ROOT/boot/Pongo.bin}"
PYTHON="${PYTHON:-/opt/homebrew/bin/python3}"
# pyusb lives under a persistent GC root (the Nix store copy is garbage-collected otherwise); libusb comes from Homebrew.
PYUSB="${PYUSB:-$ROOT/artifacts/live/gcroot-pyusb/lib/python3.14/site-packages}"
export DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}"
export PYTHONPATH="$PYUSB${PYTHONPATH:+:$PYTHONPATH}"

if [[ -z "$PAYLOAD" || ! -d "$PAYLOAD" ]]; then
  echo "Usage: $0 <private-payload-directory>" >&2
  exit 2
fi
for file in "$PALERA1N" "$PONGO" "$PAYLOAD/m1n1-linux.bin"; do
  [[ -f "$file" ]] || { echo "Missing: $file" >&2; exit 1; }
done
[[ -d "$PYUSB" ]] || { echo "Missing pyusb GC root: $PYUSB" >&2; exit 1; }
command -v sudo >/dev/null || { echo "sudo is required for palera1n" >&2; exit 1; }
[[ -x "$PYTHON" ]] || { echo "Python not executable: $PYTHON" >&2; exit 1; }

# Verify the private manifest first (hashes, run token, policy).
"$PYTHON" "$ROOT/boot/assemble_private_wifi_payload.py" --verify "$PAYLOAD" >/dev/null

echo "1/2 DFU -> PongoOS (replug only when palera1n asks)"
sudo "$PALERA1N" --pongo-shell --override-pongo "$PONGO" --debug-logging

# palera1n --pongo-shell stays attached until you leave its shell (Ctrl-C/exit); the loader runs afterwards.
echo "2/2 PongoOS -> m1n1 (waiting for USB 05ac:4141 if needed)"
exec "$PYTHON" "$ROOT/boot/load_m1n1.py" "$PAYLOAD/m1n1-linux.bin"
