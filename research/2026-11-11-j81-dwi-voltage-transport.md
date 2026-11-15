# J81: DWI carries the rail voltage requests, and Linux gates it off (2026-11-11)

Live measurements on two Linux boots of the cycle payload, plus offline
decoding. Labels: **E** measured or read in source, **I** inference, **U**
unknown. Follows the
[perf-state control note](2026-11-10-j81-gfx-perf-ctl-after-gpc1.md).

No GPU core read, no page-5 write, no PMU write. The only hardware write was
the already used `dwi` power-state switch (`boot/pmgr-dwi-on.c`).

## Summary

1. PMGR pages 0 to 5 are PLL0 to PLL5; page 5 is the GFX PLL, driven by the
   GFX perf-state table (I, from E values). Page-5 `+4` bit 30 is its
   "enabled" status, the same bit the running PLLs 1, 3 and 4 show.
2. The four words at `0x20e023004..10` are the voltage manager's current
   rail codes. The CPU word and the SRAM word follow the CPU frequency (E).
3. The PMU (D2207) buck registers follow those words **only while the `dwi`
   power state is on** (E). DWI is therefore the transport for rail voltage
   requests, not only for the backlight.
4. Linux leaves `dwi` off. On our boots the CPU and SRAM rails are frozen at
   whatever was last sent before the gate closed, and the GFX state-1
   voltage request never reaches the PMU (E on the boot sampled).
5. The DWI block's two configuration words are intact on Linux (E), so
   switching the power state on is enough to make the transport work.
6. Linux itself switches `dwi` off about 0.7 s into the boot, together with
   nineteen other domains that the boot chain hands over switched on (E).
7. Open: with DWI on before the request, an earlier run still found the GFX
   PLL off. That run did not read the PMU, so it is not known whether the GPU
   buck took the new code. That, with the other nineteen domains restored,
   is the next test.

## PLL pages (boot of 2026-11-11 11:21 UTC, after GPC state 1, `dwi` on)

| PLL | `+0` | `+4` | `+8` | `+0x18` | Reading |
|---|---|---|---|---|---|
| 0 | `0x00001010` | `0x80000001` | `0x80480348` | `0x1` | external bypass |
| 1 | `0x80085040` | `0x40000000` | `0x80480348` | `0x04000040` | running |
| 2 | `0x00001010` | `0x80000001` | `0x80480348` | `0x1` | external bypass |
| 3 | `0x8003201b` | `0x40000000` | `0x80480348` | `0x04000040` | running |
| 4 | `0x80032010` | `0x40000000` | `0x88480348` | `0x04000040` | running |
| 5 | `0x00001010` | `0x00000000` | `0x81480348` | `0x1` | neither running nor bypassed |

`+0xc`, `+0x10`, `+0x14` are identical on all six (`0x081c8385`,
`0x01ac0418`, `0x02187000`). Bit 0 of `+4` is the external-bypass request,
bit 31 "bypass active", bit 30 "PLL output active" (I, from the pattern
above and the LLB sequence that clears bit 0 and waits). iPadOS reads
`+0 = 0x1010`, `+4 = 0x40000000`, `+8 = 0x81480348` on page 5 after the GPC
poll ([capture results](2026-11-10-j81-page5-capture-results.md)), so on a
working system the perf-state logic runs the PLL without changing `+0`.

The GFX table entry decodes as voltage code `[31:24]`, PLL enable `[21]`,
feedback `[20:12]`, pre-divider `[8:4]`, post-divider `[3:0]`
([live table](2026-11-08-j81-gfx-perf-state-live-read.md)). State 1 is
`0x6436d063`: code `0x64`, enable set, 365 MHz. The second word `0x70` is the
SRAM code. The code-to-voltage rule `600 mV + 3.125 mV * code` gives 912.5 mV
for `0x64`, the ADT's 912 mV for state 1 (I).

## Voltage manager words

