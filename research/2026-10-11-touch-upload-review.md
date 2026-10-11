# Review of the touch firmware upload spec and exporter (2026-10-11)

Reviewed: `research/2026-10-11-touch-firmware-upload-spec.md`, `boot/touch_fw_packets.py`, `boot/test_touch_fw_packets.py` (research agent, commit `ed9c058`). The agent's tests pass (`boot/test_touch_fw_packets.py`, `boot/test_touch_diag_frames.py`: OK).

## What is solid
- The sequence is fully recovered and carefully labelled (E/I/U): one constructed-firmware transfer (59,288 bytes, starts `18 e1`, taken verbatim from `Constructed Firmware` in `J81.mtprops`, personality `C1F15,2`, packet type `Z2`), then the 2-byte ACK query `1a a1`, expected big-endian reply `4b c1` (retry the same packet plus query at most five times); only then calibration transfers, N1 calibration, and the execute command (`1d 53`, address `0x10003400`, byte sum).
  The pre-upload version read in my earlier brief was a sequencing mistake (the `0x10008ffc` read comes after firmware + calibration); the spec corrects it.
- Mainline `apple_z2` is not a J81 uploader (different container and completion semantics): do not bind the J81 compatible to test this.
- Safety: volatile-style load evidenced (no erase/program commands in the recovered J81 path); worst established case is a stuck bootloader/IRQ until reset; recovery = reset, GPIO95 off, LDO14/clock restore, cold reboot; abort on any reply other than `4b c1`.
- Recommendation accepted: approve only the single-transfer + `4b c1` ACK experiment, no calibration/execute, no kernel driver.

## Gaps I found checking against the source (prerequisites for the hardware run)
1. **The asset is not staged.** `firmware/j81-12B410/touch/J81.mtprops` does not exist: only `firmware/j81-12B410/{ipsw,keys,wifi}` (the 2.2 GB IPSW, the keys file with `RootFSKey`, and the extracted Wi-Fi files). The earlier mounted root filesystem is gone. The exporter needs the file extracted again from the encrypted `058-01629-167.dmg` inside the IPSW (nixpkgs `ipsw`, blacktop, can mount it with the key; a pure-Python decryptor would be impractically slow). Extraction is local and private; the tool comes from the Nix binary cache.
2. **`spidev` limits a message to 4096 bytes by default** (`bufsiz = 4096`, `drivers/spi/spidev.c`; `-EMSGSIZE` above it). A 59,288-byte single message needs `spidev.bufsiz=65536` (or more) on the kernel command line of the `m1n1-hoolock-touch-spi` payload (spidev is built in there: `CONFIG_SPI_SPIDEV`); the spec does not mention it.
3. **SPI controller behaviour for a 59 KB message** (`drivers/spi/spi-apple.c`, S5L type): one `transfer_one` programs TXCNT with the whole length and refills a 16-word FIFO from interrupt/poll PIO; the core keeps CS asserted for the message, so CS continuity looks fine by design. At 1.984 MHz the transfer lasts ~0.24 s, but a refill gap
   can pause the clock mid-transfer; whether the touch bootloader tolerates a paused clock is **unknown** (the spec's "exact maximum transfer size / CS continuity" unknowns narrow to this). An abort on timeout/unexpected reply and a power cycle remain the recovery.
4. The experiment needs a DFU cycle with the touch-spi payload and the same user-run self-restoring script pattern used for the Bluetooth tests (the tool-use classifier blocks pad/PMIC writes from the assistant's shell).

## Update (same day): the asset is staged and the packets are exported (offline)
With the user's approval to fetch `ipsw` from the Nix cache (nixpkgs `ipsw` 3.1.673), the encrypted root filesystem `058-01629-167.dmg` was mounted read-only from the local IPSW with the key from the private keys file (`ipsw mount fs ... --key ... --detach`, scratch mount point, never printed),
`usr/share/firmware/multitouch/J81.mtprops` (83,479 bytes) was copied to the ignored `firmware/j81-12B410/touch/J81.mtprops` (mode 0600) and **its SHA-256 matches the recorded `4feb5081...d1dc`**; the filesystem was unmounted and the temporary decrypted DMG deleted.
`boot/touch_fw_packets.py` then exported, offline and with no hardware access, to `firmware/j81-12B410/touch/upload-packets/` (mode 0600, ignored): `00-firmware-transfer.bin` (59,288 bytes, sha256 `9948ce32...54e2`) and `01-data-ack-query.bin` (2 bytes), expected reply 2 bytes.
Remaining before the hardware experiment: `spidev.bufsiz=65536` in the touch-spi payload's command line, a user-run send script with the documented abort/recovery, and a DFU cycle; none of it done yet.
