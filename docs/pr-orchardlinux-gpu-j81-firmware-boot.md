# Draft: PR to OrchardLinux/gpu (not opened)

Branch: `j81-firmware-boot-20261126` in the local clone `~/Work/Sandbox/orchardlinux/gpu` (commit `0b9261b`, one commit on top of `origin/main` `e425018`). Push target: `mattonik/gpu` (remote `fork`), PR into `OrchardLinux/gpu` `main`. **Nothing has been pushed or opened.**

Before opening: (1) push `mattonik/ipad-nixos` (the notes link to `docs/j81-gpu-firmware-boot.md`, `docs/j81-f3a-runbook.md` and the run log there; the firmware words have been redacted from the log, but review `research/` once more for anything Apple's before pushing 90+ unpushed commits); (2) check the links in `a8x/FIRMWARE-BOOT.md` resolve; (3) decide whether to attach the forum message.

## Title

a8x: J81 firmware boot report, the offline layout and blob tools

## Body

Follow-up to #8 (identity words, `dwi` always-on, META core reads). On the iPad Air 2 (J81) Apple's META firmware now boots under Linux up to its idle loop.

**What is in it**
- `a8x/FIRMWARE-BOOT.md`: the field report (one device, Linux 7.3.0-rc1 on Orchard's `apple-4k` pin): the working sequence (Fender ConfigRAM replay at the GPC 0 to 1 request, the host-built firmware memory image and GPU page tables, the MMIO window table, thread 1's `{sp, pc}` config word), what the firmware does and where it parks, and what stays open.
- `a8x/README.md`: a status update; the A8X row in the top-level README.
- `tools/a8x/`: `j81_meta_ldr_layout.py` (offline META LDR parser and firmware-image layout builder, each rule citing the 19H394 instruction) with its tests, and `j81_f3a_build.py` (builds the 1 MiB blob the module copies into its DMA region). They read the firmware from the reader's own 19H394 kernelcache; the synthetic tests need nothing.

**Corrections to our earlier claims (please read)**: the Fender "override store hangs the bus" finding was a bug in our module (the Fender window was mapped 0x11000 bytes instead of covering `+0x20000`); the "machine dies when META runs" was our host watchdog; the F1 hang was a 512-byte buffer in our supervisor. All three are in the report.

**What it does not claim**: no GPU job was submitted and no frame rendered; the firmware does not post its first event record, and why is unknown because its code is MiniM (no public decoder). J81's `gpu = "missing"` in `devices/j81/device.toml` is unchanged.

**Apple data**: none committed here: no firmware, kernelcache content or captures, and the table of GFX bridge settings the module replays is not part of this PR. The module and runner live in mattonik/ipad-nixos (which already carries that table, `kernel/j81-gpu/gfx-bridge-plan.h`).

**Checked**: `python3 -I tools/a8x/test_j81_meta_ldr_layout.py` (11 tests, 2 skipped without images); with a real 19H394 image `j81_f3a_build.py` reproduces the blob used for the runs (sha256 `d9398bc5…a021`, heap checksum `7e5703a0`); the runs themselves are logged (runs 12 to 64) in the linked notes.

Written with AI assistance (Claude) and checked on the hardware, as the commit trailer says.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
