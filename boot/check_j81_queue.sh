#!/bin/sh
# Verify that every artifact of the 2026-11-20 test queue is present and intact, and re-run the host tests.
# No device, no builder VM, no network. usage: boot/check_j81_queue.sh
set -u
cd "$(dirname "$0")/.."
PY=/opt/homebrew/bin/python3; P=artifacts/live/private; fail=0
ok() { echo "ok   $*"; }; bad() { echo "FAIL $*"; fail=1; }
for d in j81-ios-state-probes j81-linux-w22000-write-experiment j81-linux-pll-write-experiment j81-linux-reorder-experiment j81-linux-tvm-write-experiment j81-map-probe-experiment; do
	if (cd $P/$d && shasum -a 256 -c SHA256SUMS >/dev/null 2>&1); then ok "checksums $d"; else bad "checksums $d"; fi
done
shasum -a 256 -c $P/j81-observer-paired-20261119-v1/SHA256SUMS >/dev/null 2>&1 && ok "observer bundle checksums" || bad "observer bundle checksums"
for v in fender-pmgrx-cpu48 fender-cpu194 fender-cpu20 fender-cpu190 fender-cpu150 fender-cpu1a0 fender-cpu1b0 page14 fender pmgrx cpu48 cpu194; do
	[ -f $P/j81-ios-state-probes/checkra1n-kpf-pongo-j81-$v ] && ok "iPadOS probe $v" || bad "iPadOS probe $v"
done
R=$P/j81-linux-w22000-write-experiment/runner/boot
for t in test_j81_observer_w22000_write_flow test_j81_observer_paired_campaign; do
	(cd $R && PYTHONDONTWRITEBYTECODE=1 $PY $t.py >/dev/null 2>&1) && ok "test $t" || bad "test $t"
done
(cd $R && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=$PWD/../../../../gcroot-pyusb/lib/python3.14/site-packages PYTHONDONTWRITEBYTECODE=1 $PY j81_observer_paired_campaign.py --verify-only --bundle $PWD/../../../j81-observer-paired-20261119-v1 >/dev/null 2>&1) && ok "w22000-write campaign --verify-only" || bad "w22000-write campaign --verify-only"
(cd boot && for t in test_make_j81_ios_state_probes test_decode_j81_ios_probe test_j81_map_probe_campaign test_j81_linux_pmgr_words; do PYTHONDONTWRITEBYTECODE=1 $PY $t.py >/dev/null 2>&1 && echo "ok   test $t" || echo "FAIL test $t"; done) | tee /tmp/queue-tests.txt | grep FAIL && fail=1
grep -c '^ok' /tmp/queue-tests.txt | sed 's/^/ok   repo tests passed: /'
[ $fail = 0 ] && echo "QUEUE READY" || { echo "QUEUE NOT READY"; exit 1; }
