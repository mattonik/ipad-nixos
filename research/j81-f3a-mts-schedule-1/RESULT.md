# Research request 21 result: MTS SCHEDULE_ENABLE (RGX 0xbc8) and the uncounted device-control kick (J81, 19H394)

Sources:
- the 19H394 AGXG4G kext (J81 host), disassembled again after a scratchpad cleanup;
- upstream `pvr_rogue_cr_defs.h` and `pvr_fw_meta.c` / `pvr_fw_startstop.c`;
- Orchard's public docs in `context/orchard-public/`, plus Orchard's public lane-IP2 note (`OrchardLinux/gpu`, `a9/docs/release/orchard-0.4/lane-ip2/README.md`), read on GitHub;
- run 70 in `context/notes`.

Tags: **code** (the J81 kext), **source** (upstream), **orchard**, **capture**, **inferred**. There is no Apple binary content beyond addresses, offsets, field names and small constants.

## Short answer

- **Apple's J81 host never touches `0xbc8`, or any MTS register other than `0xb00`** (t1). No access, no immediate, no ConfigRAM entry, no string. Upstream Linux doesn't either. Upstream defines `0xbc8` as a plain 8-bit DM mask with no read-as-zero marking. So the enable belongs to the firmware, by elimination (inferred). Run 70 shows the firmware did program the MTS registers around it:
  - DM-to-thread association: `0xb30 = 0xffdf`, `0xb40 = 0xffff`;
  - the per-DM interrupt enables at `0xb58`–`0xb78`;
  - the garten fence address `0xc0000000` in `0xb50` (upstream: "the fence addr is set during the fw init sequence").

  It left SCHEDULE_ENABLE at 0. So its init ran, but it has not, or not yet, opened scheduling (inferred).
- **`0xb00 = 0x10` is DM0, counted, background, priority 0, with the HOST bit (8) clear** (t2). That matches all five of Apple's kick sites and upstream. With the mask at 0, the reading that fits run 70 is that the kick is dropped: no count in `0xba8`, no `0xbb0` bit, and the consumer doesn't move.
- **Correction to requests 17, 19 and 20: Fender `+0x14 = 7` is not a wake.** The kext's own Fender dump names `+0x14` TIMER_POWER_INT_STATUS. The kick path writes 7 there through the GPC object (vtable `+0x80`), which acknowledges status bits 2:0 (inferred: write-1-to-clear). The MTS write is the only wake.

  `+0x8` is TIMER_KICK_STATUS. The kext treats `+0` bit 29 as SNOOP: in state 0 a kick is caught by the Fender, and Apple warns when snoop is off (t3).
- **One host input differs from iOS: CONTROL `+0x20`, the idle-power-off enable.** iOS sets it to 1 by default:
  - the flag is set in `configureDevice` (`0x6670b54`);
  - it is copied into CONTROL in the POLICY fill before release (`0x6689fe0`);
  - only the `gpu_idle_poweroff` boot-arg changes it.

  Our blob leaves it 0 (t4). Orchard calls this word the "never-park" veto. On the A9 it gates only the self-park, and the A9 consumed its first type-8 command with it at 0. So it is a parity fix to test, not a proven cause.

## Q1: who writes 0xbc8, and is it readable

The kext's only RGX writes in `0xb00`–`0xbff` are the five MTS_SCHEDULE kicks. Beyond those, its only use of the range is META_BOOT `0xbf8`: set to 1 through the ConfigRAM list (`0x6690c74`) and read once in the failure dump.

`0xb08`–`0xb28` and `0xbc0` are neither defined upstream nor touched by Apple. Orchard's docs mention only the kick values. Request 18's comparison found no other MTS write in Orchard's driver; the reconstructed source itself was lost in the scratchpad cleanup, so I couldn't re-check it.

Whether `0xbc8` reads as zero on this MTS version can't be settled offline. N2's read-back after a host write settles it.

## Q2: what 0xb00 = 0x10 does (t2)

Bit layout from upstream:

| Bits | Field |
|---|---|
| 3:0 | DM |
| 4 | counted |
| 5 | background context |
| 7:6 | priority |
| 8 | host |

Apple's values:

