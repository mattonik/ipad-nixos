#!/bin/sh
# Bring the iPad's Wi-Fi up at boot (busybox sh, runs in the initramfs). Installed ONLY by the private payload assembler together with the
# static iw/wpa_supplicant and the private /etc/wpa_supplicant.conf; the public base payload just starts /usr/bin/wifi-up when it exists.
# Progress goes to the kernel log (/dev/kmsg, visible on the screen and in the stream) and to /var/log/wifi-up.log. No secrets are printed.
LOG=/var/log/wifi-up.log
WPA=/usr/bin/wpa_supplicant
CONF=/etc/wpa_supplicant.conf
UDHCPC_SCRIPT=/usr/share/wifi/udhcpc.script
IF=wlan0

log() {
	echo "wifi-up: $*" >/dev/kmsg 2>/dev/null
	echo "$(date +%T) $*" >>"$LOG"
}

mkdir -p /var/log /run /var/run/wpa_supplicant
[ -x "$WPA" ] && [ -s "$CONF" ] || { log "wpa_supplicant or its configuration is missing; Wi-Fi not started"; exit 1; }

# The driver registers the interface a few seconds after boot.
n=0
while [ ! -e /sys/class/net/$IF ] && [ $n -lt 120 ]; do
	sleep 1
	n=$((n + 1))
done
[ -e /sys/class/net/$IF ] || { log "$IF did not appear after ${n}s"; exit 1; }
log "$IF present after ${n}s"

ifconfig $IF up || { log "ifconfig $IF up failed"; exit 1; }

attempt=0
while [ $attempt -lt 5 ]; do
	attempt=$((attempt + 1))
	killall wpa_supplicant 2>/dev/null
	rm -f /var/run/wpa_supplicant/$IF
	"$WPA" -B -i $IF -D nl80211 -c "$CONF" -f /var/log/wpa.log -P /var/run/wpa_supplicant.pid
	i=0
	state=""
	while [ $i -lt 30 ]; do
		sleep 1
		i=$((i + 1))
		if grep -q "CTRL-EVENT-CONNECTED" /var/log/wpa.log 2>/dev/null; then
			state=ok
			break
		fi
	done
	if [ "$state" = ok ]; then
		log "associated (attempt $attempt, ${i}s)"
		break
	fi
	log "no association yet (attempt $attempt)"
done
[ "$state" = ok ] || { log "association failed after $attempt attempts"; exit 1; }

# DHCP, retried in the background by busybox udhcpc itself.
udhcpc -i $IF -b -t 10 -T 3 -A 5 -s "$UDHCPC_SCRIPT" -p /var/run/udhcpc-$IF.pid >>"$LOG" 2>&1
log "udhcpc started"
exit 0
