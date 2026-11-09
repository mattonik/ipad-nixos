# J81: live read of the GFX perf-state table (read-only)

Date: 2026-11-08. One read-only `/dev/mem` snapshot on the running J81
(Linux 7.3.0-rc1, about 30.8 h uptime). The boot had earlier run only the
MCC read-once test ([MCC read result](2026-11-08-j81-mcc-read-result.md)).
No GFX power-up, bridge write, GPC or RGX access happened in this boot.
Follows the [iBoot/LLB note](2026-11-08-j81-iboot-llb-gfx-perf-state.md).

Tool: [`boot/gpu-pmgr-perf-peek.c`](../boot/gpu-pmgr-perf-peek.c) (static
aarch64, sha256 of the stripped build
`eb446a661e5414e038b049d9ce425458234ef3464248b1c0e90e4c2316a49fc5`). It
maps two PMGR pages read-only and reads 18 words. The raw log is kept
private under `artifacts/live/gpu-pmgr-perf/`. The device answered a shell
command right after the read.

## Values

| Address | Raw | Decoded |
|---|---|---|
| `0x20e020320` (GFX PS) | `0x00000300` | target 0, actual 0 (GFX off) |
| `0x20e01c200` (control) | `0x80000000` | bit 31 set, all other bits 0 |
| `0x20e01c000` (state 0) | `0x00000000` | invalid entry (valid bit clear) |
| `0x20e01c010` (state 1) | `0x6436d063` | 365 MHz, vidx `0x64` |
| `0x20e01c020` (state 2) | `0x7024b021` | 450 MHz, vidx `0x70` |
| `0x20e01c030` (state 3) | `0x7027d031` | 500 MHz, vidx `0x70` |
| `0x20e01c040` (state 4) | `0x7f313061` | 550 MHz, vidx `0x7f` |
| `0x20e01c050` (state 5) | `0x6436d067` | 182.5 MHz |
| `0x20e01c060` (state 6) | `0x7024b023` | 225 MHz |
| `0x20e01c070` (state 7) | `0x7027d033` | 250 MHz |
| `0x20e01c080` (state 8) | `0x7f313063` | 275 MHz |
| `0x20e01c090`–`0f0` (9–15) | `0` | unused |

The frequency formula, fitted to all eight nonzero entries and the saved
ADT `perf-states`, is

    f = 24 MHz × fb[20:12] / (pre[8:4] × (post[3:0] + 1))

Every entry matches the ADT exactly. This corrects the iBoot/LLB note on one
point: states 9–15 read as zero here, they do not repeat an entry.

## What it shows

- The observed table matches the values LLB programs and iBoot reports in
  the ADT; bit 31 of the control word is set. This confirms the table contents
  and control value on this boot, not which perf state is selected.
- The control word has no bits set except bit 31. Its selection-field layout
  is unknown, so the word does not show that state 0 is selected.
- GFX was off during this read, so the snapshot does not say what the
  hardware selects once GFX is powered. A separate read after power-up would
  be needed to answer that.

## Offline search for the perf-state selector (same day)

A search of both kernelcaches found no kernel code that selects a GFX perf
state:

- The `sgx` ADT node maps no PMGR registers. It does carry
  `meta-sw-interrupt`, which names PMGR addresses `0x20e104010` and
  `0x20e104090`, and two platform functions, `clpc_enabled` (on `pmgr`)
  and `clpc_gpu_feedback` (on `clpc`).
- J81 PMGR `perf-domains` lists only SOC and CPU. The iOS 15 ApplePMGR GFX
  clock-generator helpers (`readGFXClkGenReg` and related) and the GFX perf
  domain are generic code for other SoCs, and nothing on J81 points them at
  this block.
- In 12B410, the only kernel reader of `perf-states`, `perf-state-count`
  and `meta-sw-interrupt` is `IOAcceleratorFamily2`, at
  `0xffffff8003285468`–`854ec` and `0xffffff8003287384`. It copies the
  (frequency, voltage) pairs into its own object (`+0x5d2c`, count at
  `+0x5dac`). These are DVFS tables for the GPU power controller or
  firmware, not register writes.
- A scan of the 12B410 prelinked text and kernel text, and of the whole
  19H422 image, for an `add #0x1c, lsl #12` or a `0x1c000`/`0x1c200`
  immediate found nothing relevant. This is a pattern scan, not a full
  audit: a base pointer plus a table offset would not show up in it.

Reading: on iOS the kernel probably never selects a GFX perf state itself.
The selection may be made later by GPU firmware or by hardware when GFX
powers on. This snapshot, taken with GFX off, does not establish the selected
state after power-up or explain the stalled ID read.

## What LLB and iBoot write in this block (offline, same day)

Every constant reference to `0x20e01c000`–`0x20e01dfff` in the decrypted
12B410 LLB and iBoot:

