#!/bin/sh
# power-diag: READ-ONLY power diagnostic for the iPad (BusyBox ash). Prints one snapshot or logs CSV rows for controlled A/B tests.
#
#   power-diag [--vbus]             one human-readable snapshot
#   power-diag log [--vbus] [-i SEC] [-n COUNT] [-l LABEL] [-o FILE]
#                                   CSV rows every SEC seconds (default 5), COUNT rows (default: until interrupted), LABEL tags every row (change it between
#                                   test phases, e.g. wifi-off / wifi-on), appended to FILE (default: stdout)
#   power-diag --help
#
# Sources, all read-only: the battery gauge and charger in sysfs, and plain PMIC register READS through a forced i2c read transaction
# (the same read the earlier charger observer made): 0x04c0 input current limit, 0x04c6 programmed charge current (50 mA/count), 0x04c7[5:0] hardware charge-current
# cap (50 mA/count), 0x04cf[5:0] configured charge-current ceiling (50 mA/count), 0x0010 (bit 2 = USB input suspend),
# the status block 0x0060..0x006c (0x0062 bit 5 = USB power limited).
#
# VBUS current and voltage (D2207 ADC channels 9 and 19) are shown ONLY with --vbus (or VBUS=1) and only if the kernel exposes the charger's current_now / voltage_now
# (patch 0099). Each such sysfs read makes the kernel run one ADC conversion, which writes the PMIC ADC control register 0x0500 and the event mask 0x007b and restores
# both, so --vbus is NOT read-only: without it the VBUS columns read "n/a" and nothing is written. With VBUS data the script also prints input power (VBUS mV x mA)
# and an estimate of system power (input power minus battery power; sign convention: gauge current positive = charging).
#
# Overridable for tests: CHG, BAT, I2CTRANSFER, BACKLIGHT, WLAN, POLICY_LOG, UPTIME_FILE, LOADAVG_FILE.
CHG=${CHG:-/sys/class/power_supply/j81-d2207-charger}
BAT=${BAT:-/sys/class/power_supply/bq27545-battery}
BACKLIGHT=${BACKLIGHT:-/sys/class/backlight}
WLAN=${WLAN:-/sys/class/net/wlan0}
POLICY_LOG=${POLICY_LOG:-/var/log/charging-policy.log}
UPTIME_FILE=${UPTIME_FILE:-/proc/uptime}
LOADAVG_FILE=${LOADAVG_FILE:-/proc/loadavg}
PMU_BUS=${PMU_BUS:-0}
PMU_ADDR=${PMU_ADDR:-0x3c}
# Same numbers as charging-policy.sh, used only to report what the policy would choose.
VBUS=${VBUS:-0}
# Patch 0099 now converts like Apple's code (16.16 fixed point: 88/65536 V and 52.8/65536 A per count), so VBUS_DIV is 1. Kernels built before that fix (T4, T6) report values
# 65.536 times too large: run with VBUS_DIV=65 there for an approximation (about 1.0% off) or 65536/1000 exactly is not possible in integer shell arithmetic.
VBUS_DIV=${VBUS_DIV:-1}
TARGET_UA=${TARGET_UA:-2400000}
SAFE_UA=${SAFE_UA:-500000}
HOT_DECI=${HOT_DECI:-420}
MAX_CAPACITY=${MAX_CAPACITY:-80}

if [ -z "$I2CTRANSFER" ]; then
	for c in /usr/bin/i2ctransfer /tmp/bt/i2ctransfer /tmp/power/i2ctransfer; do
		[ -x "$c" ] && I2CTRANSFER=$c && break
	done
fi

num() { case "$1" in ''|*[!0-9-]*) echo "";; *) echo "$1";; esac; }
rd() { cat "$1" 2>/dev/null; }
batprop() { sed -n "s/^POWER_SUPPLY_$1=//p" "$BAT/uevent" 2>/dev/null | head -n 1; }
chgprop() { rd "$CHG/$1"; }

# PMIC register read: $1 = high byte, $2 = low byte, $3 = byte count (default 1). Prints the hex bytes on one line, empty if unavailable.
pmic() {
	[ -n "$I2CTRANSFER" ] || return 0
	"$I2CTRANSFER" -f -y "$PMU_BUS" "w2@$PMU_ADDR" "$1" "$2" "r${3:-1}@$PMU_ADDR" 2>/dev/null | tail -n 1
}

hex2dec() { [ -n "$1" ] && echo $(($1)); }