`0x20e023000 = 1` (control) and `0x23014..0x23020 = 0xbb81ac05` (delays,
written by LLB) on both boots. The four words in between, sampled with the
read-only [`pmgr-words-peek`](../boot/pmgr-words-peek.c) while the cpufreq
governor was switched through `powersave`, `schedutil` and `performance`:

| Word | Values seen | Reading |
|---|---|---|
| `0x23010` | `0x16d`, `0x188`, `0x19c` | CPU rail code; `0x19c` at 1512 MHz |
| `0x23004` | `0x170`, `0x180` | SRAM rail code; `0x180` at 1512 MHz |
| `0x2300c` | `0x164` (constant) | GFX rail code, equals the state-1 table code `0x64` |
| `0x23008` | `0x000` (constant) | unused channel on this board (I) |

Bit 8 is set in every used word (meaning U). The GFX word was sampled only
after a GPC state-1 request; its value before a request has not been read
yet (U), so "the request sets it to `0x164`" is still an inference.

## PMU buck registers versus the `dwi` power state

Read-only `i2ctransfer -f -y 0 w2@0x3c <hi> <lo> r8` on the PMU. The buck
blocks sit at `0x0100 + n*0x28`; byte 0 and byte 2 hold a voltage code
(requested and actual, I), bytes 4 and 5 look like minimum and maximum codes.

Boot `288eb570` (another campaign had already requested GPC state 1 with
`dwi` off), `dwi` power state `0x200`:

| Governor | `0x23010` / `0x23004` | Buck 0 (`0x0100`) | Buck 5 (`0x01c8`) | Buck 1 (`0x0128`) |
|---|---|---|---|---|
| schedutil | `0x19c` / `0x170` | `9c .. 9c` | `80 .. 80` | `00 .. 40` |
| powersave, 300 MHz | `0x16d` / `0x170` | `9c .. 9c` | `80 .. 80` | `00 .. 40` |
| performance, 1512 MHz | `0x19c` / `0x180` | `9c .. 9c` | `80 .. 80` | `00 .. 40` |

Same boot after `pmgr-dwi-on` (`0x200` to `0xff`, first poll):

| Governor | `0x23010` / `0x23004` | Buck 0 | Buck 5 | Buck 1 |
|---|---|---|---|---|
| schedutil | `0x16d` / `0x170` | `6d .. 6d` | `70 .. 70` | `00 .. 40` |
| powersave (read while the tool ran at a higher state) | `0x188` / `0x170` | `88 .. 88` | `70 .. 70` | `00 .. 40` |
| performance | `0x19c` / `0x180` | `9c .. 9c` | `80 .. 80` | `00 .. 40` |

With `dwi` off the PMU keeps `0x9c` and `0x80` whatever the voltage manager
asks for. With `dwi` on, buck 0 follows the CPU word and buck 5 follows the
SRAM word exactly (E). Buck 0 is the CPU rail, buck 5 the SRAM rail (I).
Bucks 0, 1 and 5 share a maximum byte of `0xe0`, the others have `0xff`;
buck 1 is the remaining candidate for the GPU rail (I). It stays at code
`0x00` with "actual" `0x40` (its minimum byte is `0x40`, 800 mV by the same
rule) although the voltage manager's GFX word says `0x64`: the state-1
request on this boot was issued while `dwi` was off and was never resent (I).

The DWI block's own words on the earlier boot (read only while its power
state was on): `0x20e200000 = 0x00000001`, `0x20e200004 = 0x0000003c`. These
are the values LLB's `dwi_init` computes for a 24 MHz clock (E for both, I
for the match). The configuration survives our boot path; only the power
state is off.

## Who switches `dwi` off: Linux, 0.7 s into the boot

LLB keeps the `dwi` power state on when it quiesces (E, keep mask) and
iPadOS has it on (E). On Linux the genpd debugfs entry for `dwi` shows
`active_time` 688 ms and no consumer device, with the domain off for the rest
of the uptime (E). So the domain is on when Linux starts and Linux itself
switches it off at about the late-initcall stage, although `pd_ignore_unused`
is on the command line and the kernel prints "Not disabling unused power
domains" (E). The per-provider `sync_state` path is the likely actor (I, not
checked in the pinned source; the log line `power-controller@20198:
sync_state() pending due to 20a08c000.spi` shows that path is active).

