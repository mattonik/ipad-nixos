# Review of the Orchard reply on Fender, the boot stream and firmware loading (2026-11-24)

The reply (`a8x-reply-fender-fw-20261124.md`, not tracked) answers our questions about a J81 hang during Fender accesses in GPC state 0. It describes A8 (iPod touch 6, iOS 12.4) and A9 (iPad 5, iPadOS 16.7.10) behaviour.

This review checks each claim that can be checked against Apple's J81 code: the iPadOS 15.8.5 (19H394) kernel, sha256 `c3507666…a0008`, AGXG4G addresses without the `0xfffffff0` prefix. It is offline only; no hardware was used. The run that produced the hang is in the NAS mailbox, which was not mounted for this review, so its exact sequence is not checked here.

## 1. One real error on our side: the ConfigRAM 64-bit encoding

Apple's J81 64-bit stream writer, Fender slot `0xc8` (`0x669c66c`), stores four words:
1. `reg + 4`, with **no flag byte**;
2. `val >> 32`;
3. `reg | flag << 16`;
4. `val & 0xffffffff`.

Its caller, fw `+0x1e8` (`0x6691854`), passes the plain register (for example `0x100`) and flag `0xff`. This agrees with the reply and with Orchard's A8 driver.

Request 8's tool and `fender-configram.tsv` put `0xff` on the first word too. So the old table had `0x00ff0104`, `0x00ff1204`, `0x00ff3804`, `0x00ff380c` where Apple writes `0x00000104`, `0x00001204`, `0x00003804`, `0x0000380c`. Read the way Apple's encoding is built, Fender would take each old 64-bit entry as two flagged 32-bit writes: one to `reg + 4`, then one to `reg`.

Fixed in this change:
- `configram_words()`, with its test pinned to slot `0xc8`. The test failed against the old code on the word value itself, not on an import.
- The regenerated `fender-configram.tsv` and `manifest.json`. Only those seven words changed.
- The request 8 text and appendix.

New: `tool/j81_meta_ldr_layout.py --decode-configram WORDS.txt` decodes any word list and reports:
- a 64-bit write with a flag on its high half;
- a list that would start the META on replay (META_BOOT, or a final `SOFT_RESET = 0`);
- `BIF_CAT_BASE0 = 0`.

**Action:** if the runner's ConfigRAM test was built from the old table or the request 8 F2 text, run the decoder on its exact list. If it shows "not Apple's encoding", that run did not test Apple's stream. Whether this encoding caused the hang is not known.

## 2. The reply's claims, checked against 19H394

