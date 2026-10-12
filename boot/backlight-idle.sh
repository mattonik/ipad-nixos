#!/bin/sh
# Dim the iPad's backlight after a period without button presses, restore it on a press (BusyBox ash). The only input device is the gpio-keys one (Home, Power, Volume), so
# "activity" means a key event. Writes only the backlight brightness (restored to the starting value on exit).
# Overridable for tests: BL (brightness file), EVENT (input device), IDLE_SECS, DIM, MAX_LOOPS.
BL=${BL:-$(ls /sys/class/backlight/*/brightness 2>/dev/null | head -n 1)}
EVENT=${EVENT:-/dev/input/event0}
IDLE_SECS=${IDLE_SECS:-120}
DIM=${DIM:-100}
MAX_LOOPS=${MAX_LOOPS:-0}	# 0 = forever

[ -w "$BL" ] || { echo "backlight-idle: no writable backlight ($BL)" >&2; exit 1; }
[ -r "$EVENT" ] || { echo "backlight-idle: no input device $EVENT" >&2; exit 1; }
BRIGHT=$(cat "$BL")
trap 'echo "$BRIGHT" > "$BL"' EXIT INT TERM

loops=0
while :; do
	echo "$BRIGHT" > "$BL"
	# one input event (24 bytes) within IDLE_SECS keeps the screen bright
	if timeout "$IDLE_SECS" dd if="$EVENT" bs=24 count=1 of=/dev/null 2>/dev/null; then
		:
	else
		echo "$DIM" > "$BL"
		# dimmed: the next key press brings the brightness back
		dd if="$EVENT" bs=24 count=1 of=/dev/null 2>/dev/null
	fi
	loops=$((loops + 1))
	[ "$MAX_LOOPS" -gt 0 ] && [ "$loops" -ge "$MAX_LOOPS" ] && break
done
