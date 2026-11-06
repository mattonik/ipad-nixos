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

**First boot, 2026-11-04: works.** Payload `m1n1-orchard-touch-demo` (private
`j81-orchard-touch-demo-20261104T082414Z`, run id `c1ad1c07…`, touch firmware 15.8.8) booted straight into PAINT;
Martin drew with several fingers ("works like a charm", video `IMG_4699.MOV` in the project library). From the
device:

- display backend `drm` (simpledrm 1.0.0 on `87d0de000.framebuffer`): `SETCRTC` and `DIRTYFB` work, no fbdev fallback;
- `iPad5,3 Touchscreen` on `/dev/input/event1`, axes X `0..1535` and Y `0..2047` (no zero range), 32 slots;
- after 567 s: 2,462 reports, 27,736 events, 73 contacts, **5 fingers at once**, kernel-to-app latency 0.15 ms
  average, raw range seen x `0..1520` y `17..2030`, `TOUCH_MAJOR` up to 3216, 1,509 touch interrupts;
- `dmesg`: 2 `touch frame error` (-74/-75) with one failed resynchronisation, both recovered on their own.

Two fixes from that run (same day): the Orchard defconfig has only the 8x16 console font, so
`fbcon=font:TER16x32` falls back and the panel text was tiny (text is now drawn 2x under 24 px); and `EVIOCGABS`
answers for every axis code, so the panel claimed a pressure axis (axes now come from `EVIOCGBIT`).

**Orchard main, 2026-11-04: works, 0 frame errors.** Payload `m1n1-orchard-main-touch-demo`: Orchard `d214e53`'s
own apple-4k kernel (`kernel/orchard-main.nix`: torvalds `cee9395` + all 417 patches of `kernel/series/apple-4k` +
`kernel/configs/apple-4k/config`, no local patches; GCC instead of Orchard's clang-19), private
`j81-orchard-main-touch-demo-20261104T095348Z`, run id `27e37011…`, touch firmware 15.8.8
(`b9b4a072…`). In 161.5 s: 6,843 reports, 99,850 events, 149 contacts, 5 fingers at once, latency 0.03 ms,
6,959 touch interrupts, **no `touch frame error` and no failed resynchronisation**. Raw range seen x `13..1535`
y `0..2018`. GRID targets (Martin: the dots landed "in the middle of the circle almost"):

| Target | Offset of the mean reported position |
|---|---|
| top-left (96, 96) | dx -0.3, dy -7.5 px (15 samples) |
| bottom-right (1440, 1952) | dx -10.4, dy +8.9 px (10 samples) |

At about 10 px/mm that is under 1.4 mm, so the DT's `touchscreen-inverted-y` (from the iPad 5) is right for the
Air 2 and no axis swap or flip is needed. Reported upstream as the evidence for J81 `touch = "working"` in Orchard.

Still open: whether `TOUCH_MAJOR` is really in 0.01 mm; J82; suspend/resume.
