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
