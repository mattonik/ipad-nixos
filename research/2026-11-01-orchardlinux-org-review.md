# OrchardLinux org review (2026-11-01)

Follow-up to `research/orchard-reuse-audit.md` (project library, 2026-10-29,
audited `OrchardLinux/hardware` at `619b916`). That repo is now
`OrchardLinux/orchard`; main has 279 commits on top of `619b916`.
Read-only review. Nothing built, nothing booted.

Local clones: `/Users/martinp/Work/Sandbox/orchardlinux/` (next to, not inside,
`ipadlinux/`). `linux/` is a shallow clone, all branches at depth 1.

## Repos

| Repo | What it is | State | Use for J81 |
|---|---|---|---|
| `orchard` | Hardware data, kernel patch layers, m1n1/Pongo patches, firmware recipes, recovery runtime, and the `orchard` host tool (Python, uv + Podman) | Active, 378 commits, main `18963da` | Main source; see below |
| `minimal-linux` | Alpine release image built on orchard | Active | Reference only |
| `omarchy-a` | Arch Linux ARM + Labwc touch desktop built on orchard | Active, 151 commits | Reference only. micro23 ran it natively on a J81 |
| `cli` | The old host tool | **Archived**, moved into `orchard` | None |
| `resize-apfs` | Swift app that shrinks APFS through palera1n | Tested on J71b iPadOS 17.7 | **Does not apply**: needs iOS/iPadOS 16 or later, and J81 tops out at 15.8 |
| `m1n1` (fork) | HoolockLinux m1n1 `idevice` | HEAD `d5a10ac`, the same commit as our nightly | Nothing new. Orchard's own m1n1 patches live in `orchard/boot/m1n1/patches` |
| `linux` (fork) | HoolockLinux kernel | HEAD `6831bc70`, **our exact pin** | Nothing new. Orchard's work is in patch files, not in this fork |

## What changed since the Oct 29 audit

1. **J81/J82 merged to main as experimental** (`4bf26ba`, 2026-10-30), with
   Martin's sign-off added to the DT and A8X patches (`b91162b`, `d00fd07`).
   micro23's J81 RAM boot on Orchard's kernel (2026-10-29) showed Wi-Fi, battery,
   display, backlight and buttons working, with no DART faults. So Orchard's
   seven deliberate differences from our port all hold on hardware: protection
   bits plus `DMA_BIDIRECTIONAL` RX, a single rebased mapping (no `apple,pci-alias`),
   DEVICE_WAKE before link training, all three PCIe power domains held, OTP-based
   NVRAM pick, and iPadOS 15.8.8 firmware `7.63.81.2`. This answers open
   questions 1 and 2 of the audit, and audit item B6 (dropping `0063/0064/0080`) is
   now low risk for us.
2. **Native install on J81 (contributor experiment, not on main).** micro23 wrote
   an ext4 root to internal ANS1 (`/dev/asp0n1p2`), after shrinking APFS with
   Apple's own tooling, and booted Omarchy natively with persistence across reboot.
   Source: `micro23/ipadair2-omarchy` `11463ba`, `experimental/j81-storage/`. Our
   ANS1 work is read-only. **This is the biggest new lead**, but writes carry
   the most risk (a global WRITE_UNLOCK guarded only in software).
3. **Air 2 touch** (`67c2a04`): our SPI3 node and 60 MHz clock, the iPad 5 N1
   runtime, a D2207 LDO `0x84` bit 2 analog supply (decoded from the ADT `pmuL`
   with iOS's LDO table), KLCT clock at PMGR `0x1e000`, and firmware from
   `J81.mtprops` via `z2fw-from-z2-packet@1`. **On a J81 it failed**: "two
   candidates tested, no response to taps" (`docs/integration/j81-2026-10-30-ui-followup.md`).
4. **iPhone 6 (N61, A8/T7000) touch works** (`5e254da`, Shayne Legault): a
   T7000 SPI variant (`spi/0003`, CFG `0x4018`, then `0x4038` with PIO, mode 0,
   8-bit) plus an `apple_z2` Gen1 path. The owner used it to type on two boots. It is
   the first working touch on our SoC's SPI block. Orchard's J81 touch uses that
   SPI controller.
5. **Air 2 Bluetooth** (`4f9b577`): UART3 on pins 14/15/32/33 with **function 1**
   (we used function 2), power on D2207 GPIO 2, BT_WAKE on AP GPIO 164, BCM4350C2
   USI patchram from BlueTool (J81 = STC), and `hci_bcm` with the iPad 5/7
   sequence. On a J81: "no successful HCI reset". Function 1 against our function
   2 is a concrete thing for us to try.
6. Also: an S8000 SPI with Berkay's validated PIO sequence (`spi/0005-0006`, now on
   main), the CT819 ambient light sensor probing on J81 (lux stuck at 0), and m1n1
   painting the boot splash.

