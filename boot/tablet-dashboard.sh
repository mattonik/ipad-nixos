#!/bin/sh
# Read-only tablet dashboard: a refreshing text screen built on tablet-status.
# Never launched automatically. It only reads: it runs tablet-status, reads two
# log/pid files and lists processes. No control action, no writes.
#
#   tablet-dashboard [--once] [--interval SECONDS]     Ctrl-C quits
#
# Overridable for tests: TABLET_STATUS (command), POLICY_LOG, DROPBEAR_PID.
TABLET_STATUS=${TABLET_STATUS:-tablet-status}
POLICY_LOG=${POLICY_LOG:-/var/log/charging-policy.log}
DROPBEAR_PID=${DROPBEAR_PID:-/var/run/dropbear.pid}
INTERVAL=5
ONCE=

while [ $# -gt 0 ]; do
	case $1 in
	--once) ONCE=1 ;;
	--interval)
		shift
		case ${1:-} in "" | *[!0-9]*) echo "usage: tablet-dashboard [--once] [--interval N]" >&2; exit 2 ;; esac
		INTERVAL=$1
		[ "$INTERVAL" -ge 1 ] || INTERVAL=1
		;;
	-h | --help)
		echo "usage: tablet-dashboard [--once] [--interval N]  (read-only; Ctrl-C quits)"
		exit 0
		;;
	*) echo "usage: tablet-dashboard [--once] [--interval N]" >&2; exit 2 ;;
	esac
	shift
done

render() {
	echo "== iPad Air 2 tablet dashboard (read-only; Ctrl-C quits) =="
	date 2>/dev/null
	echo
	# shellcheck disable=SC2086
	$TABLET_STATUS 2>&1
	echo
	echo "== services =="
	if [ -r "$DROPBEAR_PID" ] && kill -0 "$(cat "$DROPBEAR_PID" 2>/dev/null)" 2>/dev/null; then
		echo "ssh (dropbear): running"
	else
		echo "ssh (dropbear): not running"
	fi
	if ps 2>/dev/null | grep -q '[t]elnetd'; then
		echo "telnet recovery: running"
	else
		echo "telnet recovery: not running"
	fi
	if ps 2>/dev/null | grep -q '[w]pa_supplicant'; then
		echo "wifi (wpa_supplicant): running"
	else
		echo "wifi (wpa_supplicant): not running"
	fi
	if ps 2>/dev/null | grep -q '[c]harging-policy'; then
		echo "charging policy: running"
	else
		echo "charging policy: not running"
	fi
	echo
	echo "== charging policy log (last 3) =="
	if [ -r "$POLICY_LOG" ]; then
		tail -n 3 "$POLICY_LOG"
	else
		echo "n/a"
	fi
}

if [ -n "$ONCE" ]; then
	render
	exit 0
fi

trap 'printf "\033[?25h\n"; exit 0' INT TERM
printf '\033[?25l'
while :; do
	frame=$(render)
	# Cursor home + clear, then the whole frame at once to limit flicker.
	printf '\033[H\033[2J%s\n' "$frame"
	sleep "$INTERVAL"
done
