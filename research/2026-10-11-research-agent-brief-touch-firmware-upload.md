# Brief for the research agent: prepare and validate the J81 touch-controller firmware upload (offline), so the user can decide on it

Project: Linux on an iPad Air 2 (J81, A8X/T7001). Repo: `<repo>` (branch `main`). Method background: memory note "Apple firmware archaeology technique" (ipsw + Ghidra), `tools/ghidra/README.md`.

## Read first (in this order)
1. `research/2026-10-04-session-handoff.md` (touch sections: power order, clock, SPI mode, open questions), `research/2026-10-05-touch-pcie-builder-handoff.md`.
2. `research/j81-touch-diagnostic.md` (hardware results 1-3), `research/j81-touch-spi-experiment-design.md`.
3. `research/j81-z2-n1-transport-framing.md`, `research/j81-z2-legacy-ack-calibration.md`, `research/j81-z2-native-validation.md`, `research/2026-10-04-touch-callback-resolution.md`, `research/2026-10-04-display-sync-pinmux-decode.md`.
4. `research/j81-private-firmware-assets.md` (the private asset inventory: `usr/share/firmware/multitouch/J81.mtprops`, 83,479 bytes, SHA-256 `4feb5081...d1dc`, from the iPad5,3 iOS 8.1 12B410 root filesystem; the files stay under the ignored `firmware/` tree) and `docs/plans/2026-09-09-j81-touch-spi3.md`.
5. Code: `boot/touch-diag.c`, `boot/test_touch_diag_frames.py`, `boot/analyze_touch_capture.py`, `kernel/patches/0011-touchscreen-apple-z2-add-j81.patch`.

## The problem in one paragraph
The J81 touch controller (SPI3 `0x20a08c000`, Apple "Z2/N1" family, ADT node `multi-touch`) is fully powered by the recovered Apple order (touch clock, D2207 LDO14, GPIO95, reset release; SPI mode 2, 1.984 MHz) and raises its boot interrupt, but its ROM only returns an idle pattern (`1111 1000 1000 0000`, `f0 01 f1 01 ...`) that none of our frames changes.
Every non-firmware precondition is now tried (power order, reset, clock, SPI mode/rate, optional `function-enable_download`, `display_sync` GPIO55 pinmux). What we have not done is **upload the firmware**: Apple sends a preconstructed packet (`18 e1` ...) followed by an ATN/ACK that must read `4b c1`. The decision to upload is the user's; he needs to make it with the sequence fully specified and its risks understood.

## Your job: static / offline analysis only (no hardware, no builds, no committing private data)
Write `research/2026-10-11-touch-firmware-upload-spec.md` (and further notes if the analysis splits). Evidence = function addresses, offsets, short field values; **never raw firmware bytes, decompiler dumps or device identifiers**.
1. **Exact upload sequence in `AppleMultitouchSPI` (iOS 8.1, J81 personality).** From the instance vtable (not the metaclass vtable; see the method lesson in the session handoff) decode the bootloader/firmware-download path (`MTSPIBootloader` and its callers): the commands sent before the packet (bootloader entry/version read, reset or mode handshakes),
   how the firmware image is taken from the `.mtprops` file (which keys/sections: constructed firmware blob, calibration, product-id specific data; offsets and lengths), the framing of each transfer (`18 e1` header, length fields, checksums/CRC, chunk size, padding, inter-packet delays, ATN/IRQ handshakes, expected replies such as `4b c1`), the final launch/execute command and what the controller does afterwards
   (first reply, version/status read, the "boot complete" interrupt). Mark each step direct evidence / inference.
2. **Parse the private `.mtprops` offline** (read it from `firmware/`; do not copy it out): list its structure (plist keys, blob sizes, hashes of sub-blobs only), identify the blob(s) Apple actually transmits, and write a **packet builder** under `boot/` (e.g. `boot/touch_fw_packets.py`) that reads the asset path from an argument, emits the exact packet sequence to a private ignored directory, and prints only lengths/hashes. A host test must check the builder against the framing documents with synthetic data and against the recovered constants (header `18 e1`, ACK `4b c1`); no firmware bytes in Git.
3. **Linux-side comparison.** The pinned kernel has `apple-z2` (mainline `drivers/input/touchscreen/apple-z2.c`, patched for J81 by `0011`). How does its firmware/boot protocol differ from the older "N1/legacy" A8X sequence you decode (mainline Z2 expects a different firmware container and `z2_boot` steps)? State exactly what must change (new driver path vs reuse), and whether our `boot/touch-diag.c` SPI machinery can send the sequence as a userspace experiment first (spidev) without new kernel code.
4. **Hardware-safety review for the user's decision.** Is the firmware loaded into controller RAM (volatile; a power cycle returns to ROM) or can the sequence write non-volatile storage? What can a malformed or interrupted upload do (stuck bootloader, held IRQ, current draw)? What is the recovery (reset line GPIO, LDO14 cycle, full reboot)? Are there any rails or timing limits to respect (LDO14 voltage, reset pulse width)?
   State plainly the worst case you can establish from the evidence and what you cannot establish.
5. **A step-by-step hardware experiment plan** with explicit abort criteria and read-only checkpoints, using existing tooling where possible (`boot/touch-diag.c`, `m1n1-hoolock-touch-spi` payload, capture analyzer): what is sent, what reply is expected at each step, what a negative result teaches. This is a proposal for the user to approve; do not run anything.

## Constraints
No hardware access (the user runs hardware tests). No downloads without asking the user. Never commit firmware, `.mtprops` bytes, NVRAM, calibration, OTP, ROM/RAM dumps, MACs, device identifiers, Ghidra projects or session transcripts. Use `/opt/homebrew/bin/python3`, `command ls` (ls is aliased), no stdin-heredoc python. Path-limited commits with the trailer
`Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. If a Nix store path or Ghidra project is missing, ask the user before downloading or re-importing.

## Deliverables
1. The upload spec note (sequence, framing, timings, replies; evidence labels).
2. `boot/touch_fw_packets.py` + its host test, runnable on the private asset, committing no firmware bytes.
3. The Linux-versus-iOS protocol diff and the recommended implementation route (userspace spidev first, then driver).
4. The safety assessment and the hardware experiment plan for the user's approval.
5. A short list of anything in the existing touch notes that this analysis contradicts or supersedes.
