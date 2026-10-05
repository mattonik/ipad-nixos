# Session handoff for the research agent, 2026-10-04

**This note is the authoritative current state.** Older dated notes and transcripts
are retained as history; where they disagree with this file (notably the D2207 GPIO
map and the touch status), this file wins.

Everything below was done in one working session and is committed. Hardware
results are summarized here and recorded in full, with their evidence, in the
linked notes; raw output stays private under the ignored `artifacts/live/`.
Labels: **E** observed or read in code, **I** inference, **U** unknown.

## TL;DR

Five hardware milestones, all with recorded sessions:

1. **Wi-Fi chip is reachable.** Asserting `WLAN_REG_ON` in-kernel before PCIe probe
   makes the BCM4350 (`14e4:43a3`, rev `0x05`) enumerate. Root cause of every earlier
   "no endpoint" result: the D2207 GPIO register map was wrong.
2. **SSH works** (Dropbear, key-only) with telnet kept as the permanent recovery path.
3. **Charging is automatic**: a boot-time policy uses a now-writable kernel sysfs
   property. **Agreed policy:** 2400 mA while capacity is below 80% and temperature
   below 42 C; **500 mA** at or above either limit, or if either reading is
   unavailable (resume below 38 C with hysteresis). The booted revision implements
   the 42 C / unreadable-temperature part; the 80% capacity cap (final form, 14 host
   tests) is committed and statically verified in the rebuilt tablet payloads but has
   not been booted.
4. **Touch controller powers up on J81** from Apple's recovered power order; its boot
   interrupt fires.
5. **Touch has power-up/IRQ and repeatable clocked RX evidence, but not a valid
   protocol ACK or proven command reception.** After Apple's power order the boot
   interrupt fires, and the controller returns a clocked, periodic 16-bit pattern
   (`f8 80`; shifted one bit in mode 2) that is repeatable across power cycles but
   independent of the bytes sent and matches neither recovered ACK (`4b c1`, `4a d1`).
   Whether the controller receives our commands is unproven. The next step is static
   research, then a separate explicit firmware decision (not taken).

Four static corrections to earlier notes (listed under "Corrections"): the GPIO map,
the KLCT decode (first wrong, then right), and the SPI mode inference.

## Hardware results (chronological)

| # | Result | Payload / tool | Note |
| --- | --- | --- | --- |
| 1 | `0x0403` write persists; PMU resets GPIO on reboot | console | [`j81-d2207-gpio-register-correction.md`](j81-d2207-gpio-register-correction.md) |
| 2 | **BCM4350 enumerates** (rev `0x05`, 2.5 GT/s x1, DLLLA set) | `m1n1-hoolock-pcie-reg-on-test` (patch `0050`) | same note |
| 3 | PCIe warnings (`retraining failed`, `iommu-map id 0x8`, `link_up=0`) all benign | read-only config reads | same note, last section |
| 4 | SSH stage 1: key auth, PTY, wrong key and password rejected, 3 reconnects, hash-checked file stream | `m1n1-hoolock-ssh-stage1` | [`../docs/plans/2026-09-26-tethered-tablet-and-charging.md`](../docs/plans/2026-09-26-tethered-tablet-and-charging.md) |
| 5 | Charging stage 2: sysfs write = raw `0x04c0` at 500/1000/2400 mA | `m1n1-hoolock-charging-writable-test` (patch `0017`) | [`../docs/plans/2026-09-13-pmic-pcie-execution.md`](../docs/plans/2026-09-13-pmic-pcie-execution.md) |
| 6 | Boot-time charging policy raises to 2400 mA; backoff path exercised | `m1n1-hoolock-tablet` | tethered-tablet plan |
| 7 | Touch read-only status | `touch-diag status` | [`j81-touch-diagnostic.md`](j81-touch-diagnostic.md) |
| 8 | **Touch boot interrupt** after Apple's power order (clock, LDO14, GPIO95, reset release) | `touch-diag run` | same note |
| 9 | spidev node + `spi-check` (configures spidev; no frame, nothing powered) | `m1n1-hoolock-touch-spi` (patch `0051`) | [`j81-touch-spi-experiment-design.md`](j81-touch-spi-experiment-design.md) |
| 10 | SPI runs A-E: mode 3/0/1/2, 1.984 MHz; periodic pattern, 1-bit shift in mode 2 | `touch-diag run --spi-dev ...` | same note, results 2-6 |

## Key technical findings

### D2207 GPIO and Wi-Fi power
- `_index2GPIOAddress(i)`: `0x0400|i` for `i < 0x11`, `3*i + 0x3e0` for 17-20. GPIO3 =
  `REG_ON` = register `0x0403`, GPIO2 = Bluetooth `power_enable` = `0x0402`.
- Config byte rule `(old & 0x1d) | 0x02` for level high: `0x09` = output low, `0x0b` =
  high. The data register `0x63+(pin>>3)` is only valid in input mode.
- The PMU **resets the GPIO config on every reboot/DFU cycle**, so the assert must be
  in-kernel before the PCIe probe (`kernel/patches/0050-...`, 100 ms delay).