# What charging-policy.sh would ask for from the present capacity and temperature (it adds hysteresis on the way back from hot, so this is the
# stateless view; the log line shows what it actually did).
policy_view() {
	cap=$(num "$(batprop CAPACITY)")
	tmp=$(num "$(batprop TEMP)")
	if [ -z "$cap" ] || [ -z "$tmp" ]; then
		echo "backoff ($((SAFE_UA / 1000)) mA: gauge reading unavailable)"
	elif [ "$cap" -ge "$MAX_CAPACITY" ]; then
		echo "backoff ($((SAFE_UA / 1000)) mA: capacity $cap% >= $MAX_CAPACITY%)"
	elif [ "$tmp" -ge "$HOT_DECI" ]; then
		echo "backoff ($((SAFE_UA / 1000)) mA: temperature $((tmp / 10)).$((tmp % 10)) C >= $((HOT_DECI / 10)) C)"
	else
		echo "target ($((TARGET_UA / 1000)) mA)"
	fi
}

policy_last() { [ -r "$POLICY_LOG" ] && tail -n 1 "$POLICY_LOG" || echo "(no log)"; }

# Collect everything once into shell variables.
collect() {
	up=$(cut -d' ' -f1 "$UPTIME_FILE" 2>/dev/null)
	status=$(batprop STATUS)
	cap=$(batprop CAPACITY)
	vbat_uv=$(num "$(batprop VOLTAGE_NOW)")
	ibat_ua=$(num "$(batprop CURRENT_NOW)")
	tmp=$(batprop TEMP)
	pavg_uw=$(num "$(batprop POWER_AVG)")
	ilim_ua=$(num "$(chgprop input_current_limit)")
	imax_ua=$(num "$(chgprop constant_charge_current_max)")
	vbat_mv=""; ibat_ma=""; pbat_mw=""; ilim_ma=""; imax_ma=""
	[ -n "$vbat_uv" ] && vbat_mv=$((vbat_uv / 1000))
	[ -n "$ibat_ua" ] && ibat_ma=$((ibat_ua / 1000))
	[ -n "$vbat_uv" ] && [ -n "$ibat_ua" ] && pbat_mw=$((vbat_uv / 1000 * ibat_ua / 1000000))
	[ -n "$ilim_ua" ] && ilim_ma=$((ilim_ua / 1000))
	[ -n "$imax_ua" ] && imax_ma=$((imax_ua / 1000))
	r04c0=$(pmic 0x04 0xc0); r04cf=$(pmic 0x04 0xcf); r0010=$(pmic 0x00 0x10); r04c6=$(pmic 0x04 0xc6); r04c7=$(pmic 0x04 0xc7)
	prog_ma=""; cap_ma=""; ceil_ma=""
	[ -n "$r04c6" ] && prog_ma=$(( $(hex2dec "$r04c6") * 50 ))
	[ -n "$r04c7" ] && cap_ma=$(( ($(hex2dec "$r04c7") & 63) * 50 ))
	[ -n "$r04cf" ] && ceil_ma=$(( ($(hex2dec "$r04cf") & 63) * 50 ))
	blk=$(pmic 0x00 0x60 13)
	r0062=$(echo "$blk" | cut -d' ' -f3)
	suspend=""; plimit=""
	[ -n "$r0010" ] && suspend=$(( ($(hex2dec "$r0010") >> 2) & 1 ))
	[ -n "$r0062" ] && plimit=$(( ($(hex2dec "$r0062") >> 5) & 1 ))
	vbus_ma=n/a; vbus_mv=n/a; vbus_mw=n/a; sys_mw=n/a
	if [ "$VBUS" = 1 ] && [ -r "$CHG/current_now" ] && [ -r "$CHG/voltage_now" ]; then
		vi=$(num "$(chgprop current_now)"); vv=$(num "$(chgprop voltage_now)")
		if [ -n "$vi" ] && [ -n "$vv" ]; then
			vbus_ma=$((vi / 1000 / VBUS_DIV)); vbus_mv=$((vv / 1000 / VBUS_DIV)); vbus_mw=$((vbus_mv * vbus_ma / 1000))
			[ -n "$pbat_mw" ] && sys_mw=$((vbus_mw - pbat_mw))
		fi
	fi
	load1=$(cut -d' ' -f1 "$LOADAVG_FILE" 2>/dev/null)
	bl=""
	for b in "$BACKLIGHT"/*/brightness; do [ -r "$b" ] && bl=$(cat "$b") && break; done
	wlan=down
	[ -r "$WLAN/operstate" ] && [ "$(cat "$WLAN/operstate")" = up ] && wlan=up
}

snapshot() {
	collect
	echo "uptime            ${up:-?} s"
	echo "battery           ${status:-?}, ${cap:-?} %, ${vbat_mv:-?} mV, ${ibat_ma:-?} mA (gauge sign: + charging), temp ${tmp:-?} (0.1 C), average power ${pavg_uw:-?} uW"
	echo "battery power     ${pbat_mw:-?} mW (voltage x current)"
	echo "input limit       ${ilim_ma:-?} mA (PMIC 0x04c0 = ${r04c0:-?}; USB input suspend bit ${suspend:-?})"
	echo "max charge curr   ${imax_ma:-?} mA (sysfs; PMIC 0x04cf = ${r04cf:-?}, ceiling ${ceil_ma:-?} mA)"
	echo "charge programmed ${prog_ma:-?} mA (PMIC 0x04c6 = ${r04c6:-?}, 50 mA/count); hardware cap ${cap_ma:-?} mA (0x04c7 = ${r04c7:-?})"
	echo "PMIC status       0x0060.. ${blk:-n/a}; USB power limited bit ${plimit:-?}"
	if [ "$vbus_ma" = n/a ]; then
		echo "VBUS              n/a (run with --vbus on a kernel with patch 0099; that performs ADC conversions, i.e. PMIC writes that are restored)"
	else
		echo "VBUS              ${vbus_mv} mV, ${vbus_ma} mA = ${vbus_mw} mW input power; system power estimate ${sys_mw} mW (input minus battery); kernel values divided by VBUS_DIV=${VBUS_DIV} (unconfirmed scale)"
	fi
	echo "charging policy   would choose $(policy_view); last log: $(policy_last)"
	echo "context           load ${load1:-?}, backlight ${bl:-?}, wlan0 ${wlan}"
	[ -n "$I2CTRANSFER" ] || echo "note              no i2ctransfer found: PMIC register values are unavailable (set I2CTRANSFER or push it to /tmp/power/)"
}

csv_header() {
	echo "uptime_s,label,status,capacity_pct,vbat_mv,ibat_ma,pbat_mw,temp_deci_c,input_limit_ma,max_charge_ma,pmic_04c0,pmic_04c6,pmic_04c7,pmic_04cf,pmic_0010,charge_programmed_ma,charge_cap_ma,usb_suspend,usb_power_limited,vbus_ma,vbus_mv,vbus_mw,sys_power_est_mw,load1,backlight,wlan,policy_view,policy_last"
}

csv_row() {
	collect
	pv=$(policy_view | tr ',' ';'); pl=$(policy_last | tr ',' ';')
	echo "${up},${label},${status},${cap},${vbat_mv},${ibat_ma},${pbat_mw},${tmp},${ilim_ma},${imax_ma},${r04c0},${r04c6},${r04c7},${r04cf},${r0010},${prog_ma},${cap_ma},${suspend},${plimit},${vbus_ma},${vbus_mv},${vbus_mw},${sys_mw},${load1},${bl},${wlan},${pv},${pl}"
}

usage() { sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; }

[ "$1" = "--vbus" ] && { VBUS=1; shift; }
case "$1" in
	--help|-h) usage; exit 0 ;;
	log)
		shift
		interval=5; count=0; label=""; out=""
		while [ $# -gt 0 ]; do
			case "$1" in
				--vbus) VBUS=1; shift ;;
				-i) interval=$2; shift 2 ;;
				-n) count=$2; shift 2 ;;
				-l) label=$2; shift 2 ;;
				-o) out=$2; shift 2 ;;
				*) echo "power-diag: unknown option $1" >&2; exit 2 ;;
			esac
		done
		case "$interval$count" in *[!0-9]*) echo "power-diag: -i and -n take whole numbers" >&2; exit 2 ;; esac
		label=$(echo "$label" | tr ',' '_')
		emit() { if [ -n "$out" ]; then "$@" >> "$out"; else "$@"; fi; }
		if [ -z "$out" ] || [ ! -s "$out" ]; then emit csv_header; fi
		n=0
		while :; do
			emit csv_row
			n=$((n + 1))
			[ "$count" -gt 0 ] && [ "$n" -ge "$count" ] && break
			sleep "$interval"
		done
		;;
	"") snapshot ;;
	*) echo "power-diag: unknown argument $1 (try --help)" >&2; exit 2 ;;
esac
