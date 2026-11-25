#!/usr/bin/env bash
# Start pinned PongoOS, then run the guarded J81 GPU fork-point test.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PALERA1N="${PALERA1N:-$ROOT/boot/vendor/palera1n-macos-arm64}"
PONGO="${PONGO:-$ROOT/boot/Pongo.bin}"
PLAN="$ROOT/artifacts/live/private/gpu-offline/gfx-bridge-plan.bin"
PYTHON="${PYTHON:-/opt/homebrew/bin/python3}"
PYUSB="${PYUSB:-$ROOT/artifacts/live/gcroot-pyusb/lib/python3.14/site-packages}"
export DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}"
export PYTHONPATH="$PYUSB${PYTHONPATH:+:$PYTHONPATH}"

check_hash() {
  local file="$1" expected="$2"
  [[ -f "$file" ]] || { echo "Missing: $file" >&2; exit 1; }
  [[ "$(shasum -a 256 "$file" | cut -d ' ' -f 1)" == "$expected" ]] || {
    echo "SHA-256 mismatch: $file" >&2
    exit 1
  }
}

check_hash "$PALERA1N" 950c357b6ae5df36128f6e42a3c6d371e55aeb69a5afcde276f096276210d0c9
check_hash "$PONGO" 1e5543fd8e6dbd84c334b87d71aa473f4d347c2ba8a5e863b6e10f18461c7575
check_hash "$PLAN" 1c7b3839da2e7aa914a393e914a7a427c12190293ba5d2b50fe06cf4d8df6435
[[ -d "$PYUSB" ]] || { echo "Missing pyusb GC root: $PYUSB" >&2; exit 1; }
[[ -x "$PYTHON" ]] || { echo "Python not executable: $PYTHON" >&2; exit 1; }
[[ -x "$PALERA1N" ]] || { echo "palera1n is not executable: $PALERA1N" >&2; exit 1; }
command -v sudo >/dev/null || { echo "sudo is required for palera1n" >&2; exit 1; }
"$PYTHON" "$ROOT/boot/pongo_gpu_split.py" --help >/dev/null

echo "WARNING: a core-read hang freezes PongoOS with its watchdog off."
echo "Recovery requires a forced restart back into DFU; no filesystem is mounted."
echo "1/2 DFU -> PongoOS (exit the Pongo shell without booting another payload)"
sudo "$PALERA1N" --pongo-shell --override-pongo "$PONGO" --debug-logging
echo "2/2 PongoOS GPU split test"
exec "$PYTHON" "$ROOT/boot/pongo_gpu_split.py" "$@"
