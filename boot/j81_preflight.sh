#!/usr/bin/env bash
# Read-only go/no-go check of the live J81 boot before staging a test.
# It only reads files on the iPad (no /dev/mem, no module loads, no writes).
#
#   boot/j81_preflight.sh <test> [host]
#   tests: gpu-pmgr-once   GFX power-up through gpu-pmgr-once.ko
#          perf-peek       read-only gpu-pmgr-perf-peek
#
# PREFLIGHT_TRANSCRIPT=<file> evaluates a saved transcript instead of
# connecting (used by boot/test_j81_preflight.py).
set -u
TEST="${1:-}"
HOST="${2:-172.16.42.1}"
GPU_NOTES=82ff70e850df341559fb775819962a9787a7bd85712a04b210d0fbfd407b7014
GFX_NODE=/proc/device-tree/soc/power-management@20e000000/power-controller@20320

case "$TEST" in
  gpu-pmgr-once|perf-peek) ;;
  *) echo "usage: $0 gpu-pmgr-once|perf-peek [host]" >&2; exit 2 ;;
esac

probe() {
  # One line per fact, all between two markers. Every command only reads.
  cat <<CMD
echo PF_BEGIN
echo NOTES=\$(sha256sum /sys/kernel/notes | cut -d ' ' -f 1)
[ -e '$GFX_NODE/experimental,j81-gpu-test-no-poweroff' ] && echo DT_GUARD=yes || echo DT_GUARD=no
[ -d /sys/module/gpu_pmgr_once ] && echo MOD_PMGR_ONCE=yes || echo MOD_PMGR_ONCE=no
[ -d /sys/devices/gpu-pmgr-once ] && echo PMGR_ONCE_DEV=yes || echo PMGR_ONCE_DEV=no
[ -c /dev/mem ] && echo DEVMEM=yes || echo DEVMEM=no
echo MODULES=\$(cut -d ' ' -f 1 /proc/modules | tr '\n' ',')
echo UPTIME=\$(cut -d ' ' -f 1 /proc/uptime)
echo TMP=\$(ls /tmp | tr '\n' ',')
echo PF_END
CMD
}

if [ -n "${PREFLIGHT_TRANSCRIPT:-}" ]; then
  raw=$(cat "$PREFLIGHT_TRANSCRIPT")
else
  command -v nc >/dev/null || { echo "NO-GO: nc not found" >&2; exit 1; }
  raw=$( (sleep 1; probe; sleep 3) | nc "$HOST" 23 | LC_ALL=C tr -cd '[:print:]\n')
fi
facts=$(printf '%s\n' "$raw" | sed -n '/^PF_BEGIN$/,/^PF_END$/p' | grep -E '^[A-Z_]+=')
if ! printf '%s\n' "$raw" | grep -qx PF_END; then
  echo "NO-GO: no complete answer from $HOST (USB networking down?)"
  exit 1
fi
get() { printf '%s\n' "$facts" | sed -n "s/^$1=//p" | tail -1; }

echo "boot: uptime $(get UPTIME) s, notes $(get NOTES | cut -c1-12)"
echo "      modules: $(get MODULES)"
echo "      /tmp: $(get TMP)"
fail=0
need() { # name actual expected why
  if [ "$2" = "$3" ]; then echo "  ok   $1 = $2"
  else echo "  FAIL $1 = ${2:-?} (need $3): $4"; fail=1; fi
}
case "$TEST" in
  gpu-pmgr-once)
    need kernel "$(get NOTES)" "$GPU_NOTES" "module is built for the GPU-test kernel"
    need dt-guard "$(get DT_GUARD)" yes "boot the gcroot-gpu-pmgr-once-payload device tree"
    need module-loaded "$(get MOD_PMGR_ONCE)" no "already loaded this boot; the power-up is one-shot"
    need consumer-dev "$(get PMGR_ONCE_DEV)" no "a power-up consumer already exists this boot"
    ;;
  perf-peek)
    need devmem "$(get DEVMEM)" yes "the read needs /dev/mem"
    ;;
esac
if [ "$fail" -eq 0 ]; then echo "GO: $TEST"; else echo "NO-GO: $TEST"; fi
exit "$fail"