- Bluetooth pin `0x0402` is untouched; it is a separate, user-approved step.
- Link success signal: the root port's **DLLLA** (LnkSta bit 13), not controller
  register `+0x88` bit 6. The BCM4350 is a 2.5 GT/s device on a port that advertises
  5 GT/s, which explains the benign retrain warning.

### Touch controller (iPad5,3 iOS 8.1 `AppleMultitouchSPI`, static)
- **Framing** ([`j81-z2-n1-transport-framing.md`](j81-z2-n1-transport-framing.md)):
  16-bit byte-sum checksum, high byte first; read `1c 73`, write `1e 33`, execute
  `1d 53`, calibration request `1f 01`, wake (`ee` at bytes 0/14), data chunk `18 e1`
  (max 1008-byte payload, 16 bytes overhead). Two different ACK words: **`4bc1`** after
  a data chunk, **`4ad1`** after a register write. Bootload order: firmware ->
  proximity cal -> cal -> `performCalibSeq` -> execute. The chip-version register
  (`0x10008ffc`, N1 = `0x434d11a0`) is read only after firmware.
- **Clock** ([`j81-touch-clock-kclt-a8x.md`](j81-touch-clock-kclt-a8x.md)): one register
  at **PMGR base + `0x1e000`**: bit 31 gate-off, 19 apply, 18 busy, 9:0 divider
  (`24 MHz / 32768 = 0x2dc`), settle delays 8 and 100. iBoot leaves it gated with
  divider 750.
- **GPIO polarity** ([`j81-touch-gpio-polarity-a8x.md`](j81-touch-gpio-polarity-a8x.md)):
  AP GPIO provider level = `v ^ flag1 ^ 1`. Reset GPIO82 is **active-low**; GPIO51
  (CS), GPIO95 (`power_ldo`), GPIO55 (`display_sync`) are active-high. Apple sends a
  16-byte dummy SPI transfer before reset release ("ensuring S_CLK is high").
- **D2207 GPIO map (corrected):** Bluetooth `power_enable` GPIO2 = register `0x0402`;
  Wi-Fi `REG_ON` GPIO3 = register `0x0403`. Earlier `0x03e6`/`0x03e9` values are wrong.
- **Power order that works on J81:** touch clock -> D2207 LDO14 (`0x0084` bit 2) ->
  GPIO95 high -> reset release. GPIO84 then falls (the boot interrupt). The dummy
  transfer and `display_sync` are not needed for the interrupt.
- **SPI:** `reg` words are `[cs, rate-field, flags, extra]`; rate-field x 16 kHz is the
  clock (Mesa node confirms with its explicit 8 MHz); touch = 124 -> 1.984 MHz; flags
  byte 3 = 8 bits per word. The extra word `0x1388` (5000) is unexplained (**U**).

## Corrections to earlier notes (all in git history)

1. **GPIO map** ("runtime ownership/lock" hypothesis for GPIO2): withdrawn. The earlier
   writes went to `0x03e6`, an unrelated region.
2. **KLCT clock**: the first revision today (`8ca1907`) decoded the **metaclass** vtable
   and described a wrong "`TCC_pwrctl` state field". Corrected in `13b8101`: the real
   handler is the divider register above. The iOS 10.3 helper layout was right.
3. **SPI mode**: the design inferred mode 3 from Apple's `0xd` reset value using the
   wrong (Samsung S3C) register layout. In the layout `spi-apple` actually uses,
   `0xd` = AUTO_TX | CPOL | ROLESEL = **mode 2**. Corrected in `cac3910`.
4. **Method lesson**: when decoding Apple IOKit classes, the constructor stores the
   **metaclass** vtable; the **instance** vtable is the one the metaclass `alloc` writes.
   Check both before trusting a slot.

## Open questions, in priority order

1. **Touch ROM is in an idle state.** The periodic pattern `1111 1000 1000 0000` is
   unaffected by our frames. Two untried boot-ROM preconditions:
   - Apple's "fw download mode" call (`function-enable_download`) around reset: absent
     from the J81 ADT text dump; decode what the driver does when it is missing.
   - the `display_sync` (GPIO55) drive.
   Both are static-analysis tasks in `AppleMultitouchSPI` (instance vtable first).
   **Update:** `function-enable_download` is optional and non-gating (J82 driver ignores
   the unsupported result). Apple's `display_sync` enable is a **pinmux of GPIO55 to
   peripheral function 1** (PERIPH field), not a level; GPIO55 is currently function 0.
   See [`2026-10-04-display-sync-pinmux-decode.md`](2026-10-04-display-sync-pinmux-decode.md)
   and [`2026-10-04-review-for-research-agent.md`](2026-10-04-review-for-research-agent.md).
2. **Firmware upload**: the recovered constructed packet is the exact payload Apple
   sends in one `18 e1` packet, then an ATN/ACK that must read `4b c1`. It needs the
   private asset from the IPSW and an explicit user decision. Not started.
3. **Unexplained IRQ event order**: one run saw GPIO84 rising first; the line always
   ended low. Cause unknown.
