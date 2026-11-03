# touchdemo: seeing touches on the iPad's screen

`touchdemo` (`boot/touchdemo.c`) is a small static program that shows what the J81 touchscreen reports, on the
iPad's own display. No GPU, Mesa or Wayland is needed: it draws into a DRM dumb buffer on `simpledrm`
(`/dev/dri/card0`, flushed per changed rectangle with `DIRTYFB`) and falls back to `/dev/fb0`. It reads the
multi-touch evdev node (`apple_z2`, protocol B) and the `gpio-keys` Home button, and puts the console in
`KD_GRAPHICS` while it runs so neither fbcon nor the text dashboard draws over it. It writes no hardware register.

## Screens

Switch with the buttons at the bottom (in GRID the buttons sit in the middle panel) or the Home button.

| Screen | What it shows |
|---|---|
| PAINT | A persistent trail per contact, coloured by tracking ID, a marker sized from `ABS_MT_TOUCH_MAJOR`/`MINOR` (an ellipse when both are reported) and the ID label. CLEAR wipes the trails; HUD hides the top panel. |
| GRID | Calibration and edge coverage. 128 px cells light up with dwell (heat), the outer ring stays outlined in orange until each edge cell has been touched, and eight targets (corners and edge midpoints, 96 px in) record the mean reported offset of a touch started on them. The panel shows `cells a/b edge c/52 targets d/8`. |
| EVENTS | An evtest-style readout: every MT axis with min/max/resolution/fuzz (zero ranges in orange), the live slots with raw and screen coordinates, and the latest raw events. |

The top panel in every screen shows the display backend, device name, reports per second, mean kernel-to-app
latency (`EVIOCSCLOCKID` to `CLOCK_MONOTONIC`), the axis ranges, the raw range seen so far and the live contacts.

`apple_z2` reports no pressure axis: size is `TOUCH_MAJOR`/`MINOR` (shown raw), and the marker diameter is
`major * x_resolution / 100` px, because the driver derives the resolution in px/mm from a surface in 0.01 mm.
That unit is an assumption; `--size-scale F` overrides it (diameter = `major * F` px).

### Zero axis ranges

If the driver reports `0..0` for X or Y (the geometry-at-discovery case), the panel says `ZERO RANGE (using seen
range)` and the mapping uses the raw range seen so far. Touch two opposite corners first. Until the seen range
spans 256 units on both axes, no touch presses a button (the first one always maps to mid-screen).

### Orientation check

The DT says `touchscreen-inverted-y` "as the iPad 5, unconfirmed on the Air 2". In GRID, touch the top-left
target: the orange dot marks where the touch was reported. If it lands at the opposite corner or edge, rerun with
`--flip-x`, `--flip-y` or `--swap-xy` to find the right combination, and record it before changing the DT.

## Running it

It is in every `touchModule` payload (`m1n1-orchard-touch`) at `/usr/bin/touchdemo`. Over SSH:

```sh
touchdemo                      # PAINT on the screen; Ctrl-C restores the console and prints a summary
touchdemo --mode grid
touchdemo --mode events
touchdemo --text --no-display  # contact lines on stdout only, nothing drawn
kill -USR1 $(pidof touchdemo)  # screenshot to /tmp/touchdemo-N.ppm (--shot-dir to change)
touchdemo --duration 60        # stop after 60 s
```

`m1n1-orchard-touch-demo` is the same kernel and initramfs with `j81.touchdemo=1 j81.dashboard=0` on the command
line: the boot hook starts `/usr/bin/touchdemo-screen`, which runs PAINT as soon as the touchscreen registers
(it waits up to 60 s). `j81.touchdemo=grid` or `=events` starts another screen. Its log is
`/var/log/touchdemo.log`; the summary lands there when it is killed. The assembler keeps the public bootargs,
so the plain image autostarts too with `--extra-bootarg j81.touchdemo=grid` (and `--extra-bootarg j81.dashboard=0`).

Build and assemble exactly like `docs/orchard-j81-touch.md`, with the `-demo` attribute:

```sh
BUILDER_DIR=/path/to/ipad-nixos tools/builder.sh build --wait --who <thread> \
  .#packages.x86_64-linux.m1n1-orchard-touch-demo -o artifacts/live/gcroot-orchard-touch-demo
python3 boot/assemble_private_wifi_payload.py --public artifacts/live/gcroot-orchard-touch-demo \
  --assets /path/to/private/wifi-assets --production \
  --touch-firmware /path/to/private/j81-fwstart.z2fw --out artifacts/live/private/j81-orchard-touch-demo
```

## Off-hardware check

`nix build .#packages.x86_64-linux.touchdemo-check` compiles touchdemo natively and runs
`boot/touchdemo-test.replay` and `boot/touchdemo-zero.replay` on a headless 1536x2048 screen. The replays feed
real `struct input_event` records into the same parser, so the check covers protocol-B slot handling, the axis
mapping, the compositor, GRID coverage and target offsets, and the zero-range fallback. `boot/touchdemo-check.py`
asserts the summary and screenshot pixels; the screenshots stay in the output. It cannot test the DRM/fbdev
backends, the console switch or the real touchscreen. Those need the iPad.

Screens from that check (half size): [PAINT](touchdemo/paint.png), [GRID](touchdemo/grid.png),
[EVENTS](touchdemo/events.png), [GRID with zero axes](touchdemo/zero-grid.png).

The check found two bugs before any hardware run: GRID coverage was counted against the current screen's panel,
so leaving GRID reset the counts to 0/0; and with zero axis ranges the first touch mapped to mid-screen and
pressed a button.

## Hardware status

Not yet run on the iPad (2026-11-03). Things to confirm on the first boot: that `simpledrm` accepts `SETCRTC`
and `DIRTYFB` (otherwise it falls back to fbdev, shown as `fbdev` in the panel), the report rate (the live module
test measured about 97/s), the latency, the X/Y orientation in GRID, and what `TOUCH_MAJOR` units look like.