The same accounting (about 685 ms active, then off) marks twenty domains
that the boot chain hands over switched on and Linux switches off:

    dwi, i2c1, i2c2, i2c3, uart1, uart2, uart4, uart6, uart7, uart8,
    ispsens0, ispsens1, usb2host0, usb2host1, usb2host2, disp1_busmux,
    isp, media, venc, pcie_aux

Twenty-four other domains were never on in this boot (`active_time` 0).
Whether iPadOS still has the twenty on when the GPU starts is known only for
`dwi` (on). This list is the concrete form of "the Linux power-state picture
differs from the one the GPU is started in on iPadOS", and it is testable:
[`boot/pmgr-ps-restore.c`](../boot/pmgr-ps-restore.c) switches named domains
from exactly this list back on, one acknowledged write each, the same write
`pmgr-dwi-on` uses (host test `boot/test_pmgr_ps_restore.py`). Not run.

Side effect worth fixing whatever the GPU outcome: with `dwi` off the CPU
and SRAM rails do not follow frequency changes. The frozen CPU code `0x9c`
is the 1512 MHz code, consistent with the gate closing while the kernel was
busy booting at full speed (I). Frozen at the top code this only wastes
power; frozen at a lower code it would undervolt the CPU at 1512 MHz. The
`dwi` domain should be kept on (for example `apple,always-on` in the J81
device tree); not built or tested yet.

## What this does and does not say about the GPU

- On every Linux GPU test so far except one, the GFX state-1 voltage request
  cannot have reached the PMU (I, from `dwi` off at Linux entry). The GPU rail
  then sits at its 800 mV floor while the GPC reports state 1.
- The one "`dwi` on first" run
  ([result](2026-11-10-j81-gfx-perf-ctl-after-gpc1.md)) still read page-5 `+4`
  as zero, both under 750 ns after the poll and minutes later. So a working
  transport alone has not been shown to start the PLL. That run did not read
  buck 1, did not sample the bit between 1 µs and minutes, and came before the
  transport was known to work.
- The GPC poll completes about 300 µs after the request on Linux. The LLB
  delay word `0xbb81ac05` has fields 5, 107 and 3000; a ramp of 100 code steps
  plus a fixed part of that order is plausible (I, weak). The local
  [iOS timing probe](probes/j81-gpc-timing/README.md) on `main` would give the
  iPadOS figure.

## Review of the parallel work on `main` (same day)

- The [iOS timing result](2026-11-11-j81-ios-gpc-timing-result.md) gives
  about 289 µs from the state request to the end of the poll on iPadOS (if
  the timebase is 24 MHz), against 291 to 306 µs on Linux, whose poll loop
  sleeps 10 to 20 µs between loads and so can only be late. The request takes
  the same time on both systems (E, one sample each). On iPadOS the PLL bit
  is already set at the first read after the poll, so the PLL start lies
  inside that interval; the Linux zero right after the poll is then a real
  difference and not a sample taken too early (I). One arithmetic fit, weak:
  the delay word's top field 3000 counted at 12 MHz is 250 µs, and the PLL
  lock time `0x348` at 24 MHz is 35 µs, together 285 µs.
- The [DWI review](2026-11-11-j81-claude-dwi-review.md) said that DWI was
  only shown to be a backlight path and that a GPU-rail use was not
  established. The buck measurements above settle the general point: DWI
  carries the CPU and SRAM rail codes. For the GPU rail it is still an
  inference until buck 1 is read after a request made with `dwi` on. Its
  point that `pmgr-words-peek` is not a safe scanner is taken, and the PMU
  dump side effect below is the same lesson.