4. Review follow-ups for the staged PCIe patch `0052` (apply/build/gate, binding doc,
   `of_property_present`): see the review note above. **Bluetooth** `0x0402` assert (separate approval), BCM4350 firmware/NVRAM selection
   (gated on private-capture evidence), production PCIe link-wait on DLLLA.
5. Lower priority from the earlier plan: ANS1 read-only observation repeat, suspend,
   audio (CT819 ALS I2C probe groundwork), GPU.

## New tooling and artifacts

- `boot/touch-diag.c` (static C): `plan`, `status` (read-only), `spi-check` (**not**
  read-only: it configures spidev with write ioctls, sends no frame), and a guarded `run`
  (needs `--execute --approve-pmu-write`; unwinds on success, error or signal; refuses
  unless LDO14 is off and its voltage register reads `0x14`). SPI defaults: mode 2
  (Apple's decoded default) and 1.984 MHz; `--spi-mode`/`--spi-hz` override.
- `boot/tablet-status.sh`, `boot/tablet-dashboard.sh` (read-only refreshing screen,
  never auto-launched, packaged in the tablet-family payloads), `boot/charging-policy.sh` (+ host tests), `boot/ssh-stage1.sh`
  (Dropbear + telnet hook), `boot/test_ssh_stage1.py` (static payload gate; flags
  `--tablet`, `--touch-diag`), `boot/test_touch_diag_frames.py`.
- Kernel: patches `0050` (REG_ON assert), `0051` (spidev test child on SPI3, test
  binding `rohm,dh2228fv`, never the Z2 compatible), `0017` (writable charger limit).
- Flake outputs: `m1n1-hoolock-pcie-reg-on-test`, `m1n1-hoolock-ssh-stage1`,
  `m1n1-hoolock-tablet`, `m1n1-hoolock-touch-diag`, `m1n1-hoolock-touch-spi`
  (and their `*-kernel` variants). `tools/check_offline.py`: 20 passed, 7 skipped.
- Analyzer `boot/analyze_touch_capture.py` now recognizes the N1 frames and both ACK
  words, with 16 tests.

## Operating notes

- Boot recipe unchanged: DFU, then `sudo boot/vendor/palera1n-macos-arm64 --pongo-shell
  --override-pongo "$PWD/boot/Pongo.bin" --debug-logging` from inside `ipad-nixos/`;
  upload with `python3 boot/load_m1n1.py result/m1n1-linux.bin`; ping `172.16.42.1`.
  Each payload needs a fresh DFU cycle. `result` points at the payload under test.
- SSH uses a dedicated key pair (public key committed at `boot/ssh/authorized_keys`;
  private key under ignored `artifacts/live/ssh/`). The host key changes every boot.
- The agent harness blocked a command that carried `--approve-pmu-write`; the user ran
  those commands themselves. Keep PMU-writing runs user-executed.
- zsh does not word-split unquoted variables: run SSH helper lines in `bash -c`.

## Rules still in force

Document and commit every result; hardware tests are separate explicit decisions; PMU
writes need the user's go-ahead each time; no new hardware; never commit raw ADT/FDT,
calibration, firmware, device identifiers or session transcripts; no touchscreen
firmware upload, no `apple_z2` binding, no BCM4350 OTP/NVRAM access, no Bluetooth pin
write without a fresh, explicit decision.

## Not covered here

The earlier "October 2026 research/tooling handoff" and the 14 merged research branches
are already integrated; this session added hardware validation and the corrections above
on top of them. The pending disk-space cleanup request was never completed (the Mac had
77 GiB free; the builder VM disk was not checked).

## 2026-10-05 builder results (static only; nothing booted)

Following [`2026-10-05-touch-pcie-builder-handoff.md`](2026-10-05-touch-pcie-builder-handoff.md):

- **Touch:** the opt-in GPIO55 `display_sync` pinmux experiment is implemented in
  `touch-diag` (`--display-sync-pinmux --approve-display-sync-pinmux`, requires
  `--spi-dev`, refuses an already-muxed pin, restores the exact saved word on every
  exit). Built into the touch-diag and touch-SPI payloads; both gates pass; 13 source
  tests. See `j81-touch-diagnostic.md`. **Not run**; needs the user's approval.
- **PCIe:** patch `0052` (board-gated Wi-Fi `REG_ON`, `apple,reg-on-pmic` phandle,
  binding doc, `of_property_present`, intentional non-deassert comment) applies with
  zero fuzz to the exact Stage-5F source and builds. Payload
  `m1n1-hoolock-pcie-j81-reg-on` passes `boot/verify_pcie_j81_reg_on_payload.py`: checksums
  and composition, the phandle appears only on the PCIe node and resolves to the D2207
  `pmic@3c`, no `btattach` or I2C tools in the initramfs, only the board-gated REG_ON
  strings in the kernel. The `git diff --check` warnings on the patch are false positives
  from the patch file's own context lines; the added lines have no whitespace problems.
  Still inherited technical debt: the Stage-5F `+0x88` bit-6 link poll (the separate
  DLLLA cleanup is not done). **Not booted.**
