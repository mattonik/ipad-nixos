#!/bin/sh
# Continuous power log for the NixOS-in-RAM system (BusyBox ash): runs `power-diag log` forever, one CSV row every INTERVAL seconds, and keeps the file small enough for a RAM root
# by rotating it (FILE -> FILE.old) when it grows past MAX_BYTES. READ-ONLY: VBUS reads are OFF (VBUS=0) because each VBUS sample is a PMIC ADC conversion that writes the ADC control
# registers (restored); turn them on only deliberately (VBUS=1 in the environment of the unit).
# Overridable for tests: POWER_DIAG, FILE, INTERVAL, MAX_BYTES, LABEL, ROWS_PER_ROUND, MAX_ROUNDS.
POWER_DIAG=${POWER_DIAG:-power-diag}
FILE=${FILE:-/var/log/power.csv}
INTERVAL=${INTERVAL:-10}
MAX_BYTES=${MAX_BYTES:-2000000}
LABEL=${LABEL:-nixos}
ROWS_PER_ROUND=${ROWS_PER_ROUND:-60}
MAX_ROUNDS=${MAX_ROUNDS:-0}	# 0 = forever
VBUS=${VBUS:-0}
export VBUS

mkdir -p "$(dirname "$FILE")"
vbus_flag=""
[ "$VBUS" = 1 ] && vbus_flag="--vbus"
round=0
while :; do
	# shellcheck disable=SC2086
	"$POWER_DIAG" log $vbus_flag -i "$INTERVAL" -n "$ROWS_PER_ROUND" -l "$LABEL" -o "$FILE" || sleep "$INTERVAL"
	size=$(wc -c < "$FILE" 2>/dev/null || echo 0)
	[ "$size" -gt "$MAX_BYTES" ] && mv -f "$FILE" "$FILE.old"
	round=$((round + 1))
	[ "$MAX_ROUNDS" -gt 0 ] && [ "$round" -ge "$MAX_ROUNDS" ] && break
done