## What is usable, and how

In order of value:

1. **Touch: diff our S5L SPI3 path against the N61 T7000 driver**
   (`kernel/patches/drivers/spi/0003`, `input/0006`, `regulator/0002`, `clk/0002`).
   This is the same SoC family's SPI block, proven on hardware. Check the CFG word,
   bit order (N61 uses the default MSB-first), the PIO feed, and the KLCT clock and
   LDO choice (Orchard's `0x84` bit 2 against ours). Offline source work. It
   replaces audit item B8.1 as the best lead on `4cb1`.
2. **Bluetooth: try UART3 function 1 and the D2207 GPIO 2 / AP GPIO 164 map** in
   one run. These are cheap DT changes, and our controller is silent today.
3. **Wi-Fi cleanup, now hardware-backed by micro23's run:** the five-cell DART
   window, dropping `0063/0064/0080`, plus `wifi/0002`+`0005` and `brcm,board-type`
   (audit item 4), and the clean set `wifi/0001,0003,0004`, `usb/0001-0002`,
   `spi/0001`, `pinctrl/0002` and `power/0011` (audit item 2). One build and one run.
4. **Storage: read micro23's `experimental/j81-storage`** before any ANS1 write
   work of ours. This needs Martin's decision. It is the only path to a native install.
5. Keep everything else from the Oct 29 audit (recipes, `hardware.txt` pattern,
   m1n1 from source).

Not usable: `resize-apfs` (iOS 16+ only), the `m1n1`/`linux` forks (identical to
our pins), `cli` (archived), and the distro repos beyond reference.

**Convergence:** the audit's question still stands, and it is now stronger.
Orchard boots J81 Wi-Fi with an upstream-shaped stack on our pin. Booting their
`examples/hardware-check --device j81` on our iPad would be one A/B run (needs
Hoolock's prebuilt Pongo, Podman, and a case-sensitive volume for the kernel cache).

## Follow-up: touch, "hot reload" and other tooling (same day)

**Touch.** N61 (iPhone 6, T7000) touch works with mode 0, 8-bit words, 500 kHz,
and CFG `0x4018`, then `0x4038` with PIO (`docs/bring-up/n61-touch.md`,
`spi/0003`). In that word bit 14 is set and bit 13 (our `APPLE_SPI_CFG_LSB_FIRST`)
is clear, so N61 seems to send **MSB-first**. Our J81 runs send LSB-first,
recovered from Apple's S5L config. 500 kHz is not new: we already ran it, and it
refuted the timing hypothesis. N61 is a Gen1 ROM and J81 is N1/Z2, so the
protocol differs, and Orchard's J81 port (T7000 SPI + iPad 5 N1 runtime) got no
taps on micro23's J81. The ROM reply it got is not recorded. The one new,
hardware-backed variable is the CFG word and bit order. It touches the parked
transport question (`touch-status`), so it needs Martin's go-ahead.

**"Hot reload".** Orchard has no live kernel replacement. It rejects kexec on
purpose (`docs/bring-up/bootloader/README.md`, `docs/integration/j71t.md` 2.8-2.9).
What makes its loop fast:
- a persistent incremental kernel tree in `kernel/.work/` plus an input-keyed,
  hash-checked component cache (`orchard cache`, hard-linked objects);
- a kernel SDK export, so module or DTB edits rebuild without the full kernel
  (`src/orchard/kernel_sdk.py`);
- `orchard push/pull/exec/shell` over USB SSH, SHA-256 checked, with a serial
  fallback up to 16 MiB.
For us this means building the touch/SPI drivers as modules, rebuilding only
the `.ko` and loading it with `rmmod`/`insmod`, with no DFU cycle. Caveat:
reloading `brcmfmac` reset an iPad 6 once (`j71t.md`), so keep Wi-Fi built in.

**Other things worth taking:** firmware recipes that pull only the needed files
from an IPSW by HTTP byte range, `capture-adt` without a PongoOS reboot, the
`hardware-check` example and `/run/hardware-check.txt` report, m1n1 built from
source with ADT touch-calibration forwarding (no private cal files), and
m1n1's boot-entry `launch` from a boot partition, for a later native install.

## Correction: the N61 SPI config matches ours (same day, later)

The "N61 looks MSB-first" lead above was wrong. Decoded against our S5L
definitions (`spi-apple.c` after patch 0007), N61's `0x4018` is `ROLESEL` (bit 3)
| `CLOCK_ENABLE` (bit 4) | `CLOCK_SELECT` (bit 14), and `0x4038` adds IRQ mode
(bit 5). Bit 13 is `APPLE_S5L_SPI_CFG_MSB_FIRST`, and it is **clear**, so N61 is
LSB-first like our J81 runs. Our `apple_s5l_spi_init()` writes the same bits 3, 4,
14 and IRQ mode. The only difference is the IRQ FIFO threshold field (ours 1 byte,
N61's 0), which does not change the wire. MSB-first was also our original
spidev default, and hardware already refuted it on 2026-10-11: the ROM's replies
only decode as valid HBPP words LSB-first
(`research/2026-10-11-touch-no-ack-analysis.md`). **No run was made.** The N61 SPI
config gives no new touch variable. The difference is the touch ROM itself
(Gen1 on N61, N1/Z2 on J81), and the touch upload stays parked for the bus
capture.

## Touch hints from Orchard's latest work (2026-11-01 evening)

- **iPad 5 touch works on hardware** (Orchard PR #28, Berkay Kösebay, stages 1-3):
  `iPad6,11 Touchscreen` probed with no firmware errors, and a 30 s drag gave
  12,600 events with 0 `SYN_DROPPED`. iPad 5 is personality `C1F15,1`, the same
  N1 bootloader class as J81's `C1F15,2`. Its boot sequence (`input/0009`): wake
  `19 c1` and NOP probe before reset release (we do the same), then the unit's
  **calibration first**, in packets of at most 0x3f0 bytes to `0x10009000`, each
  checked for ATN_ACK `4b c1` with five attempts, **then** the firmware packet, then
  N1 register calibration, `1f 01`, execute `0x10003400`. Timing: 10 us CS
  setup/hold, **no inter-word delay** ("as iOS' configureSPI() asks"), on the S8000
  SPI with Berkay's continuous-feed PIO sequence (`spi/0006`).
- **Our firmware bytes are right.** Orchard's `z2packet.extract()` run on our
  12B410 `J81.mtprops`, profile `C1F15,2`, returns 59,288 bytes, byte-identical to
  our `00-firmware-transfer.bin` (sha256 `9948ce32…`).
- **Their J81 packet is probably different.** The same converter on our mtprops
  gives z2fw sha256 `670eab55…`, but Orchard's J81 recipe pins `b9b4a072…` from
  iPadOS 15.8.8's `J81.mtprops`. Since the code is the same, the 15.8.8 packet most
  likely differs from iOS 8.1's (not verified, since we don't have the 15.8.8 file).
- Never tried on J81: a calibration-sized packet (≤ 0x3f0 bytes) **to `0x10009000`**
  sent before the firmware. Our size ramp sent packets to address 0, `0x400` and
  `0x10001800`, and never got `4b c1`. One ACK on a calibration chunk would prove the
  packet framing and wire path for the first time. It is a calibration-phase run,
  outside the standing touch approval.
- micro23's two J81 touch candidates on Orchard's driver got "no response to taps".
  The ROM replies are not published.

## Hardware result C1: calibration chunk first, 2026-11-01 (Martin approved)

Run C1 on payload `wifi-touch-kmod-K1` (run id `ea04e00d82b46e61351a9610ebdb6ab3`),
stock `spi_apple` module, private log `touch-cal-C1-20261101T194527Z.log`. First 0x3f0 bytes of the
unit's `multi-touch-calibration` (1024 bytes in our ADT capture, matching `MtCl`),
wrapped exactly as Orchard's `apple_z2_build_hbpp_blob()`: byte pairs swapped,
destination `0x10009000`, 1,024-byte packet, header `18 e1 30 01 00 fc 90 00 10 00 01 9c`.
`touch_upload_experiment.py --go --apple --spi-hz 1984000 --word-delay-us 5 --ack-tries 1`.

- Power-up and `DETECT PASS` as always (`1f 01` x 8).
- The packet went out in 9.3 ms. The ACK reply was **`1f 01`** (idle), not `4b c1`, and
  every post-query stayed `1f 01`. That's the same as every packet of 4,112 bytes or
  less in the size ramp. **The calibration-first order does not produce an ACK here.**
- **Stop rule hit:** the touch-clock register snapshot was `0x800002ee` before the
  run (divider 750), but the unwind left `0x800002dc` (divider 732, the tool's
  KLCT value). Earlier runs started from `0x800002dc`. The unwind writes the
  tool's own divider instead of restoring the snapshot. The clock gate (bit 31)
  ended disabled as before, so it is probably harmless, but per the standing rule
  I stopped here. The other iPad 5 difference, no inter-word delay, was **not run**.

## Hardware results D1, C2, F1: the remaining iPad 5 alternatives (2026-11-01 night)

Martin asked to try all the alternatives. Payload: the m1n1-from-source wifi-touch
payload (PR #16, built-in SPI, spidev child, 64 KiB buffer). touch-diag now has the
exact clock restore (`84faf99`), and every run unwound to `0x800002ee (was
0x800002ee)`. Temperature was 30.5 C. All runs used `--apple`, mode 0, LSB-first,
1,984,000 Hz. Private logs are under `artifacts/live/private/`.

| Run | Packet | Word delay | Attempts | Reply |
|---|---|---|---|---|
| D1 | 12B410 firmware, 59,288 B | 0 us (iPad 5 timing), 245 ms on the wire | 1 | `4c b1` |
| C2 | calibration 0x3f0 B to `0x10009000` | 0 us | 5 | `1f 01` every time |
| F1 | **iPadOS 15.8.8** firmware, 59,288 B | 5 us | 1 | `4c b1` |

The 15.8.8 `J81.mtprops` came from Apple's IPSW by HTTP byte range with Orchard's
`remote_ipsw` (3.0 MB read, sha256 `457c7af5…`, matching Orchard's recipe; stored
privately under `firmware/j81-19H422/`). Its `C1F15,2` packet differs from 12B410's
in only **4 bytes** (offsets 29735, 29775 and the checksum trailer), and its z2fw
reproduces Orchard's pinned `b9b4a072…`.

**Conclusion:** none of the iPad 5 differences changes the ROM's answer. Not the
inter-word delay, not calibration-first to `0x10009000`, not five attempts, not the
newer firmware. Together with C1 and the October size ramp, the replies still
depend only on how many bytes are clocked. That points back at the wire itself,
which the parked bus capture would show. The one iPad 5 element we cannot copy is
its S8000 SPI controller with Berkay's continuous PIO feed.

## Hardware result P1: full-duplex upload on the current S5L driver hangs after 32 bytes

Same payload and settings as F1, with `--upload-rx` (the full 12B410 packet sent full
duplex, so RX is drained). The transfer fails with `-ETIMEDOUT`. dmesg: `polled
transfer timed out (remaining 59256 tx, 0 rx), status=0x400433`. Decoded with our S5L
definitions: TX FIFO level 16 (full), RX FIFO level 0, `HUNG` (bit 4) and
`RXL_TIMEOUT` (bit 5) set. The controller stopped after 32 bytes, two FIFOs' worth.
Clock and power unwound exactly. **So the S5L PIO path still hangs whenever the
receive side is active**, the failure 0098 only fixed for transmit-only. The
"remaining 0 rx" with an empty RX FIFO also suggests the RX accounting is off.
Berkay's S8000 fix addresses exactly this class of problem: both word counts set to
the full length, RX always drained, and never more than one FIFO of unread words in
flight. Our transmit-only uploads leave `RXCNT = 0` and never read RX at all. Whether
that also corrupts the long transmit-only stream (the byte-count thresholds) is the
hypothesis the PIO port tests.

## PIO port, first hardware runs S1-S4 (2026-11-02 morning)

Payload `wifi-touch-kmod-K1` (run id `ea04e00d…`), freshly booted. The `spi_apple` work
copy has a new S5L bounded-PIO loop after Berkay's S8000 sequence (diff:
`research/2026-11-02-s5l-bounded-pio-wip.diff`; switches `s5l_bounded_pio`,
`s5l_bounded_autotx`, `s5l_bounded_mode`, all writable at runtime). Every run used
`--apple`, 1.984 MHz, 5 us word delay, and full-duplex probe frames of 16 to 4096 bytes
(no firmware). Clock and power unwound exactly on every run.

| Run | AUTO_TX | CFG mode after RUN | Result |
|---|---|---|---|
| S1 | off | polled (0) | the 2-byte wake `19 c1` times out: TX 2 sent, **no RX at all** (status `0x30`, HUNG + RXL_TIMEOUT) |
| S2 | on | polled (0) | wake, dummy and detect OK (`DETECT PASS`); probes of 16 and 32 B return `1f 01`; **64 B fails after 32 words** (status `0xc30`: TX level 16, RX level 1 with nothing outstanding) |
| S3 | on | PIO enable (1) | same as S2: 32 B OK, 64 B stops at 32 |
| S4 | off | PIO enable (1) | as S1: no RX |

Findings: on the S5L, **receive needs AUTO_TX**, and with AUTO_TX the controller stops
after exactly 32 words (two FIFOs) and reports a full TX FIFO we didn't fill. That is
the same 32-word wall as P1 and as the pre-0098 transmit-only hang. So the S5L does
not take the S8000 sequence as-is. The likely reading is that AUTO_TX makes the
controller generate its own TX words, which conflicts with fed data. Apple itself
uses PIO only below 0x100 bytes, in IRQ mode with thresholds 0x180, and DMA through
SmartIO above that. The stock module was loaded again afterwards. Next options:
Apple's IRQ-mode PIO for transfers up to 255 bytes, then decide whether the long
transmit-only stream needs the same treatment. Or go straight to SmartIO DMA, which
is the larger job.

## FIRST TOUCH ACK: Apple's S5L PIO order fixes the upload (2026-11-02, runs S5, F-tx, F-rx)

Apple's PIO path, decompiled from the iPadOS 15.8.8 J81 kernelcache (`AppleSamsungSPI`,
`FUN_fffffff005c1e5c4` transfer and `FUN_fffffff005c1edd4` start; the kernelcache came
by byte range with Orchard's `remote_ipsw`, 19.7 MB read, sha256 `832cd980…`):

1. RXCNT = TXCNT = max(tx, rx), **also for transmit-only**. The extra receive words are
   discarded. This corrects our October note "Apple writes RXCNT = 0", which was wrong.
2. CLKDIV (`0x30`), WORD_DELAY (`0x38`), STATUS clear, CFG = base (`0x4018` on J81:
   ROLESEL, CLOCK_ENABLE, CLOCK_SELECT; **no AUTO_TX**, FIFO threshold 0).
3. **CTRL = `0xd` (RUN | TX_RESET | RX_RESET) in one write.** The `0xd` earlier notes
   decoded as "CFG = AUTO_TX | …" is this CTRL value.
4. CFG |= bit 5 (PIO mode), then prime the TX FIFO (padding with `0xff`), then the IRQ
   enables (0x100, or 0x80 for receive-only) and IRQ-driven refills.

The work-copy module follows 1-4 with polled, bounded refills (diff:
`research/2026-11-02-s5l-bounded-pio-wip.diff`, module sha256 `2ff43506b3e10c32…`, switch
`s5l_bounded_apple_order`). Payload `wifi-touch-kmod-K1`, `--apple`, 1.984 MHz, 5 us word
delay, clock and power unwound exactly on every run:

- **S5**, full-duplex probe frames 16 to 4096 bytes: all complete, with no hang (the
  32-word wall is gone). The ROM answers `48 79` instead of `1f 01`; `0x4879` is in
  Apple's accepted HBPP word set.
- **F-tx**, the 12B410 firmware packet (59,288 B) transmit-only: 541.6 ms, **ACK reply `4b c1`,
  ACKNOWLEDGED.** This is the first ACK this project has ever had from the J81 touch ROM.
- **F-rx**, the same packet full duplex: the ROM sent `48 79` for all 29,644 words during
  the transfer, then **`4b c1`, ACKNOWLEDGED.**

**Root cause of the October `4c b1` / byte-count thresholds: hypothesis H3, wire corruption
in our S5L PIO path.** The fix is the controller start order and counts, not the
firmware, timing, order or bit order. Next, outside the standing approval: N1 register
calibration, calibration upload, `1f 01`, then execute `0x10003400`. Then turn the module
change into a kernel patch and do the reproducible build.

## The J81 touch firmware boots (2026-11-02, run B1)

Same payload and bounded-PIO module, temperature 29.8 C, private log `touch-n1boot-B1-20261102T061629Z.log`.
touch-diag gained `--upload-cal FILE` and `--n1-boot --approve-execute`, which do the
post-firmware sequence from OrchardLinux's N1 driver (`input/0009`, `0014`; iOS
`MTSPIBootloader_N1`). The harness gained `--cal-files` and `--n1-boot`. Sequence and replies:

| Step | Reply |
|---|---|
| detect | `1f 01` x 8, DETECT PASS |
| firmware 59,288 B (12B410), transmit-only | ACK `4b c1` |
| calibration chunk 0x3f0 B to `0x10009000` | ACK `4b c1`, first attempt |
| calibration chunk 16 B to `0x100093f0` | ACK `4b c1`, first attempt |
| read version `0x10008ffc` | **`0x434d15c1`** (so const-cal 3, not the 0x434d11a0 case) |
| writes fll-mval 6068, `0x1000305c`=0x20, `0x10003058`=6, const-cal 3, clk32-enable 1 | ACK `4a d1` on all five |
| read SPI_APU_EN `0x10003800` | 0 |
| calibration request `1f 01`, 65 ms | status `49 69` |
| execute `1d 53` `0x10003400` arg 0x100 | sent |
| next 2 s | **17 interrupt edges**, line low |
| NOP frame after execute | `e1 0e 00 … 00 ef 00`: no longer an HBPP word, a runtime frame |

**The touch controller left its bootloader and is running firmware, raising its
interrupt line.** The clock and power unwound exactly. Next: the runtime protocol, which is
discovery (E2 x2, family `0xd1`, sensor `0xd3`, region `0xd0`/`0xa1`, surface `0xd9`) and
EB/E3 report reads, i.e. Orchard's `apple_z2` N1 runtime with the J81 match. Our modular
kernel builds `apple_z2` as a module, so this can come in through the same reload loop.
It also needs a touchscreen DT node instead of the spidev test child.

## apple_z2 on J81, run Z1 (2026-11-02, partial)

Payload `wifi-touch-z2-kmod-Z1` (run id `16056205…`) booted. m1n1 copied the calibration
into the touchscreen node (`apple,z2-cal-blob` and `apple,z2-prox-cal-blob` present under
`/proc/device-tree`). The bounded-PIO `spi_apple` loaded, the private z2fw (59,376 B,
sha256 `670eab55…`) went to `/lib/firmware/apple/j81-fwstart.z2fw`, and `touch-diag hold`
turned on LDO14 (0x04) and the touch clock (`0x000802dc`) from the snapshot `0x00` /
`0x800002ee`. OrchardLinux's `apple_z2` module (rebuilt from their Pauli and driver patches)
then **failed probe: `error -ENODEV: unable to get display-sync pins`**. The J71t/J81 path
calls `devm_pinctrl_get()`, which returns `-ENODEV` for a node with no pinctrl properties at
all. In Orchard's DT the node probably inherits a pinctrl device. The work copy now treats
`-ENODEV` as "no display-sync pins" (J81 leaves the pin an input, as iOS does) and builds.
Before it could be loaded, the session hit its usage limit and the iPad stopped answering, so
there is no driver result yet.

## apple_z2 on J81, runs Z1b-Z1d (2026-11-02 afternoon): input device, discovery passes, no contacts yet

Same Z1 payload, rebooted (run id `16056205…`). Bounded-PIO `spi_apple`, `touch-diag hold`,
private z2fw, then OrchardLinux's `apple_z2` as a module with three J81 changes (diff
against Orchard's file: `research/2026-11-02-apple-z2-j81-wip.diff`): no display-sync
pinctrl is accepted, **J81 family 22** (the iPad 5 reports 21), and sensor/surface
mismatches only warn. Debug dumps were added.

- The driver boots the chip by itself: detect, firmware, calibration from the DT blob m1n1
  wrote, the N1 registers, execute. **`input: iPad5,3 Touchscreen` registers as event1.**
- Discovery passes exactly: device info `e2 16 01 92 09`, family `0x16` (22), sensor
  little-endian 40x30 (`01 28 1e`), firmware version `0x381`, region `d0`/`a1`, and surface
  14745x19657 (the same as the iPad 5's, so the inverted-y default and the scaling apply).
- At runtime the firmware raises ATN a few times and sends frames
  `ea NN 0e 00 | 0x 50 02 00 00 00 00 0x 00 xx 27 00 00 | ck ck`: report **`0x50`**, not the
  contact reports `0x43..0x45` the iPad 5 parser handles. The length query right after a
  frame repeats `e1 0e` but its data phase reads all zeros, which the driver counts as a
  bad frame (`-EBADMSG` → "touch frame error -74, resynchronising"). Resync then succeeds.
- Three touch windows (Z1b 60 s, Z1c 45 s, Z1d 40 s; whether Martin touched during each is
  not confirmed): no input events, and only a handful of interrupts in total. If he did, the
  J81 firmware isn't sending contact reports in this mode yet.

Next: find out what iOS sends after discovery to start contact reporting on J81 (the
iPadOS 15.8.8 `AppleMultitouchN1SPI` is in the kernelcache we already fetched), decode
report `0x50`, and tolerate the stale length reply after a frame.

**Run Z1e (confirmed touching):** Martin touched continuously ("still touching" at the
1-minute mark) through a 120 s capture, with the interrupt count logged every 5 s. **The
count stayed at 6, the post-boot total, for the whole window, with 0 input events.** The
running J81 firmware sends no interrupts for touches in this state, so contact reporting is
not enabled, or not routed to the ATN line, after Orchard's iPad 5 discovery sequence.
Afterwards `apple_z2` was unloaded and `touch-diag release` restored LDO14 and the clock.

**Run Z1g (report-enable experiment):** iPad rebooted on Z1 (run id checked first). The
`apple_z2` work copy gained `j81_init`, which writes the iPhone 6 (N61) report sequence
after discovery: `e4 9d 08 01 00…` / `e4 bf 04 9d 81 09 00` / `e4 af 01 00`, each followed by
`e1`. The firmware's echo bytes after each write were `e4 9d 03`, `e4 bf 00` and `e4 af 03`.
Read as status, `bf` was accepted and `9d`/`af` were rejected (an inference). The same
runtime then followed: report `0x50` frames, then the stale zero-data read. In a 90 s touch
window the interrupt count stayed at 2 (the boot edges) with 0 events. GPIO 84 reads high
afterwards (`/sys/kernel/debug/gpio`), so the line isn't stuck asserted: the chip just never
signals. Whether Martin touched in this window wasn't confirmed, but Z1e (confirmed) behaved
the same. Released LDO14 and the clock afterwards.

**Decompile result (iPadOS 15.8.8 `AppleMultitouchSPI`, `__TEXT_EXEC 0xfffffff005de0000`,
0x139c8 bytes):** the kernel driver writes no report to enable contacts. The only report
it sets on its own is power stats `0x72`. Reports `0x30` and `0x31` are driver-internal
(interrupt read delay / repeats). Everything else comes through `deviceSetReport` from
`AppleMultitouchSPIUserClient`, i.e. the userspace MultitouchSupport framework. The next
source is therefore MultitouchSupport in the 15.8.8 dyld shared cache (the full IPSW is on
the NAS).

**Userspace side (iPadOS 15.8.8 dyld cache, extracted from the NAS IPSW with `ipsw extract
--dyld`):** MultitouchSupport `MTDevicePowerSetState` builds a 0x204-byte request of type 4 with
the state byte and sends it with `MTDeviceIssueDriverRequest`, which is a kext request and not a
device report. `MTDeviceSetTouchMode` only posts notifications and input-detection masks
(`0x8009`, `0x819d`, `0x8199`). The kext also applies an optional `DefaultReports` property,
an array of (report ID, data) pairs written with "Setting DefaultReport 0x%02X". But the string
`DefaultReports` appears only once in the whole J81 kernelcache (the kext's own lookup), so no
J81 personality sets it. So far nothing in iOS sends a "start reporting" report to the J81 N1
firmware. Remaining suspects: hardware-side, i.e. the display-sync routing (GPIO 55; Orchard
reads iOS function code 2 as "input", which may mean "peripheral route 2") or a missing
supply/clock difference; or a mode change carried in the kext's power-state handling.

**Run Z1h (display sync):** Z1 boot (run id checked), `apple_z2` booted the chip as before
(input1, 2 interrupts). With the driver running, `touch-diag dsync N` moved GPIO 55 from its
boot word `0x00072a82` (PERIPH 0) to peripheral function 1, 2 and 3 in turn (`0x…aa2`,
`0x…ac2`, `0x…ae2`, each read back), for a 30 s touch window each while Martin touched
continuously. **The interrupt count stayed at 2 and there were 0 events in every window.**
`dsync-restore` put back `0x00072a82` each time, and power and clock were released afterwards.
Routing display sync after the boot doesn't start contact reporting. Not tested: routing it
before the firmware starts.

Where this leaves J81 touch: SPI is fixed, and the bootloader, calibration, registers,
execute and the runtime discovery all work. The firmware sends report `0x50` status frames
but never signals a touch. That matches micro23's "no response to taps" on Orchard's J81
port, which uses the same post-boot flow.

**Run Z1i (display sync routed before the firmware boots):** same Z1 boot. For each function
N: `touch-diag dsync N`, then `insmod apple_z2` (which boots the chip with the pin already
routed), a 30 s touch window while Martin touched, then `rmmod` and `dsync-restore`.
- **N = 1:** the read-back word had bit 0 set (`0x00072aa3`, the pin reads high), and **the
  driver's boot failed: `probe … failed with error -71` (EPROTO)**. Function 1 interferes
  with the bootloader handshake.
- **N = 2 and N = 3:** the boot succeeded (input3, input4, two interrupt edges per boot, so the
  cumulative count went 2 → 4 → 6), but **no interrupts and 0 events during either touch
  window**.

So display sync, routed before or after the boot, doesn't start contact reporting. Everything
was restored (GPIO 55 back to `0x00072a82`, LDO14 and clock released).

**Offline trace of iOS's post-bootload path (15.8.8 `AppleMultitouchSPI`,
`bootloadTimerFiredHandler` at `0xfffffff005de1844`):** after "successfully bootloaded
device" the kext marks firmware present (vtable +0x780), posts a state change (+0x6c8, 1),
sleeps 2 ms, caches device properties (+0x608, the discovery Orchard already reproduces),
runs +0x5a0, publishes "Driver is Ready" and posts state 2. Its only device writes besides
discovery are `deviceSetReport` (`e4` short / `e5` long, `FUN_fffffff005deeadc`), used for
power stats `0x72`, the optional `DefaultReports` (none for J81) and userspace requests.
This 15.8.8 trace does not establish the older 12B410 path: its J81 personality sets
`AutomaticallySetOperatingMode`, and its post-discovery `+0x598` method sends
`rOPERATING_MODE` report `0xab {0}`. A synchronized 60-second live touch test showed
that the accepted write still yielded zero contact IRQs and input bytes.

The ADT's `multi-touch` node (J81 capture) lists functions beyond the ones Orchard uses:
`function-enable_cs` (GPIO 51 = the SPI CS pin, args `01 01 00 00`), `function-power_ana`
(PMU `Lump 0x20e`, already decoded as LDO14), `function-display_sync` (GPIO 55, args
`01 01 00 02`, the same shape as `function-power_ldo` GPIO 95 `01 01 00 00` apart from the
last byte) and `function-clock_enable` (KLCT). Untested idea: display sync may want to be
**driven as a GPIO output** (like power_ldo) rather than routed to a peripheral function.

**Run Z1j (display sync driven as a GPIO, new `touch-diag dsync-gpio LEVEL SECONDS`):**
- **High:** the chip boots but **discovery fails: `device information failed: -74`**, so probe
  fails. A first low attempt overlapped the still-held high line and failed the same way.
- **Low (clean rerun):** the boot and discovery succeed (input7), but a 35 s touch window while
  Martin touched gives **no new interrupts and 0 events**.
Display sync clearly affects the controller (high, or peripheral function 1, breaks the
handshake), but no tested setting makes it report contacts. Released afterwards.

**Status: J81 touch parked here (2026-11-02), as agreed with Martin.** Everything up to a
running N1 firmware that answers discovery works on our stack. The open problem is that the
firmware never raises ATN for touches. The remaining untested ideas are the analog
rail level (LDO14 voltage `0x14` is never changed), `function-enable_cs`, the exact
display-sync transition during boot, or a bus capture of iOS. The PMU
`function-sensor_power` (`Lump 0x202`) belongs to the Oscar motion coprocessor ADT node,
not touch. Both the 12B410 and 15.8.8 firmware images booted with Apple's
proximity/touch calibration order and still
produced no contact IRQ during confirmed touch windows. The 12B410 post-discovery
`0xab {0}` write was also accepted but produced no contacts.

**Correction (2026-11-02 evening, from Martin's `research/2026-11-02-j81-touch-runtime-gap.md`
in the `ipadlinux-bt-ab` checkout):** the PMU `function-sensor_power` (`Lump 0x202`) listed
above as an untested touch lead belongs to the ADT's **Oscar motion-coprocessor** node, not
to `multi-touch`. Touch's `function-power_ana` (`Lump 0x20e`, LDO14) is already on in every
run, and LDO14's stored `0x14` is the documented 6 V code. Drop both from the touch leads. That
note also rules out Apple's bootload order with proximity calibration, the 15.8.8 firmware
(`0x382`), and the iOS 8.1 `rOPERATING_MODE` write (`e4 ab 01 00`, accepted with status 0), and
shows GPIO84 sampling high for a full touch minute. What's left: a forced report read during a
touch (silent queue vs. no scanning), and display sync routed at Apple's exact wake-to-dummy
point with reset asserted.