| Code | Access | Effect |
|---|---|---|
| LLB `0x180013adc` (called for states 0–15) | write `0x20e01c000 + n*0x10` and `+4` | Word 0 = `vidx<<24 \| valid<<21 \| fb<<12 \| pre<<4 \| post`. Bit 21 (valid) is set when `fb != 0`. Word `+4` gets one byte from the 20-byte entry (`+16`), probably the SRAM voltage index behind the ADT `perf-states-sram`. |
| LLB `0x180013020`–`13034` | RMW `0x20e01c200` | Sets bit 31 only. |
| LLB `0x180013fe4` (tunable batch) | write `0x20e01c300 = 0x40000001` | Unknown meaning. Written together with other SoC tunables. |
| LLB `0x180013818` (quiesce path) | write `0x20e01c200 = 0` | Clears the control word. |
| iBoot `0x87a0fcfb0`–`fd01c` | read `0x20e01c000 + n*0x10` | Builds the ADT `perf-states`. |
| iBoot `0x87a0fc5ec` (DIAGS/MONITOR quiesce only) | write `0x20e01c200 = 0` | Clears the control word. |

So no boot stage writes a state-select field. In `0x20e01c200` only bit 31
is ever written by software. Today's `0x80000000` is therefore exactly
LLB's value, and it says nothing about which state is selected. If a
selection field exists, it is set by hardware or by the GPU firmware.
Nothing that runs before the ID read writes one.

The decode of bit 21 explains the table: states 1–8 have it set, while state
0 and states 9–15 have zero words and are invalid entries, not 0 Hz states.

Two words in this block that LLB programs were not read today:
`0x20e01c300` (`0x40000001` from LLB) and the per-state `+4` words. They
are in the same 4 KiB page as the words already read, and they are LLB
outputs, not GPU registers. A read-only extension of the probe could read
them in the current boot (preflight `perf-peek` = GO).

## Next

1. Done above, inconclusive on its own.
2. Hardware: repeat this read once right after the guarded PMGR power-up
   (`0x3ff`), with no bridge, GPC or RGX access. The boot used here runs the
   original GPU-test kernel (`/sys/kernel/notes` sha256 `82ff70e8...`, the
   value the 20261106 bundle wrappers check), but its device tree is the
   MCC payload's. Tried 2026-11-08 18:5x: `insmod gpu-pmgr-once.ko` failed
   with `EINVAL` before any register access, because the GFX power-state
   node lacks the `experimental,j81-gpu-test-no-poweroff` guard property
   that the module requires. Nothing was powered, and a perf read right
   after showed unchanged values (PS `0x300`, control `0x80000000`). The
   check needs a boot of the `gpu-pmgr-once` payload (DFU).
   Done 2026-11-09, see below.

## After the guarded GFX power-up (2026-11-09)

DFU boot of `artifacts/live/gcroot-gpu-pmgr-once-payload` (palera1n +
`boot/load_m1n1.py`). `boot/j81_preflight.sh gpu-pmgr-once` returned GO at
49 s uptime: kernel notes `82ff70e8...`, DT guard present, module not
loaded, no consumer device. Staged files matched their expected sha256
(`gpu-pmgr-once.ko` `39d32b55...`, `gpu-pmgr-peek` `78349e4a...`,
`gpu-pmgr-once-run` `4fb50cd7...`, `gpu-pmgr-perf-peek` `eb446a66...`).

Sequence, one shell session: wrapper read GFX PS `0x300`, wrote
`power_once` once (`rc=0`), then the read-only perf peek, then a second PS
read. No bridge, GPC, MCC or RGX access.

| Register | GFX off (2026-11-08) | GFX on (2026-11-09) |
|---|---|---|
| `0x20e020320` (GFX PS) | `0x00000300` | `0x000003ff` (target 15, actual 15) |
| `0x20e01c200` (control) | `0x80000000` | `0x80000000` |
| `0x20e01c000`..`0x20e01c0f0` (states 0-15) | table above | identical, word for word |

The device stayed up and responsive afterwards; dmesg showed nothing new
except the module load.

What it shows: powering GFX changes none of the 17 words this probe reads.
The control word does not move when GFX turns on, so either the selected
state is not held in `0x20e01c200` or nothing selects one at power-up. This
read alone cannot tell those apart. `0x20e01c300` (`0x40000001` from LLB)
and the per-state `+4` words were read next, on the same boot.

### Remaining words, same boot, GFX still on

`boot/gpu-pmgr-perf-peek.c` now also reads each entry's `+4` word and
`0x20e01c300` (static aarch64 build sha256 `d2ef11e1...`; preflight
`perf-peek` GO at 568 s uptime, `gpu_pmgr_once` loaded, PS `0x3ff`).

| Register | Value |
|---|---|
| `0x20e01c004` (state 0 +4) | `0x00000000` |
| states 1, 2, 3 +4 | `0x00000070` |
| state 4 +4 | `0x00000080` |
| states 5, 6, 7 +4 | `0x00000070` |
| state 8 +4 | `0x00000080` |
| states 9-15 +4 | `0x00000000` |
| `0x20e01c300` | `0x40000001` (exactly LLB's value) |

The `+4` words repeat the same pattern for the full-rate states 1-4 and the
half-rate states 5-8, so they belong to the voltage/rate level, not to
selection. `0x20e01c300` holds the value LLB wrote. The device stayed up.

Result: every word in this PMGR block holds LLB's static setup, with GFX
both off and on. None of them records a selected perf state, so this block
does not show what the GPU clock is when the ID read stalls. The selection,
if any, lives elsewhere (GPU firmware, the CLPC/`meta-sw-interrupt` path
named in the `sgx` ADT node, or hardware not exposed here). This line of
reads is finished.

The stop rules in
[`2026-11-08-j81-next-mcc-experiment-decision.md`](2026-11-08-j81-next-mcc-experiment-decision.md)
still apply. No register was written.
