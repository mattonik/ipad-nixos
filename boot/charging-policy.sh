#!/bin/sh
# Raises the USB input current limit at boot and backs off when hot.
# Writes only the charger's input_current_limit sysfs property (patch 0017).
# Overridable for tests; ONCE=1 runs a single evaluation. BusyBox ash.
CHG=${CHG:-/sys/class/power_supply/j81-d2207-charger}
BAT=${BAT:-/sys/class/power_supply/bq27545-battery}
TARGET_UA=${TARGET_UA:-2400000}   # tier validated 2026-09-21 and 2026-10-04
SAFE_UA=${SAFE_UA:-500000}        # backoff tier
HOT_DECI=${HOT_DECI:-420}         # >= 42.0 C: back off
COOL_DECI=${COOL_DECI:-380}       # <= 38.0 C: resume
INTERVAL=${INTERVAL:-30}
WAIT_SECS=${WAIT_SECS:-60}
LIMIT=$CHG/input_current_limit

log() { echo "charging-policy: $*"; }

waited=0
while [ ! -w "$LIMIT" ] || [ ! -r "$BAT/uevent" ]; do
	if [ "$waited" -ge "$WAIT_SECS" ]; then
		log "sysfs not available after ${WAIT_SECS}s; leaving limit unchanged"
		exit 1
	fi
	sleep 1
	waited=$((waited + 1))
done

# Temperature in deci-degrees C, empty if unreadable.
temp() { sed -n 's/^POWER_SUPPLY_TEMP=//p' "$BAT/uevent" | head -n 1; }

set_limit() {
	echo "$1" > "$LIMIT" 2>/dev/null
	got=$(cat "$LIMIT" 2>/dev/null)
	if [ "$got" = "$1" ]; then
		log "limit $1 uA ($2)"
		state=$3
	else
		log "write of $1 uA failed (read back '$got')"
	fi
}

state=unset
while :; do
	t=$(temp)
	case $t in
	"" | -  | *[!0-9-]*)
		# Unknown temperature: stay on the safe tier, never the high one.
		[ "$state" = safe ] || set_limit "$SAFE_UA" "temperature unreadable" safe
		;;
	*)
		if [ "$t" -ge "$HOT_DECI" ]; then
			[ "$state" = safe ] || set_limit "$SAFE_UA" "hot ${t} deciC" safe
		elif [ "$t" -le "$COOL_DECI" ] || [ "$state" = unset ]; then
			[ "$state" = target ] || set_limit "$TARGET_UA" "temp ${t} deciC" target
		fi
		;;
	esac
	[ -n "$ONCE" ] && exit 0
	sleep "$INTERVAL"
done
