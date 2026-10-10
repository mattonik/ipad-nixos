#!/bin/sh
# Start the tablet dashboard on the iPad's own screen (the framebuffer console, tty0). Started in the background by the boot hook of the
# production base payload. `j81.dashboard=0` on the kernel command line turns it off (for debugging with the kernel log on screen).
# Kernel messages would overwrite the dashboard, so the console log level is lowered first; they stay in dmesg and the telnet/SSH shells.
grep -q 'j81.dashboard=0' /proc/cmdline 2>/dev/null && exit 0
echo 0 >/sys/module/printk/parameters/ignore_loglevel 2>/dev/null
echo "1 1 1 1" >/proc/sys/kernel/printk 2>/dev/null
# 1536x2048 screen at the 16x32 font (fbcon=font:TER16x32) is 96 columns by 64 rows; cut to 95 so no line wraps.
DASH_COLS=${DASH_COLS:-95} exec tablet-dashboard --interval 5 </dev/null >/dev/tty0 2>/dev/null
