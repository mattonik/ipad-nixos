# J81 GPU: strategy reset (2026-11-14)

Read-and-think review. No device access, no boot, no new MMIO. Sources: every
GPU note on `main` (`583540b`), the unmerged `j81-dwi-gpu-compare` branch
(`3a5d7f9`), the local-only `j81-gpu-assessment-20261114` branch (`b87cf0c`,
including its own `research/2026-11-14-j81-gpu-assessment.md` from the same
morning), the Orchard J96 and J81 field reports, and the public A9 GPU
repository ([brkosebay/a9-gpu-research](https://github.com/brkosebay/a9-gpu-research)
at `a20e507`).

## 1. Short answer

We are going in circles because, since about 2026-11-09, every experiment has
asked the same question one word at a time: *which single register does
Linux have different from iPadOS at the GPC request?* Each answer has been
"this one matches too". The method cannot converge, because the hypothesis
space (any register, any agent, any time since power-on) is unbounded and
each boot removes one point from it.

The way out is to **bisect instead of compare**. The two boot paths share
everything up to PongoOS, then split into XNU + Apple kexts on one side and
m1n1 + Linux on the other. One test at the fork point tells us which half the
missing step lives in, and each later test halves it again. That needs a few
boots, not dozens.

Also, the premise "chips before and after work, ours doesn't" is only half
right. See section 3: nobody has a Linux GPU on **A7 or A8** at all, and the
one other A8 attempt (J96, iPad mini 4) hit our exact hang independently.

## 2. What has been tried (one paragraph per area)

**Power and bridges.** GFX PMGR power cycle reaches `0x3ff`. All 66
selector-9/10 bridge stores match iPadOS's GFX-thread writes in order and
value (only `+0x18` read back). Restoring the 20 domains Linux turns off at
0.7 s (DWI, I2C, UART, USB2HOST, DISP1_BUSMUX, ISP, …) did not help, and the
core-ID read after it still hung (2026-11-11). DISP0/DISP_BUSMUX match iPadOS
(2026-11-13).

**GPC (Fender).** The three writes (`+0x10000=0xffff0000`, `+0=0x40000000`,
`+0x1000=0x11`), poll and 10 µs wait match Apple and match what makes the A9
ID read succeed. GPC reaches state 1 on Linux every time.

**Perf state, voltage, DWI.** The PMGR GFX perf block is static LLB setup and
matches iPadOS, including `0x20e01c200 = 0x80110100` after the request. The
voltage-manager word `0x2300c` goes `0 → 0x164` on both. With DWI held on
from early boot, the candidate PMU buck row follows to `0x64`. None of this
changed page 5.

**Page-5 bit 30.** `0x20e005004` bit 30 is the one known difference: set on
iPadOS after the GPC poll, clear on Linux at every sample (10 busy polls, the
success poll, +100 µs, hours later). On iPadOS it is clear before the first
poll and set after it; waiting before the request does not set it; two traced
32-bit PMGR store sites and the 64-bit writer show no software write. All of
this points to a hardware status bit, most likely "GFX PLL (PLL5) output
running", which the perf-state engine raises on its own.

**Ruled out by evidence:** perf block, GFX PS changes, DWI (both orders and
early hold), 20-domain restore, display domains, `0x2300c`, MCC selector
patterns, kdebug codes `0x2700c00x`, `bcc56c`/`hw-dpe-reg`, the 64-bit
region-8 writer. **Not tested:** the PMGR clock/divider/mux region outside
pages 0-5, the GPC block beyond its three words, anything XNU does at boot
before the GPU provider runs, and whether any Linux/m1n1 action is harmful.

### What the bit-30 work actually tells us

Read together, the results say: the GPC request reaches PMGR on both systems,
but on Linux the GFX PLL never starts, so the core has no clock and the first
R0 read gets no bus response. That is a useful conclusion, not a dead end.
But the bit is the **symptom**. Chasing *who writes it* cannot succeed if
nobody writes it. The real question is *what interlock stops PLL5 on Linux*,
and the comparisons so far only looked at the GPU's own path.

## 3. What other chips did differently

| Chip | GPU | Linux GPU status | How the core became reachable |
| --- | --- | --- | --- |
| A5 (Cascadia) | SGX543 | Works | Pre-Rogue SGX, 32-bit SoC, different PMGR. Not transferable. |
| A7 (iPhone 5s) | G6430 | **Nobody** | No public attempt. Our own iPhone 5s port is paused. |
| A8 (J96, iPad mini 4) | GX6450 | **Same hang as J81** | Orchard J96 report: GFX PS on/off clean, Fender accepted iPadOS's sequence, GPC state 1, first `0x201000020` read hung "every time". |
| A8X (J81, us) | GXA6850 | Same hang | — |
| A9 (J71t) | G5P | Works, Mesa, desktop | PMGR GFX on, then the same three Fender writes, poll, 10 µs. That alone made `R0+0x20` return `0x00090f00`. Their bridge replay (37 words) was tested later and made **no** difference: bridges are AXI2AF port config, not clocks or resets. |
| A10 (Orchard) | G9P | Works | Different design: GPU firmware on an RTKit IOP behind `gfx-kf`, Fender PS register. |

Projects people sometimes cite do not help here: Project Sandcastle (A10
Android) and Corellium's virtual devices never had GPU acceleration, and the
checkra1n-era Linux trees stop at basic boot.

So the honest picture is: **the A9 recipe is ours, and it works on A9 but not
on A7/A8**. The A9 team found nothing extra to do because there was nothing
extra on their chip. Two independent A8-family devices failing identically,
on two different kernel trees, points to a generation difference between the
T7000-family PMGR (`pmgr1,t7001`, separate GFX perf engine and PLL5) and the
S8000 PMGR. It is not a bug in our test code and not J81-specific.

The A9 work still gives us two things we can use: Apple's accessibility rule
(PMGR GFX on, GPC state in range, `R1+0` bit 29 clear; we satisfy all three),
and everything after the ID read (reset FIFO, LDR loading, rings). Those
transfer only once the core answers.

## 4. New directions, ranked

Each entry has its cost and the offline check that confirms it or kills it
before any boot.

### 1. Fork-point test: run the GPU sequence in PongoOS, before any OS

**Idea.** Both iPadOS (palera1n `--override-kpf`) and Linux
(`--override-pongo`) pass through PongoOS. Do the known Linux sequence (GFX
PS on, 66 bridge stores, GPC wake, then the ID read) from PongoOS, before XNU
or m1n1 runs.

- **Read succeeds:** something in m1n1 or Linux breaks the GPU. Bisect that
  side next (m1n1 without `cpufreq_init`, Linux with initcalls blacklisted).
  Both are fast bootarg or payload toggles.
- **Read hangs:** XNU does something at boot that Linux does not, outside the
  GPU's own path. Go to direction 2. We would also stop auditing m1n1 and
  Linux for harmful writes.

Either result halves the search space. PongoOS is also the safest place for a
hang: no filesystem is mounted, and recovery is DFU.

- **Cost:** one small KPF-style Pongo module (the probe build system in
  `research/probes/` and the `make KPF_CFLAGS=… checkra1n-kpf-pongo` flow
  already exist), host tests, and one boot.
- **Offline check first:** confirm that Pongo's MMU maps `0x20e000000`,
  `0x201000000`, `0x201e00000` and `0x201f00000` as device memory at
  module time. Confirm that palera1n's bundled Pongo and our pinned
  `2.6.3-bb492b0` (`Pongo.bin`) do the same pre-fork work: the
  [pre-Linux audit](2026-11-09-j81-pongo-m1n1-pre-linux-writes.md) covers only
  the pinned one. Decide what the module does if the read hangs. An internal
  watchdog cannot help, so the log must be sent out over USB before the read.

### 2. Bisect XNU's boot on iPadOS, using the existing KPF hooks

Only if direction 1 hangs. Instead of adding more observers to the working
GPU path, take a raw "Linux recipe" ID read, the same code as direction 1,
and run it at earlier and earlier points of a normal iPadOS boot:

- (a) as the GPU provider starts, but with our own raw accesses instead of
  Apple's: this checks the *how* (mapping, width, which CPU), not the *what*;
- (b) right after ApplePMGR/AppleT7001PMGR `start()`;
- (c) right after the CLPC / AppleARMPlatform performance-controller start;
- (d) early in IOKit matching.

The first point where the raw read works brackets the missing step between
two named kexts. That is about 3-4 boots for a well-defined answer, against
an open-ended number for word comparisons. A hang here is an iPadOS hang and
reboot, as in earlier probe boots.

- **Cost:** 3-4 temporary iPadOS boots, each needing a new hook site.
- **Offline check:** find hookable, exact-build (19H394) sites for (b)-(d)
  in the kernelcache. Then, statically, list what ApplePMGR `start()` and the
  T7001 performance-controller start write in PMGR outside the per-device PS
  words: clock muxes and dividers, PLL pages 0-5, `0x1c000`/`0x23000`, and any
  "soc perf state" or fabric/MCC frequency setup. Earlier tracing covered only
  the GPU provider's path. This list alone may name a candidate.

### 3. One wide, read-only PMGR snapshot on both systems

Replace the one-word comparisons with a single snapshot of a vetted PMGR
allowlist, taken at the same point (before the GPC request) on iPadOS and on
Linux: PLL pages 0-5 (all words), the clock/divider/mux region, the perf
blocks, the voltage manager, and the PS words `0x20000-0x20400`. A diff of a
few hundred words either names a candidate or rules out the whole class
"a static PMGR register differs" in two boots.

- **Cost:** one iPadOS probe boot plus one Linux boot. The capture code is
  mostly the existing `pmgr-words-peek` and page-5 probes.
- **Offline check:** build the allowlist from the ADT (`ps-regs`, `clocks`,
  `device-clocks`, PLL page layout) and the 19H394 PMGR read sites. Exclude
  anything Apple never reads, because read side effects are unknown. The
  existing 2026-11-11 iOS "wide/matrix" captures may already cover part of
  this; check them before building anything.

This is cheaper than direction 2 but weaker: it only finds differences that
show up as static register values. It can run in parallel with direction 1.

### 4. Pool effort with the J96 (A8) work

The J96 report reached our hang independently, with a different kernel tree
and m1n1 build. That makes it a free control. If the J96 author has iPadOS
captures of page 5 or PLL state, or tried anything we have not, that is
evidence at zero boot cost.

- **Cost:** a message or an issue. The decision is Martin's; nothing is sent
  without his go-ahead.
- **Offline check:** read the full J96 report and its branch for GPU notes
  beyond the one table row.

### 5. Warm handoff from iPadOS (keep as the fallback)

Already researched in `research/2026-11-12-j81-warm-handoff-feasibility.md`
(on the `j81-dwi-gpu-compare` branch):
get to Linux with iPadOS's GPU state still in place. It would get around the
whole problem, but there is no existing XNU-to-Linux path for 15.8.5, sleep
may reset the GPU, and data safety is unproven. This is weeks of work. Keep
it in reserve in case directions 1-3 end in "something XNU does that we
cannot find".

### Deliberately not recommended

- More bit-30 timing, writer-attribution or single-word iOS/Linux samples.
  The bit is now well characterized as status. Another sample changes no
  decision.
- Writing page 5 or PLL5 directly, guessing PLL settings, or repeating the
  core-ID read on Linux without a new prerequisite.
- Skipping the ID read. Every later step (reset FIFO, firmware boot, rings)
  also needs a clocked core, so this would only move the hang.
- Porting A9 or A10 firmware paths now. They become useful once R0 answers.
- Upstream Imagination's open 6XT (GX6250) support. It is worth a look later
  for BVNC and META-firmware structure, but it says nothing about Apple's
  PMGR.

## 5. Suggested order

1. Offline (no boots): direction 1's Pongo MMIO-mapping and Pongo-version
   checks, direction 2's static list of PMGR `start()` writes, and direction
   3's allowlist and existing-capture check. Read the J96 branch.
2. One boot: the Pongo fork-point test. Run `boot/j81_preflight.sh` only for
   any later Linux leg; the Pongo leg needs its own written GO/NO-GO checklist,
   because preflight does not cover a Pongo module.
3. Then either the m1n1/Linux bisection (fast toggles) or 3-4 iPadOS bisection
   boots, depending on the result.

No test in this note has been built or run.
