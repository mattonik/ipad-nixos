#!/bin/sh
# Read-only tablet summary. Writes nothing. BusyBox ash compatible.
# SYSFS/PROCFS/NETDEV may be overridden to test against a fake tree.
SYSFS=${SYSFS:-/sys}
PROCFS=${PROCFS:-/proc}
NETDEV=${NETDEV:-usb0}
WIFIDEV=${WIFIDEV:-wlan0}
IW=${IW:-iw}
BAT=$SYSFS/class/power_supply/bq27545-battery
CHG=$SYSFS/class/power_supply/j81-d2207-charger

rd() { cat "$1" 2>/dev/null || echo "n/a"; }

# uevent KEY from the battery; empty when absent.
bat() {
	sed -n "s/^POWER_SUPPLY_$1=//p" "$BAT/uevent" 2>/dev/null | head -n 1
}

# Print "<label>: <value> <unit>" scaling a micro-unit integer to milli.
milli() {
	case $2 in ""|-|*[!0-9-]*) echo "$1: n/a"; return ;; esac
	v=$2
	sign=""
	case $v in -*) sign="-"; v=${v#-} ;; esac
	echo "$1: ${sign}$((v / 1000)) $3"
}

echo "== battery =="
cap=$(bat CAPACITY)
if [ -n "$cap" ]; then echo "capacity: $cap%"; else echo "capacity: n/a"; fi
echo "status: $(bat STATUS)"
milli "voltage" "$(bat VOLTAGE_NOW)" mV
milli "current" "$(bat CURRENT_NOW)" mA
t=$(bat TEMP)
case $t in ""|-|*[!0-9-]*) t="" ;; esac
if [ -n "$t" ]; then
	sign=""; a=$t
	case $a in -*) sign="-"; a=${a#-} ;; esac
	echo "temperature: ${sign}$((a / 10)).$((a % 10)) C"
else
	echo "temperature: n/a"
fi

echo "== charger =="
milli "input_current_limit" "$(rd "$CHG/input_current_limit")" mA
echo "online: $(rd "$CHG/online")"

echo "== usb network ($NETDEV) =="
echo "address: $(ip -4 addr show "$NETDEV" 2>/dev/null | sed -n 's/^ *inet \([^ ]*\).*/\1/p' | head -n 1)"
echo "carrier: $(rd "$SYSFS/class/net/$NETDEV/carrier")"

echo "== wifi ($WIFIDEV) =="
if [ -e "$SYSFS/class/net/$WIFIDEV" ]; then
	echo "state: $(rd "$SYSFS/class/net/$WIFIDEV/operstate")"
	link=$($IW dev "$WIFIDEV" link 2>/dev/null)
	case $link in
	*"Not connected"* | "") echo "ssid: not connected" ;;
	*)
		echo "ssid: $(echo "$link" | sed -n 's/^[[:space:]]*SSID: //p' | head -n 1)"
		echo "frequency: $(echo "$link" | sed -n 's/^[[:space:]]*freq: \([0-9.]*\).*/\1/p' | head -n 1) MHz"
		echo "signal: $(echo "$link" | sed -n 's/^[[:space:]]*signal: //p' | head -n 1)"
		echo "rx bitrate: $(echo "$link" | sed -n 's/^[[:space:]]*rx bitrate: //p' | head -n 1)"
		echo "tx bitrate: $(echo "$link" | sed -n 's/^[[:space:]]*tx bitrate: //p' | head -n 1)"
		;;
	esac
	echo "address: $(ip -4 addr show "$WIFIDEV" 2>/dev/null | sed -n 's/^ *inet \([^ ]*\).*/\1/p' | head -n 1)"
else
	echo "state: no $WIFIDEV"
fi

echo "== system =="
echo "uptime: $(cut -d' ' -f1 "$PROCFS/uptime" 2>/dev/null || echo n/a) s"
echo "== last kernel messages =="
dmesg 2>/dev/null | tail -n 8
