#!/bin/sh
# Start touchdemo on the iPad's own screen at boot when the kernel command line asks for it (payload m1n1-orchard-touch-demo):
#   j81.touchdemo=1 (PAINT), j81.touchdemo=grid or j81.touchdemo=events.
# Started in the background by the boot hook after apple_z2.ko is loaded; touchdemo itself waits up to 60 s for the
# touchscreen to register (the firmware boot runs after insmod returns). Without the argument it does nothing, and
# touchdemo stays available over SSH: `touchdemo`, `touchdemo --mode grid`, `touchdemo --text --no-display`.
arg=$(tr ' ' '\n' </proc/cmdline 2>/dev/null | sed -n 's/^j81\.touchdemo=//p' | tail -n 1)
case "$arg" in
	1|paint) mode=paint ;;
	grid) mode=grid ;;
	events) mode=events ;;
	*) exit 0 ;;
esac
# Keep kernel messages off the screen; they stay in dmesg.
echo 0 >/sys/module/printk/parameters/ignore_loglevel 2>/dev/null
echo "1 1 1 1" >/proc/sys/kernel/printk 2>/dev/null
exec /usr/bin/touchdemo --mode "$mode" --wait 60 </dev/null