| Site | Address | Value |
|---|---|---|
| TA | `0x6690e24` | `0x10` |
| 3D | `0x6690ffc` | `0x11` |
| CL | `0x66911d4` | `0x12` |
| kickFirmware | `0x6691380` | `0x10` |
| device control | `0x6691668` | `0x10` |

`0xba8` is an 8-bit pending count per DM. Run 70's single read 10 ms after the kick can't tell "never counted" from "counted and taken at once". N1's back-to-back read right after the kick can.

## Q3: expected values on a healthy boot

There is no capture, and no doc gives `0xbc8` or `0xba8` after alive. Apple's kext has no expected-value check or log string for them. The alive record's own field is "PC of waiting for BG kick", so a healthy firmware waits for MTS background kicks there. That only works with its DM enabled. So on a healthy boot I'd expect `0xbc8` bit 0 to be set by the time alive is posted (inferred).

The condition the firmware waits on before it sets the enable is not visible from the host. The candidates are a host input that differs from iOS (CONTROL `+0x20`, t4) or state the firmware reaches only on a fully working power path.

Orchard's IP2 note is the closest precedent. On the A9, the first type-8 command was not consumed when the map-time record differed: release at pstate 1, a sampler period, and two extra firmware words. It was consumed with Orchard's earlier record. J81's iOS host itself releases at state 1 (`setGPCPerformanceState(1)`, `0x6690390`), so that A9 factor doesn't transfer directly.

## Q4: next boots (t5)

1. **N1 (read-only):** Fender `+0x0`, `+0x8`, `+0x10`, `+0x14` and `+0x1000` around each step of the kick. Also `0xb98`/`0xba0`/`0xba8` right after the kick, and `0xb54`.
2. **N2:** write `0xbc8 = 0x00000001` (DM0 only), read it back, then repeat the kick. This is low-to-moderate risk: it hands the firmware the background task Apple's kick normally does.
3. **N3:** CONTROL `+0x20 = 1` in the blob, as on iOS. The firmware may then park after alive, so gate every RGX access on Fender state != 0. Kick anyway, as Apple does.

Other DMs (`0x11`/`0x12`) tell nothing new while the mask is 0.

## Q5: what else could drop a kick

- **Clock or power gating of the MTS:** unlikely in state 1, since the RGX bank answers reads with live, firmware-written values (capture).
- **SNOOP (Fender `+0` bit 29):** matters only in state 0 (t3).
- **`0xb50`:** reads `0xc0000000`. That is IDLE_CTRL = META, no SLC coherency, and fence address `0xc0000000`, the firmware's data base. The upper half (FENCE_DM, PC_BASE) is unread; read `0xb54`.
- **The interrupt enables** route disjoint bits (DM0 bits 6–7, DM2 bit 15, DM3 bits 2/3/5/8, DM4 bit 9). That looks like a deliberate, complete firmware init. The bit names are not known.

## A lead that needs your OK

Orchard publishes `tools/a9/firmware/minim.py` (`OrchardLinux/gpu`, MIT, 14,852 bytes). It expands MiniM to standard META for the binutils-2.30 `objdump`, following the public META HTP TRM; Orchard marks it provisional. Orchard used it to decode the A9 firmware's main loop and park logic (lane IP2).

This could finally decode J81's idle loop at `0x80009c14` and find what sets `0xbc8`. Request 16 found no such tool. Downloading it is your call.

## Not resolved

- What the firmware waits on before it enables scheduling.
- Whether `0xbc8` reads as zero (N2).
- The name of CONTROL `+0x18` (from accel `+0xe7c`, not traced).

## Files

- `t1-mts-access.tsv`: Q1, every MTS register: run 70, Apple's host, upstream, Orchard, and who sets it.
- `t2-kick-decode.tsv`: Q2, the MTS_SCHEDULE bits, Apple's five kick sites, and the counter reading.
- `t3-fender.tsv`: Q1/Q5, the Fender register names from Apple's dump, and the kick path. This is the correction above.
- `t4-host-inputs.tsv`: Q4(c), host inputs against iOS, including CONTROL `+0x20`.
- `t5-next-boots.tsv`: Q4, the ranked boots with exact values and risks.
- `SHA256SUMS`.
