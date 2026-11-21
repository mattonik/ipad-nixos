# Framebuffer breadcrumbs: a log channel that survives a bus hang (prepared, not run)

Problem: a hanging MMIO access ends in a watchdog reset about 20 s later and everything in memory or behind an interrupt (dmesg, USB network, USB serial, netconsole) is lost.
Findings (observer kernel config `7.3.0-rc1`): `CONFIG_NETCONSOLE` is not set, USB gadget serial/ACM/NCM are built in but all interrupt-driven, `PSTORE_RAM`/`PSTORE_CONSOLE` are built in but need a
reserved-memory ramoops region and DRAM surviving a watchdog reset plus a DFU cycle (iBoot retrains DRAM; doubtful, untested). Boot args use `console=tty0` with simpledrm/fbcon, and the repo already used a framebuffer
mark for the entry probe (`boot/test_t7001_entry_marker.py`), so a plain framebuffer store is the channel: needs no interrupts, and the last frame stays on the panel until the reset.

Helper: `kernel/gpc-page5-kpoll-crumbs/fb_breadcrumb.h` (reusable; copy into a module dir). `fb_crumb_init()` at module load reads the DT `simple-framebuffer` node (reg, width, height, stride, format; nothing hardcoded) and
maps it with `ioremap_wc`; `fb_crumb_mark(n)` draws square n (1..8, 32x32 px, white) at the bottom-left. Best effort: if the node, format or mapping is unusable, crumbs are off and `core` reports `crumb=off`.
In the compressed batch the squares are: 1 before the bridge stores, 2 before the GPC request, 3 before the poll, 4 poll succeeded, 5 before the (optional) core read, 6 batch finished.

Variants (both built 2026-11-21 against the observer kernel):
- `kernel/gpc-page5-kpoll-crumbs` (core read disabled), module sha256 `1d0447c277fc1fff4d9eefe8b0488fc982ef64129506f05681c52908c782aeda`, bundle `j81-crumbs-bundle-20261121`,
  runner `j81-linux-crumbs-experiment`. Validation run, no hang expected: the batch returns and the screen should show SIX squares (look at the bottom-left of the panel while/after it runs).
- `kernel/gpc-page5-kpoll-crumbs-core` (core read enabled), sha256 `582b157efb3e1ed5a32fd6742d4bcc249def0ad9604082175e6a145f8a427f89`, bundle `j81-crumbs-core-bundle-20261121`, runner `j81-linux-crumbs-core-experiment`.
  Expected to hang on the core load: FIVE squares should be left on the panel until the reset (about 20 s), confirming the hang location with an independent channel.
Both runners keep the dry-run and clean-state gates; flow tests and `--verify-only` pass. Order: run the validation (crumbs) first.
Launch as before (fresh DFU, same two boot commands with the bundle's Pongo.bin/m1n1-linux.bin, preflight GO, go-ahead), then from the runner dir
`python3 j81_observer_paired_campaign.py <new logdir> --bundle ../../../j81-crumbs-bundle-20261121` (or the `-core` bundle).
Limits: needs a person (or photo) to read the panel before the reset; fbcon text can scroll over the squares if something prints; at most 8 squares; display scanout, not DRAM readback, is the evidence.