- The [selector-10 readback](2026-11-11-j81-bridge10-readback-result.md)
  and the tuner captures do not bear on the voltage path.

## Caution about PMU dumps

The full `0x0000..0x04ff` read cleared the latched bytes at `0x002d`,
`0x0040`, `0x0041`, `0x0050`, `0x0052`, `0x0053` and `0x005a` (non-zero in the
first dump, zero in the second). They are clear-on-read event registers (I).
No Linux driver here consumes them, but a "read-only" PMU dump is not free of
side effects. Read only the buck rows (`0x0100`, `0x0128`, `0x0150`, `0x01c8`)
in future runs. The 2026-09-08 dump had the same effect.

## Next test (fresh cycle-payload boot)

Steps 1 to 3 and 5 to 6 are of kinds already run. Step 4 has two variants;
the wider one writes power-state words that have not been written from
Linux userspace before and needs a go-ahead.

1. `boot/j81_preflight.sh gpc-page5-kpoll` must say GO.
2. Stage `pmgr-words-peek` (sha256 `b58d2ada...`), `i2ctransfer`
   (`4d030c81...`) and the power-state tool; check each hash on the device.
3. Baseline, read-only: PMGR `20120 23004 23008 2300c 23010 5000 5004 5008
   5018 1c200`, PMU rows `0x0100 0x0128 0x0150 0x01c8`. This gives the GFX
   voltage word before any request.
4. Either `pmgr-dwi-on` alone, or `pmgr-ps-restore` with the whole list
   above (recommended: the `dwi`-only variant already failed to start the PLL
   once, and the wide variant still answers the buck question). Preflight
   again; PMU rows again to confirm buck 0 now follows the CPU word.
5. kpoll campaign in `paired` mode (page-5 `+4` right after the poll and
   about 100 µs later).
6. Repeat step 3 at once and about 10 s later.

Reading: the PLL bit set means one of the restored domains (or the timing of
the read) was the missing piece, and the list can be halved on later boots.
Buck 1 at `0x64` with the PLL still off means neither the rail voltage nor
these domains hold the PLL back. Buck 1 still at `0x00` means the PMU does
not accept the GFX code (PMU-side setup that iPadOS does and we do not).

## Prepared, not run

`pmgr-ps-restore` static aarch64 build, sha256
`90474674554b3e3abac9f15e3d5d189b43a8a816feddf97dacdb8a32286f1d18`, private
bundle with a staging file `artifacts/live/private/j81-pmgr-ps-restore-bundle-v1/`
on the Mac. This build is **not** the Nix build: the shared builder refused
to start because the Mac had 12 GB free (15 GB required), so it was compiled
with `zig cc -target aarch64-linux-musl -static -O2 -s` (zig 0.17.1) on two
machines, which gave the same hash. The flake attribute
`pmgr-ps-restore-static` is the reproducible record once the builder is
available again.

Dry run on boot `288eb570` (E): no arguments and a name outside the list
both exit 2 before `/dev/mem` is opened; with all twenty names and `READ`
then a refused write it printed the current words (`dwi` `0xff`, the others
off) and exited 1 without writing.

Captures (private): `artifacts/live/gpu/pmgr-words-20261111-dwi-config/` and
`artifacts/live/gpu/pmgr-words-20261111-boot288e-after-bridge10/` on the Mac.

## Review on 2026-11-15: what the follow-up runs settled

