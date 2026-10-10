#!/bin/sh
# Raises the USB input current limit at boot and backs off when hot or 80% full.
# Writes only the charger's input_current_limit sysfs property (patch 0017).
# Overridable for tests; ONCE=1 runs a single evaluation, MAX_ITER=N runs N.
# Policy: 2400 mA below 80% capacity and 42 C; 500 mA at or above either limit
# or if either reading is unavailable. BusyBox ash.
CHG=${CHG:-/sys/class/power_supply/j81-d2207-charger}
BAT=${BAT:-/sys/class/power_supply/bq27545-battery}
TARGET_UA=${TARGET_UA:-2400000}   # tier validated 2026-09-21 and 2026-10-04
SAFE_UA=${SAFE_UA:-500000}        # backoff tier
HOT_DECI=${HOT_DECI:-420}         # >= 42.0 C: back off
COOL_DECI=${COOL_DECI:-380}       # <= 38.0 C: resume
MAX_CAPACITY=${MAX_CAPACITY:-80}  # >= 80%: back off
INTERVAL=${INTERVAL:-30}
WAIT_SECS=${WAIT_SECS:-120}
# The battery gauge (HDQ over UART5) sometimes fails its one identification at boot (a marginal pulse: "matched 15/16 bytes"); the driver never
# retries, so no battery is registered and this policy would have nothing to read. While the gauge is missing, re-probe it every 5 s.
HDQ_DRV=${HDQ_DRV:-/sys/bus/serial/drivers/bq27xxx-hdq-uart}
HDQ_DEV=${HDQ_DEV:-serial0-0}
LIMIT=$CHG/input_current_limit

log() { echo "charging-policy: $*"; }

waited=0
while [ ! -w "$LIMIT" ] || [ ! -r "$BAT/uevent" ]; do
	if [ "$waited" -ge "$WAIT_SECS" ]; then
		log "sysfs not available after ${WAIT_SECS}s; leaving limit unchanged"
		exit 1
	fi
	if [ ! -r "$BAT/uevent" ] && [ -d "$HDQ_DRV" ] && [ $((waited % 5)) -eq 4 ]; then
		log "battery gauge not registered after ${waited}s; re-probing $HDQ_DEV"
		echo "$HDQ_DEV" > "$HDQ_DRV/unbind" 2>/dev/null
		echo "$HDQ_DEV" > "$HDQ_DRV/bind" 2>/dev/null
	fi
	sleep 1
	waited=$((waited + 1))
done

# Temperature in deci-degrees C, empty if unreadable.
temp() { sed -n 's/^POWER_SUPPLY_TEMP=//p' "$BAT/uevent" | head -n 1; }
capacity() { sed -n 's/^POWER_SUPPLY_CAPACITY=//p' "$BAT/uevent" | head -n 1; }

# Write $1 (uA) and verify by reading it back; $2 is the log reason.
set_limit() {
	echo "$1" > "$LIMIT" 2>/dev/null
	got=$(cat "$LIMIT" 2>/dev/null)
	if [ "$got" = "$1" ]; then
		log "limit $1 uA ($2)"
	else
		log "write of $1 uA failed (read back '$got')"
	fi
}

# Decide from the actual current value, so an external change is corrected.
want() {
	[ "$(cat "$LIMIT" 2>/dev/null)" = "$1" ] || set_limit "$1" "$2"
}

hot=0
iter=0
while :; do
	t=$(temp)
	c=$(capacity)

	# Temperature: a leading minus is valid (cold). Capacity: digits only.
	case $t in "" | - | *[!0-9-]*) temp_ok=0 ;; *) temp_ok=1 ;; esac
	case $c in "" | *[!0-9]*) cap_ok=0 ;; *) cap_ok=1 ;; esac

	if [ "$temp_ok" = 0 ]; then
		# Unknown temperature: latch the safe tier, never the high one.
		hot=1
	elif [ "$t" -ge "$HOT_DECI" ]; then
		hot=1
	elif [ "$t" -le "$COOL_DECI" ]; then
		hot=0
	fi

	# 2400 mA only while capacity is known and below the cap and not hot.
	if [ "$temp_ok" = 0 ]; then
		want "$SAFE_UA" "temperature unreadable"
	elif [ "$cap_ok" = 0 ]; then
		want "$SAFE_UA" "capacity unreadable"
	elif [ "$c" -ge "$MAX_CAPACITY" ]; then
		want "$SAFE_UA" "capacity ${c}%"
	elif [ "$hot" = 1 ]; then
		want "$SAFE_UA" "hot ${t} deciC"
	else
		want "$TARGET_UA" "temp ${t} deciC capacity ${c}%"
	fi

	iter=$((iter + 1))
	[ -n "$ONCE" ] && exit 0
	[ -n "$MAX_ITER" ] && [ "$iter" -ge "$MAX_ITER" ] && exit 0
	sleep "$INTERVAL"
done
