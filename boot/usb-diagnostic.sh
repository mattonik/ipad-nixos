#!/bin/sh
# Replaces the legacy debug-shell hook; /init has already mounted proc/sys/dev.
# Keep its network setup and built-in g_ether; never touch internal storage.
# shellcheck disable=SC1091
. /etc/deviceinfo
# shellcheck disable=SC1091
. /init_functions.sh
setup_usb_network
start_udhcpd

mkdir -p /sys/kernel/debug /tmp/usb-diagnostic
mount -t debugfs debugfs /sys/kernel/debug 2>/dev/null || true
telnetd -b "$IP:23" -l /bin/sh
# Errors stay visible in the rotating log page, without asynchronous scrolling.
dmesg -n 1

# Use the framebuffer explicitly even if the hook inherited redirected output.
exec >/dev/tty0 2>&1
echo 'USB DIAGNOSTIC: starting (RAM only)'
echo 'Telnet debug shell: 172.16.42.1:23; host: 172.16.42.2/24'
sleep 3

while :; do
    # One bounded probe each cycle, so TX is tested even if the Mac sends nothing.
    ping -c 1 -W 1 172.16.42.2 > /tmp/usb-diagnostic/ping 2>&1
    {
        echo 'PAGE 1/3: LINK AND PACKET COUNTERS'
        uptime
        ip addr show usb0
        for udc in /sys/class/udc/*; do
            [ -d "$udc" ] || continue
            echo "UDC: ${udc##*/}"
            for field in state current_speed function; do
                printf '%s: ' "$field"
                cat "$udc/$field" 2>/dev/null || echo unavailable
            done
        done
        printf 'carrier: '
        cat /sys/class/net/usb0/carrier 2>/dev/null || echo unavailable
        for field in rx_packets tx_packets rx_errors tx_errors rx_dropped tx_dropped; do
            printf '%s: ' "$field"
            cat "/sys/class/net/usb0/statistics/$field" 2>/dev/null || echo unavailable
        done
        cat /proc/net/arp
        grep -i 'usb\|dwc2' /proc/interrupts
        tail -n 3 /tmp/usb-diagnostic/ping
    } > /tmp/usb-diagnostic/link 2>&1
    {
        echo 'PAGE 2/3: USB CONTROLLER / ENDPOINTS'
        for controller in /sys/kernel/debug/usb/*; do
            [ -f "$controller/state" ] || continue
            echo "$controller"
            cat "$controller/state"
            grep -E 'g_dma|g_rx_fifo|g_np_tx_fifo|g_tx_fifo' "$controller/params"
        done
    } > /tmp/usb-diagnostic/controller 2>&1
    {
        echo 'PAGE 3/3: LATEST USB KERNEL MESSAGES'
        dmesg | grep -iE 'dwc2|g_ether|gadget|ecm|usb0|packet filter' | tail -n 24
    } > /tmp/usb-diagnostic/kernel 2>&1
    # These three files are overwritten, not appended: bounded RAM usage.
    for page in link controller kernel; do
        printf '\033[2J\033[H'
        cat "/tmp/usb-diagnostic/$page"
        echo 'Photo this page; next page in 12 seconds. Logs: /tmp/usb-diagnostic'
        sleep 12
    done
done