| Claim | J81 19H394 | Where |
|---|---|---|
| State setter: poll bit 4 every 10 µs up to ~30 s, then write `state \| 0x10`, no poll after | **Confirmed**, with one extra step: J81 reads `+0x1000` once right after the write (a dummy load, value discarded). It logs "Timed out waiting for GPC register" from `pollFenderReg` | slot `0x10` = `0x6698d94`; dummy read `0x6698e9c` |
| "Fender powered" flag at object `+0xc`; `getPowerState` returns 0 without MMIO when clear | **Confirmed** | slot `0x18` = `0x6698f24`; flag setter slot `0x30` |
| R0 read only if Fender powered, `1 ≤ state ≤ max`, and `+0` bit 29 clear | **Confirmed.** Max state is read from config (PLATFORM) `+0x29c`. With no Fender object it returns (`0x7a4d882 & 0x12) == 0x10` | `0x6692828` |
| Doorbell: `+0x14 = 7`, read state, at state 0 read `+0` and `+0x14`, then `MTS_SCHEDULE` | **Confirmed.** At state 0 with `+0 == 0` and accel `+0xe70` bit 0 clear, J81 calls `0x68ea90` first (Apple's restart, by analogy with A8 `0x846dc1c`) | `0x6690e04`–`0x6690ea8` |
| First wake: end marker, `+0 = 0x40000000`, `0x11`, tight poll with no timeout, 10 µs | **Confirmed** (request 8) | `0x683968` |
| Before the stream: `+0x10 = 0` ("mode 3"), `+0 = 0x40000000`, cursor reset | **Confirmed.** Hardware start calls slot `0x20` (which reads `+0x10` first), slot `0x58`, slot `0xa8`, then the stream, then the end marker | `0x6690bbc`–`0x6690cec` |
| Apple never reads the stream back | **Not on J81.** Every Fender store in 19H394 is followed by a dummy load of the same address: stream words (`0x669c634`, `0x669c69c`…), end marker (`0x669c608`), `+0` (`0x669c230`, `0x669c3d0`), `+0x14` (`0x669c410`). The A8 statement is about the iOS 12 kext | slots `0x58`/`0x68`/`0x80`/`0xb8`/`0xc0`/`0xc8` |
| A8 has no `0x20` core-word hold; A9 writes `0x20` and polls bit 5 | J81's slot `0x60` (`0x669c238`) is the A9 form: arg != 0 writes `+0x20000 = 0x20`, polls bit 5 (~0.5 s), then the busy bit. Its only caller with 1 is a META slave-port routine (`0x66906d0`, which also touches R0 `+0xa18`); the boot path writes 0, as on A8 | `0x669c238`; callers `0x6690378`/`0x6690438`/`0x669423c` (0), `0x669070c` (1) |
| Apple uses no gap after 1 → 0 | **True per instruction, but not in real time.** Between the 1 → 0 request in accelerator start and the first stream store, J81 runs the provider clock/power callbacks and the whole mapping and allocation phase (calls from `0x666d950` on). The real-time settle after 1 → 0 was not measured, but it is long, not microseconds [inferred] | `0x666d950`, `0x6690bbc` |
| GPU page size, firmware VAs, translator, alive wait in memory | **Confirmed** (requests 8 and 9) | — |

The consequence for the gap question:
- Apple's J81 code itself makes about 70 back-to-back Fender accesses in state 0, with no delay between them: `+0x10` read and write, `+0` store and load, 31 stream store/load pairs, and the end marker.
- So on J81, spacing between state-0 Fender accesses is unlikely to be the requirement.
- The variable left open is the settle time after the 1 → 0 request. Apple has a long host phase there, and the A8's 100 ms pause is the only shape Orchard has run.

## 3. Their observers and experiments, on J81

The PMGR words they suggest logging are already known on J81, at the same offsets:

| Word | J81 offset | Known J81 values |
|---|---|---|
| GFX PS | `0x20e020320` | `0x3ff` at the GPC poll, on both Linux and iOS (bit 28 clear, history bits 9:8 set) |
| GPU DVFS sequencer | `0x20e01c200` | `0x80000000` before the GPC request, `0x80110100` after |
| GFX voltage | `0x20e02300c` | `0` before, `0x164` after (the state-1 code is `0x64`) |
| PLL5 | `0x20e005004` | bit 30 is 0 on every hung read; `0x40000000` on working identity runs |

The A8 iOS value of PS bit 28 (`AUTO_PM_EN`) is 0 at run time. Our J81 genpd activation also leaves it 0. So their experiment 2 (clear bit 28) only matters if the runner's sequence sets bit 28. Check the logged PS word first.

Suggested J81 order, one variable per boot, with PMGR words logged into RAM before each Fender access and printed afterwards:
1. **Observers only** on the failing sequence: PS `[27:24]` and `[7:4]`, bit 28; `0x1c200` bits 31/30; `0x2300c` bit 31; `0x5004` bit 30.
2. **Settle:** 100 ms after the 1 → 0 request, then the same accesses back to back. This is the A8's only proven shape and the closest to Apple's real order.
3. **Sequencer wait:** after 1 → 0, wait for the busy bit, then for `0x1c200` bit 30 and `0x2300c` bit 31 to clear.
4. **Spacing:** `udelay(10)`, `usleep_range`, `msleep(1)`, `msleep(100)` between accesses. This is the cheapest of the remaining checks, and per section 2 the least likely to matter.
5. **Bit 28**, only if step 1 shows it set.
6. **Stream staging, with Apple's encoding:**
   - (a) empty stream;
   - (b) one 64-bit SLC write (`0x3808`), each word stored then loaded back, as J81's kext does;
   - (c) the two-write F2 list (`0x00003804 0x00035500 0x00ff3800 0x00300001 0x0000380c 0x00000000 0x00ff3808 0x00000001 0xffff0000`);
   - (d) the full list only with firmware memory and a page catalogue in place.

   Run every list through `--decode-configram` first.

## 4. What to send back to Orchard

They asked for our exact ConfigRAM list and which PMGR words we can log. A short answer:
- **The list:** 30 words and the end marker, as in the fixed `fender-configram.tsv`, with `BIF_CAT_BASE0` = the page-catalogue physical address. Say that our earlier list put `0xff` on the high-half words and has been fixed.
- **PMGR words:** those in section 3.
- **J81 differences worth telling them:**
  - J81's kext loads back every Fender store, including every stream word.
  - The setter adds one dummy read after its write.
  - J81 has the A9-style `0x20` core-word hold, used only by the slave-port routine.
  - The R0 licence on J81 reads its max state from PLATFORM `+0x29c`.

Sending is the user's step; nothing has been sent.
