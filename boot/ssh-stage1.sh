#!/bin/sh
# Stage 1 SSH hook: replaces the debug-shell hook, keeps telnet as recovery.
# Placeholder @DROPBEAR@ is substituted at build time with the Dropbear store
# path, whose full runtime closure is shipped at the same paths.
# Never returns to /init: that would continue into root-partition probing.
# shellcheck disable=SC1091
. /etc/deviceinfo
. /init_functions.sh
TELNET_PORT=23
SSH_PORT=22
DB=@DROPBEAR@

setup_usb_network
start_udhcpd

{
	echo "#!/bin/sh"
	echo "sh"
} >/telnet_connect.sh
chmod +x /telnet_connect.sh
telnetd -b "${IP}:${TELNET_PORT}" -l /telnet_connect.sh

mkdir -p /var/log /var/empty /etc/dropbear
chmod 755 /var/empty
# Volatile root: host key is regenerated every boot; check the fingerprint
# over telnet (/var/log/dropbear.log) before trusting it.
"$DB/bin/dropbearkey" -t ed25519 -f /etc/dropbear/dropbear_ed25519_host_key \
	>/var/log/dropbear-keygen.log 2>&1
chmod 600 /etc/dropbear/dropbear_ed25519_host_key
# -s key-only, -j/-k no forwarding, bound to the USB address only.
"$DB/bin/dropbear" -s -j -k -E -p "${IP}:${SSH_PORT}" \
	-r /etc/dropbear/dropbear_ed25519_host_key \
	-P /var/run/dropbear.pid >/var/log/dropbear.log 2>&1
sleep 1
if [ -f /var/run/dropbear.pid ] && kill -0 "$(cat /var/run/dropbear.pid)" 2>/dev/null; then
	echo "SSH: dropbear running on ${IP}:${SSH_PORT}"
else
	echo "SSH: dropbear FAILED to start; telnet recovery on ${IP}:${TELNET_PORT}"
fi

echo "WARNING: telnet recovery shell is active on ${IP}:${TELNET_PORT} (stage 1)."
loop_forever