This section reviews work done by others after this note was written. Sources:
branch `j81-dwi-gpu-compare` (41 commits on top of this branch, no pull
request yet) and branch `claude/project-thread-gb81y1` (PR #39). Two of the
result notes were checked against their private raw logs on the Mac
(`artifacts/live/gpu/dwi-gpu-compare-20261111-01/` and
`wide-power-20261111-01/`); the values in the notes match the logs. No device
access was made for this review.

### The questions this note left open

| Question | Answer | Run |
| --- | --- | --- |
| Does the PMU row `0x0128` take the GFX code when the request is made with DWI on? | Yes. Bytes 0/2 go from `00`/`40` to `64`/`64` after the GPC request. | DWI-first, 2026-11-11; repeated in the 20-domain run |
| Does that start the GFX PLL? | No. Page 5 `+4` stays `0` and `+0x18` stays `0x1`. | Same runs |
| Does restoring all 20 domains help? | No. Bit 30 stays clear, and a core-ID read Martin authorised afterwards did not return. The iPad rebooted into iPadOS. | 20-domain run and core read, 2026-11-11 |
| Does holding DWI on from boot help? | No. The power-off callback at 0.75 s was rejected, DWI stayed `0xff`, bit 30 stayed clear. | Early hold, 2026-11-13 |
| Does iPadOS see the same `0x2300c` values? | Yes, `0` before and `0x164` after. | iPadOS rail compare, 2026-11-12 |

So the transport described in this note is confirmed, and it is **not** the
missing step. The row `0x0128` now follows the GFX request in three boots,
which supports reading it as the GPU rail; it is still not a measured voltage.
The pending test in "Next test" above is done and the decision asked of
Martin is withdrawn. `boot/pmgr-ps-restore.c` was not used; the 20-domain run
used its own supervised tool.

Still worth doing independently of the GPU: Linux switches DWI off at about
0.75 s in every boot (seen directly in the instrumented control boot), which
freezes the CPU and SRAM rails. Keeping `ps_dwi` on in the J81 device tree
fixes that. Orchard's S8000 and T7000-handheld trees get the same effect from
their `dwi_bl` node.

### The bisection result and two qualifications

The real progress is PR #39: with the unchanged recipe run at the end of
iPadOS `ApplePMGR::start()`, bit 30 sets and the core ID reads `0x00070500`.
The recipe is therefore sufficient, and what Linux lacks (or breaks) is
decided before any GPU, CLPC or tuner code runs. Two points need care.

1. **The PongoOS run failed for a reason Linux does not have.** In PongoOS
   the voltage manager is disabled (`0x23000 = 0xf01`) and `0x2300c` stayed
   `0`, so the GFX voltage request was never issued. On Linux it is enabled
   and the request reaches the PMU. The PongoOS run therefore shows that the
   pre-OS state is not enough. It does not show that m1n1 and Linux are
   harmless. Two readings remain: (A) XNU does a further step that Linux
   lacks; (B) enabling the voltage manager is the only missing step from the
   pre-OS state, and something in m1n1 or Linux then stops the PLL.
2. **The entry-hook run is likely to repeat the PongoOS result.** At the
   entry of `ApplePMGR::start()` the voltage manager is probably still
   `0xf01`, because `start()` itself enables it (it read `1` at the end). If
   so, bit 30 will stay clear and `V1` will stay `0`, for the same reason as
   in PongoOS, and the conclusion "the step is inside `start()`" would be one
   we already have. The bit-30 gate keeps that outcome safe. The first log
   line tells which case it is: `V0=00000f01` means this prediction holds.

### A test that separates (A) from (B)

Run the recipe from the pre-OS state with one addition, the voltage-manager
enable done the way iPadOS does it: write the CPU and SRAM codes for the
current CPU state to `0x23010` and `0x23004` first, then clear bits 11:8 of
`0x23000`. Either the PongoOS script or the entry-hook probe can carry it.

- Bit 30 sets: reading (B). The search moves to m1n1 and Linux, where every
  step is a fast toggle and no iPadOS boot is needed.
- Bit 30 stays clear: reading (A). The step is another write inside
  `start()`. A read-only snapshot of the PMGR words at the entry and at the
  end of `start()` then lists what changed, without tracing the code.

Risk to settle before any run: clearing bits 11:8 while the CPU code is `0`
and DWI is on would ask the PMU for the lowest CPU voltage. The codes must be
seeded first, and the right values for the pre-OS CPU state are not yet
established (Linux at its top state uses `0x19c` and `0x180`). This is a new
hardware write and needs Martin's go-ahead. Nothing here has been built or
run.
