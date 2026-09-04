# T7001 PongoOS-to-Linux Handoff: Prior Art and Next-Step Candidates

Research conducted September 2026, after six PongoOS builds (five run on hardware)
failed to produce a confirmed Linux boot on the iPad Air 2 (A8X/T7001). See
[`docs/project-status.md`](../docs/project-status.md) for the full attempt-by-attempt
log; this document covers what was found by looking outside this repository, and
ranks concrete next steps by how directly they're evidenced.

## The problem, in one paragraph

Every real `linux_t7001` handoff attempt (5 hardware runs) produces the identical
symptom: PongoOS accepts the command, prints its normal prep-boot messages, then
goes silent and stops responding to USB, with no visible sign the CPU ever executed
our staged code. A safe, no-jump sanity test (`t7001_color_test`) confirmed the
marker's framebuffer-writing logic and color assumptions are correct. A safe,
read-only check (`t7001_sram_check`) confirmed this device's `jump_to_image` SRAM
release path was never the issue (`need_to_release_L3_SRAM=0x69`, not the `0x41`
that would trigger it). What's left is something in the actual jump/teardown
mechanics or CPU state that isn't observable through the framebuffer alone.

## Prior art found

### konradybcio/pongoOS + konradybcio/linux-apple — the load-bearing find

In June 2022, Konrad Dybcio and Markuss Broks got mainline Linux booting on Apple
A7/A8/A8X devices via PongoOS — **explicitly including the iPad Air 2 (T7001)**,
confirmed by a dedicated `src/drivers/plat/t7001.c` in their fork naming
`"Apple A8X (T7001)"`. This is not a loosely related project; it is a working
implementation of the exact thing this repo is trying to do, on the exact chip.

- Fork: <https://github.com/konradybcio/pongoOS>
- Kernel fork: <https://github.com/konradybcio/linux-apple>
- Coverage: [Hackaday](https://hackaday.com/2022/06/12/boot-mainline-linux-on-apple-a7-a8-and-a8x-devices/),
  [Liliputing](https://liliputing.com/now-you-can-boot-linux-on-apple-devices-with-a7-and-a8-series-chips/)
- Konrad's own writeup was linked from multiple sources as `konradybcio.pl/linuxona7/`
  but returned HTTP 404 at the time of this research (may have moved or been taken
  down) — the Hackaday summary is the best available secondary source on the
  debugging story itself.

The Hackaday summary of their debugging journey is worth restating because it's a
close match for where this project is stuck: they were blocked for **over a year**
by an MMU-enablement issue, had only framebuffer access to debug with (same
constraint as us), improvised a technique of **printing register values as
scannable barcodes on screen** to get data off the device without a serial console,
and the actual breakthrough was **"a single line difference"** between their
attempt and a known-working reference. That last detail is the strongest argument
for treating their source as ground truth to diff against rather than reasoning
about ARM64/SoC internals from first principles again.

### Concrete architectural differences vs. this repo's patch

Cloned and read directly (`src/modules/linux/linux.c`, `src/kernel/entry.c`,
`src/boot/jump_to_image.S`, `src/boot/stage3.c`). Three differences stand out:

**1. Fixed physical entry point, not a dynamically allocated one.** Their
`linux_prep_boot()` sets:

```c
/*
 * This is a really hacky guesstimate, but it works on all devices..
 * The main issue with the entrypoint is that we need a contiguous
 * region where we can stuff like >30 megabytes worth of Linux. A good
 * place to do so is before or after SEPFW. But it doesn't really matter
 * as long as it works..
 */
gEntryPoint = (void *)0x803000000;
```

That comment says outright this constant was chosen empirically and validated
across their whole A7–A11 device range, T7001 included. This repo's patch instead
computes the kernel's physical address from wherever `alloc_contig()` happens to
place it — a heap allocation, not a deliberately chosen safe region relative to
firmware-reserved memory (they explicitly reserve the ADT's `SEPFW` region in the
DTB before choosing where to place things). If `alloc_contig()`'s result lands
somewhere that isn't actually safe to execute from post-teardown — overlapping a
firmware-reserved range, or a region with different cache/MMU treatment — that
would produce exactly the observed symptom (silent hang, no output) independent of
everything already ruled out.

**2. Linux boot is routed through the same path as XNU boot, not a custom
`jump_to_image` call.** Their `pongo_entry()`:

```c
else if(gBootFlag == BOOT_FLAG_LINUX)
{
    linux_boot();  // just does memcpy(gEntryPoint, gLinuxStage, gLinuxStageSize)
}
else
{
    tz_lockdown();
    xnu_boot();
}
exit_to_el1_image((void*)gBootArgs, gEntryPoint);
```

There is no Linux-specific jump call at all. `linux_boot()` only stages the
kernel at the fixed address; the actual exit happens through the identical
`exit_to_el1_image()` used for every other boot type — the same mechanism proven
to work for real XNU/jailbreak boot on this exact device, since that's what
`checkra1n`/`palera1n` exercise every time this project's docs record a successful
jailbreak step. This repo's patch instead calls `jump_to_image()` directly from
inside the `BOOT_FLAG_LINUX` branch, with a hand-picked `tramp` argument, bypassing
`exit_to_el1_image()`/`stage3_exit_to_el1_image()` entirely. That wrapper does more
than call `jump_to_image` — it stages arguments through BSS-safe globals and
branches between "kernel" and "hypervisor" continuation modes based on a flag in
`boot_args`. Skipping it means skipping whatever of that turns out to matter.

**3. Their `jump_to_image` is a simpler 2-argument function with no
SRAM/tramp release mechanism at all** — confirming, independently of this
project's own `t7001_sram_check` result, that the SRAM-release complexity in the
version of PongoOS this repo forked from is not what makes T7001 boot work. Their
barrier sequence (`isb; dsb sy; ic iallu; dsb sy; isb`) is functionally the same
category of instructions as the "raw" path this repo's `jump_to_image` already
takes on this hardware. **This deprioritizes the "missing `cache_clean()` before
the jump" theory** recorded in `docs/project-status.md` Step 3 — their working
`linux_boot()` doesn't call `cache_clean()` on the staged kernel either, and it
works, so that gap is very unlikely to be the actual blocker.

**4. Their `linux_prep_boot()` has the identical `pixfmt0`/color-matrix register
poke** this repo already traced the reddish-flash artifact to. Finding the exact
same code in a working reference implementation is strong independent confirmation
that artifact really is benign and unrelated to boot success, not something to
keep chasing.

### Other projects checked, lower relevance

- **postmarketOS wiki** (`wiki.postmarketos.org`): the iPad Air 2 device page is
  behind an Anubis anti-bot challenge that blocked automated fetching during this
  research; worth checking manually in a browser. Search results independently
  confirm postmarketOS has run on the iPad Air 2 using the Dybcio/Broks work above,
  with netboot for the mainline kernel — consistent with, not additional to, the
  konradybcio fork findings.
- **A11pwnX/Linux-iPhone-6s-X-howto**: a community packaging of the same
  konradybcio work, but scoped to A9–A11 devices (iPhone 6s through X) — does not
  cover A8X specifically, though its README credits `konradybcio/linux-apple` and
  `konradybcio/pongoOS` as the source, corroborating those as the canonical
  references.
- **Project Sandcastle** (Android on iPhone 7, A10): predates and is credited as
  groundwork for the Dybcio/Broks A7/A8/A8X work, but targets a different,
  already-supported chip (T8010/A10, the chip PongoOS's stock Linux module already
  targets) — not directly applicable to the T7001-specific gap here.
- **Asahi Linux / m1n1**: a different SoC family entirely (M-series Apple Silicon
  Macs, not A-series mobile SoCs) with a different bootloader (m1n1, not PongoOS)
  and different exception-level/hypervisor model. Not pursued further — too large
  an architectural gap to usefully diff against for this specific handoff bug.

## Round 1 outcome (implemented, tested, and it wasn't enough)

Candidate 1 below (fixed entry point + route through `exit_to_el1_image()`) was
implemented in full (see `docs/project-status.md` "Step 4") and run on hardware.
The console confirmed the new code path executed correctly —
`Booting Linux: 0x803000000(0x805960000)`, matching the fixed entry point and the
expected `gBootArgs` (DTB) placement right after it — and PongoOS then fell through
to the exact same `exit_to_el1_image()` mechanism proven to work for XNU boot on
this device. **Same result as every previous attempt**: silent hang, USB drops,
device left enumerated-but-unresponsive, no visible output of any kind (not even
the usual reddish `pixfmt` flash this time).

This is a genuinely informative negative result, not just another failure: it
rules out the entire category of "our jump/handoff mechanism is wrong," since
we're now using the literal same mechanism proven to work. Whatever's actually
wrong survives even a byte-for-byte-matched, proven exit path. That pointed
research at what happens *after* control reaches the kernel image, rather than at
how control gets there — which led to Round 2.

## Round 2: the kernel-side gap (reserved-memory / no-map)

Re-examined `konradybcio/pongoOS`'s Linux DTB generation
(`linux_dtree_init`/`linux_dtree_late` in `src/modules/linux/linux.c`) more
closely than the first pass, and compared it against both this project's current
PongoOS patch and mainline Linux's actual, upstreamed `t7001-air2.dtsi`
(`torvalds/linux`, confirmed **Konrad Dybcio's own work was merged into mainline**
— the file's copyright line reads `Konrad Dybcio <konradybcio@kernel.org>`).

**Mainline's DTS explicitly defers memory description to the loader.** Fetched
directly:

```c
memory@800000000 {
	device_type = "memory";
	reg = <0x8 0 0 0>; /* To be filled by loader */
};

reserved-memory {
	#address-cells = <2>;
	#size-cells = <2>;
	ranges;

	/* To be filled by loader */
};
```

This is a real, present, empty node in the exact kernel this project builds and
boots — not something that needs to be added to the DTS. It's a placeholder the
bootloader (PongoOS, in this project's case) is expected to populate with actual
values at boot time, before Linux ever sees the tree.

**This project's PongoOS patch never fills it in, beyond the SEPFW addition from
Round 1.** Checked `linux_dtree_init()` in the pinned PongoOS revision this
project patches: it contains an entire `reserved-memory` population block that
does exactly this kind of work — **but it's wrapped in a C block comment
(`/* ... */`), entirely dead code**, present in stock/upstream PongoOS itself
(not something introduced by this project's patch or by any T7001-specific
change). No prior iteration of this project's patch enabled or replaced it.

**Konrad's working PongoOS, by contrast, populates `/reserved-memory` for real,**
and does so with two concrete, generic entries that need no per-device hardcoded
addresses -- both computed from `boot_args` fields PongoOS already has on every
boot, on every device:

```c
/* Reserve the framebuffer (so that Linux doesn't overwrite it) */
siprintf(fdt_nodename, "/memory@%lx", gBootArgs->Video.v_baseAddr);
node1 = fdt_add_subnode(fdt, node, fdt_nodename);
fdt_appendprop_addrrange(fdt, 0, node1, "reg", gBootArgs->Video.v_baseAddr, fb_size);
fdt_appendprop(fdt, node1, "no-map", "", 0);
```

```c
if (gBootArgs->physBase > 0x800000000)
{
    /* Reserve TZ/low FW regions and such */
    node1 = fdt_add_subnode(fdt, node, "memory@800000000");
    fdt_appendprop_addrrange(fdt, 0, node1, "reg", 0x800000000, (gBootArgs->physBase - 0x800000000));
    fdt_appendprop(fdt, node1, "no-map", "", 0);
}
```

The second one is directly checkable against this project's own recorded
`linux_diag` output: `[t7001] soc=7001 phys=0x800c00000 ...` — `physBase` on this
exact unit is `0x800c00000`, i.e. **DRAM base plus ~12 MiB is firmware-reserved and
currently completely unprotected** in every build this project has run on
hardware so far. This project's own `linux_dtree_init()` shrinks the *advertised
size* of the `/memory` node by a flat 32 MiB to avoid the very top of RAM, which
has the same practical effect for that specific region (Linux never learns that
memory exists, so it can't allocate into it) -- but nothing analogous protects the
bottom ~12 MiB, and nothing protects the framebuffer at all.

**Why this is a strong candidate, independent of everything ruled out already**:
without these reservations, Linux's own generic memory allocator (page tables,
slab, buddy allocator -- all initialized extremely early, before any driver probe,
before any console/earlycon) is free to claim and overwrite firmware-reserved
memory and the framebuffer's own backing store as ordinary free RAM. That would
produce exactly the observed symptom class across all six builds so far: total
silence, no console output (because whatever writes an early kernel message might
itself be racing this corruption, or the write path depends on state that just got
clobbered), no visible framebuffer change (because the framebuffer's own memory
may be the thing that got reused), and a full hang shortly after entry -- all
without needing any new hypothesis about the jump mechanism itself, which Round 1
already showed is very likely not the problem.

**What's not yet independently confirmed**: whether *only* these two reservations
are needed, or whether the ADT's `memory-map` node has other regions beyond
`SEPFW` (Konrad's DTSI separately hardcodes several more:
`0x870100000`/`0x870180000`/three more in the `0x87f4xxxxx`-`0x87f6xxxxx` range) --
those look like specific values captured from his own physical unit rather than
something derivable from `boot_args` alone, so directly reusing his constants on
a different unit is a real risk, not just a style choice. A more portable version
of this fix would enumerate the ADT's `memory-map` node generically (PongoOS
already has `dt_parse()`, a generic node/property walker, in
`src/kernel/dtree.c`/`pongo.h`) and reserve *every* named region it finds, rather
than hand-picking `SEPFW` alone as this project's patch currently does. That's a
larger, not-yet-implemented piece of work, and the honest state is: it has not
been tried, and it's unknown whether the two generic reservations above are
sufficient on their own.

### postmarketOS as an independent sanity check (not completed)

Wanted to check whether postmarketOS's own current device page/build for
`apple-ipad5,3` (or `apple-j81`/`apple-j82` -- search results were inconsistent
about the exact codename) still describes a working boot today, as a check on
whether this general technique is still reliable in 2026 independent of anything
in this repository. The wiki page (`wiki.postmarketos.org`) is behind an Anubis
anti-bot challenge that blocked every automated fetch attempted during this
research. **This is worth checking manually in a real browser** -- it wasn't
possible to complete from here, and it would be a genuinely useful data point
either way (confirms the technique still works in general, or reveals it's
degraded/bitrotted even for the reference implementation).

## Ranked candidates for the next attempt

1. **Implement the reserved-memory / no-map fix** (Round 2 above): add the two
   generic, `boot_args`-derived reservations (low-FW region via `physBase`,
   framebuffer via `Video.v_baseAddr`) to this project's `linux_dtree_init()` or
   equivalent, matching Konrad's working PongoOS. This is now the best-evidenced
   untried candidate -- concrete, small (a few dozen lines, no new assembly or
   low-level primitives), and directly explains the exact symptom class observed
   across all six builds so far, in a way the jump-mechanism theories (all now
   ruled out or deprioritized) never fully did.
2. If (1) still fails: consider the generic ADT `memory-map` enumeration
   (reserving every named region, not just `SEPFW`) rather than hand-picking
   which regions matter -- more robust, more work, not yet attempted.
3. Check the postmarketOS wiki page manually (see above) as an independent
   sanity check, ideally before or alongside (1) -- cheap, no hardware cycle
   needed, and informative either way.
4. UART/serial console (or JTAG/SWD via something like a Tamarin cable) remains
   the correct fallback if (1) and (2) are both tried and still fail -- at that
   point the remaining hypothesis space (DART/IOMMU setup, clock/power-domain
   gating, exception-level assumptions, something not yet identified) genuinely
   needs real execution visibility rather than more inference from a black box.
5. Not recommended: continuing to guess at the jump/teardown mechanism itself --
   Round 1 showed matching the proven mechanism exactly still wasn't sufficient,
   so further iteration there has a demonstrated poor track record specifically
   (independent of the general point that six hardware attempts without a
   confirmed positive signal is already a lot of cost for the information
   gained).

## Project viability assessment

Asked directly whether this project still makes sense to continue. Honest
answer: **conditionally yes, but the condition is specific and close.**

**What's actually been accomplished, and holds up under scrutiny:** the full
build pipeline (kernel, DTB, initramfs, Nix cross-compilation) works and is
reproducible. checkm8 exploitation, DFU handling, and PongoOS upload are all
solid and repeatable. The project has correctly identified and fixed several real
bugs along the way (an LZMA staging buffer overflow, an image-size guard bug, a
missing null-pointer guard) independent of whether the core handoff ever
succeeds -- this wasn't wasted motion. And the research in this document found a
working reference implementation for the exact chip, which is a meaningfully
stronger position than "nobody has done this" -- the question is now "what does
their working combination have that ours doesn't," which is answerable, not
"is this even possible," which would be a much harder place to be stuck.

**What should genuinely inform a stop/continue decision:** six PongoOS builds,
five run on hardware, have not yet produced a single confirmed sign of Linux
executing on this device. Round 1 (matching the proven jump mechanism exactly)
ruled out a large, plausible hypothesis space and still failed. Round 2 (this
document) has a strong, concrete, well-evidenced candidate that hasn't been tried
yet -- but "strong candidate" has been true before in this project's history
(the tramp/SRAM-release fix looked similarly well-evidenced and turned out to be
a no-op on this hardware). There is no guarantee this is the last gap, and
without a UART or other real execution trace, every future attempt pays the same
cost as every past one: a DFU cycle, a hardware round-trip, and a binary
"nothing visible happened" result that's expensive to diagnose further.

**Recommendation:** try candidate 1 above -- it's cheap to implement (no new
low-level mechanism, just DTB content), well-evidenced, and directly explains
what's been observed. If it produces a visible Linux boot log or panic, that's
the actual milestone this project has been chasing, and everything downstream
(driver work, this project's own approval-gated bring-up plan) becomes
meaningful. If it *also* produces the identical silent hang with no new
information, that's a reasonable point to treat this as genuinely blocked on
tooling rather than on undiscovered software bugs, and to either invest in a
UART/JTAG path (the `konradybcio` team's own account says they were blocked over
a year on a comparably specific bug, with the same framebuffer-only constraint,
before finding it -- that's a real cost, not a hypothetical one) or pause the
project at a well-documented, resumable state rather than continuing to spend
hardware cycles on inference alone.

## Round 3: pre-hardware code review, cross-checked against Asahi Linux/m1n1

Requested before running the Step 5 (reserved-memory) build on hardware: a
review of the current patch for dead code, correctness, and alignment with
current Linux kernel / Apple-Linux community practice -- specifically checking
whether Asahi Linux (which supports newer Apple Silicon, M-series, and is a
far more mature and actively-maintained project than the 2022 konradybcio
fork) does anything materially different that this project should learn from.

### Dead code and scope-creep found (none blocking)

- **`linux_dtree_init()`/`linux_dtree_late()` are unreachable in this
  project's real flow, and diverge from the fixed path.** `linux_prep_boot()`
  branches on `fdt_initialized`; it's only false if no DTB pack was ever
  uploaded via the `fdt` command. `load_linux.py` always uploads one before
  `linux_diag`/`linux_t7001`, so the real path is always
  `linux_prepare_fdt()` → `linux_dtree_overlay()` -- confirmed directly before
  writing the Step 5 fix (see that section above). `linux_dtree_init()`
  remains present, unmodified, from-scratch, and **none of Step 4's fixed
  entry point, Step 5's reserved-memory reservations, or the SEPFW addition
  apply to it.** Not a bug in the sense of affecting any attempt made so far
  (this path has never been exercised), but a real footgun: if anyone ever
  runs `linux_t7001` without first running `fdt`, they silently get a
  completely different, unfixed, T7001-unaware code path with no warning.
  Not changed in this pass to keep Step 5 scoped to one variable; worth
  either removing this dead path or making it error out explicitly if
  `linux_t7001` is used without an uploaded DTB pack.
- **`gLinuxDtb` and `gLinuxStageAllocation` are global-scope variables used
  only locally within `linux_prep_boot()`** now that Step 4 removed the
  marker/tramp code that used to reference them from `entry.c`. Not a
  correctness bug, just wider scope than currently needed -- a leftover from
  the abandoned custom-jump approach. Harmless to leave; candidate for a
  future cleanup pass, not this one.
- **`gLinuxStageAllocation` is never freed if `linux_prep_boot()` runs more
  than once in the same live PongoOS session** (e.g. `linux_t7001` retried
  after a failed attempt that didn't fully hang). A real leak, but low
  priority: every hardware attempt so far has been a single call per fresh
  PongoOS launch (the device hangs or is manually relaunched between
  attempts), so this has not affected any result to date.

### Verified, not changed: the leading-slash node name

`linux_dtree_overlay()`'s new framebuffer reservation builds its node name as
`"/memory@%lx"` (leading slash) and adds it as a child of the
already-non-root `/reserved-memory` node. Checked libfdt's actual
`fdt_add_subnode_namelen()` implementation directly (`src/modules/linux/libfdt/fdt_rw.c`):
it `memcpy()`s the name argument verbatim into the node header with **no
character validation at all** -- a leading (or embedded) `/` is not rejected,
producing a technically malformed node name per the Devicetree Specification
(node names may not contain `/`). This looked like a plausible bug worth
fixing, but re-checking Konrad's exact working source shows **his framebuffer
reservation has the identical leading slash** (`siprintf(fdt_nodename,
"/memory@%lx", ...)` immediately followed by `fdt_add_subnode(fdt, node,
fdt_nodename)` where `node` is `/reserved-memory`, not root) -- while his low
firmware region reservation, and this project's copy of it, correctly omits
it. Linux's early reserved-memory scan (`drivers/of/of_reserved_mem.c`) walks
children of `/reserved-memory` structurally and reads their `reg`/`no-map`
properties directly off the flattened tree -- it does not do path-based
lookups by name, so a malformed literal name is very unlikely to break the
actual protection this fix exists to provide. Left as-is, matching the proven
reference bug-for-bug, rather than "fixed" into an untested variant.

### Cross-checked against Asahi Linux / m1n1

`AsahiLinux/m1n1` (the bootloader Asahi uses to hand off from Apple's boot
chain to Linux on M-series Macs -- a mature, actively-maintained, far more
complex project than anything else checked in this research) does the
**same class of ADT-to-`/reserved-memory` conversion** as this project's Step
5 fix and Konrad's PongoOS, via a generic helper,
`dt_get_or_add_reserved_mem(name, compatible, nomap, paddr, size)`
(`src/kboot.c`): find-or-create a subnode under `/reserved-memory`, set
`reg`, optionally set `no-map`. This independently confirms the *architecture*
of this project's fix is sound and matches current community practice, not
an ad-hoc guess -- the same fundamental problem (loader must tell Linux what
firmware-owned memory to leave alone) exists across every Apple-SoC Linux
port, T7001 included.

One genuinely useful nuance found: m1n1 does **not** mark every reservation
`no-map`. Its SEP firmware reservation is added with `nomap=false` --
reserved from general allocation, but still part of Linux's normal linear
map (needed because SEP communication may require the kernel to actually
read/map that memory, unlike a region that must never be touched by Linux at
all). Checked this project's own SEPFW handling in light of that: it already
uses `fdt_add_mem_rsv()` -- the older FDT memory-reservation-map mechanism,
which is `memblock_reserve()`d but, like `nomap=false`, does **not** exclude
the region from Linux's linear map. **This project's existing SEPFW treatment
already matches both mature reference implementations' choice for that
specific region**, independent confirmation it wasn't a gap. The framebuffer
and low-FW regions, by contrast, are marked `no-map` in both this project's
fix and Konrad's reference, which also matches the standard upstream
`simple-framebuffer` binding convention (Documentation/devicetree/bindings/display/simple-framebuffer.yaml
recommends the backing memory be a no-map reserved region) -- not
ad-hoc, this is the documented, expected pattern for exactly this driver.

**Not pursued further, and why:** m1n1's reservation helper additionally
generates a `phandle` and expects consumers to link back via a
`memory-region = <&phandle>` property, used heavily for M-series' DART
IOMMU/DCP display-coprocessor memory ownership. T7001's display path has no
such coprocessor or IOMMU-mediated ownership model (PongoOS pokes the display
controller's `pixfmt`/color-matrix registers directly, and the DTB's
framebuffer node is a plain `reg`-based `simple-framebuffer`, not something
that resolves memory via `memory-region` lookup) -- the phandle/link
machinery solves a problem that doesn't exist for this chip's simpler display
path. Not adding it is a considered omission, not a gap.

### Net assessment

No blocking bug found. The dead-code and scope-creep notes above are real but
don't affect this or any prior attempt's outcome, and are left unaddressed to
keep this hardware round scoped to the one change already built and
documented (Step 5). The cross-check against Asahi/m1n1 increased confidence
in the fix rather than surfacing a missing piece -- the two-region reservation
already implemented matches the architecture of the most mature reference
available, including its choice of which regions get `no-map` versus plain
`memblock_reserve()`. Ready to test.

## Round 4: real captured ADTs, a likely-fatal zero-sized /memory node, and a much safer entry point

Ran after the Step 5 (reserved-memory) hardware test still hung. User pointed at
[`SoMainline/adt_collection`](https://github.com/SoMainline/adt_collection) (real
device ADT dumps) and [`SoMainline/linux-apple-resources`](https://github.com/SoMainline/linux-apple-resources).
Both were genuinely useful, and led to what may be the single most consequential
finding of this whole investigation.

### The `/memory` node ships with size zero, and nothing ever fixed it

Mainline's `t7001-air2.dtsi` (fetched directly, see Round 2) declares:

```c
memory@800000000 {
	device_type = "memory";
	reg = <0x8 0 0 0>; /* To be filled by loader */
};
```

`reg = <0x8 0 0 0>` with `#address-cells = 2, #size-cells = 2` decodes to base
`0x800000000`, **size zero**. This project's real boot path (`linux_prepare_fdt()`
→ `linux_dtree_overlay()`) never touched this node -- the only code that used to
set a real size, in `linux_dtree_init()`'s dead-code from-scratch tree builder
(`(gBootArgs->memSize - 0x02000000) & ~0x1FFFFFF`, confirmed unreachable in
Round 3), never ran, because this project's actual flow always uploads a real
DTB pack first. **Every hardware attempt across Steps 1-5 has been sending
Linux a device tree that describes zero bytes of usable RAM.** A kernel told
this fails in its own `memblock`/`mm` initialization before any driver, before
any console -- exactly matching the total-silence symptom of every single
attempt so far, independent of the jump mechanism (Step 4), the reserved-memory
work (Step 5), or anything else tried. This is now fixed (see below) and is the
strongest single candidate this investigation has produced for what's actually
been preventing a boot.

### Real ADTs show the chosen entry point was riskier than it looked

`SoMainline/adt_collection`'s files turned out to be PongoOS's own `dt` command
text output (captured via `scripts/issue_cmd.py dt` + `scripts/fetch_stdout.py`
per the repo's README), not raw binary ADTs -- readable directly. `a8/J82.adt`
is a real capture from a **J82**, the cellular sibling of this project's J81
target (same T7001 SoC, same board generation). Its `memory-map` node:

| region | addr | size |
|---|---|---|
| SEPFW | `0x802be4000` | 6 MiB |
| BootArgs | `0x8031e4000` | 4 KiB |
| DeviceTree | `0x8031e5000` | ~1.8 MiB, ending `0x8032021ec` |
| (17 more regions, mostly `Kernel-__*` XNU sections) | | |

Total across all 19 regions: ~35 MiB -- trivial against a 2 GiB device, so size
was never the concern. *Position* was: **`0x8032021ec` is only ~2 MiB above
`0x803000000`**, this project's entry point since Step 4. The kernel Image was
being placed at `gEntryPoint + 0x200000` (Step 6's marker offset) =
`0x803200000` -- which falls *inside* the `DeviceTree` region's own bounds
(`0x8031e5000`-`0x8032021ec`). Checking the same field across every other A8-family
dump in the collection (different exact SoC, same generation) showed the
highest region ending anywhere from ~50 MiB to **~96 MiB** from DRAM base
(`n56`/`n61`, likely iPhone 6/6 Plus, T7000). `0x803000000` is only 48 MiB in --
below the *low* end of that range, let alone the high end.

Whether this specific overlap is what caused any given hang couldn't be
confirmed (iBoot's own code isn't still running by the time PongoOS reaches
this point, so the *software* dependency risk is unclear -- but placing a ~41 MiB
kernel copy this close to memory iBoot was using moments before handoff, with
no independent verification for the actual J81 unit, is not a risk worth
carrying when a cheap, well-margined alternative exists). `konradybcio`'s own
comment on `0x803000000` -- *"a really hacky guesstimate... doesn't really
matter as long as it works"* -- reads differently in light of this real data:
it may have worked for the specific kernel builds and units they tested against
(smaller `Kernel-__PRELINK_*` sections push these regions lower), without being
safe in general. This project's kernel build's own real region sizes were never
compared against this margin before Step 4.

**Fix**: moved to `0x810000000` (256 MiB from DRAM base) -- over 2.5x past the
worst case observed (96 MiB) across every A8-family dump available, while still
leaving ~1.75 GiB above it on a 2 GiB device.

### Implemented, alongside the entry marker (Step 6)

Three changes landed together this round -- one pure instrumentation addition,
two real logic fixes bundled deliberately (both independently well-evidenced,
and going back to hardware is costly enough that testing them separately would
have meant burning a cycle on a fix -- the zero-sized memory node -- that looks
about as close to "obviously necessary" as anything found in this whole
investigation):

1. **The `/memory` node size fix** (above) -- the best-evidenced single change.
2. **The entry point margin fix** (above).
3. **Generic ADT `memory-map` enumeration**, superseding the Round 2/3 "not yet
   built" candidate: every named region under `memory-map` is now reserved as
   `no-map` in the Linux DTB (except `SEPFW`, which keeps its existing
   `fdt_add_mem_rsv` treatment from Step 4/5 -- matches `AsahiLinux/m1n1`'s
   deliberate choice not to mark SEP `no-map`, per Round 3). Uses PongoOS's
   own generic ADT walker, `dt_parse()`, rather than hand-picked addresses.
4. **An entry-point marker** (`src/boot/t7001_entry_marker.S`), reviving
   observability but architecturally different from the abandoned Step 1-3
   marker: instead of a separate `jump_to_image` call, this stub is placed
   *at* the real, fixed entry point and runs *through* the already-proven
   `exit_to_el1_image()` path (Step 4), in the exact physical position the
   kernel itself occupies. It preserves `x0` (the DTB pointer) and
   `x1`-`x3`, paints a brief marker on the physical framebuffer, then branches
   to the real kernel Image (placed 2 MiB after the entry point to make room).
   If this is ever seen, execution reached this exact point with the boot
   protocol intact, regardless of what happens next -- unlike every prior
   silent hang, this doesn't require guessing whether the kernel was ever
   reached at all.

Build details, exact diffs, and the new structural tests are in
`docs/project-status.md`, Step 6.

## Sources

- [konradybcio/pongoOS](https://github.com/konradybcio/pongoOS)
- [konradybcio/linux-apple](https://github.com/konradybcio/linux-apple)
- [torvalds/linux — arch/arm64/boot/dts/apple/t7001-air2.dtsi](https://github.com/torvalds/linux/blob/v6.19/arch/arm64/boot/dts/apple/t7001-air2.dtsi)
- [AsahiLinux/m1n1 — src/kboot.c](https://github.com/AsahiLinux/m1n1/blob/main/src/kboot.c)
- [Boot Mainline Linux On Apple A7, A8 And A8X Devices — Hackaday](https://hackaday.com/2022/06/12/boot-mainline-linux-on-apple-a7-a8-and-a8x-devices/)
- [Now you can boot Linux on Apple devices with A7 through A11 series chips — Liliputing](https://liliputing.com/now-you-can-boot-linux-on-apple-devices-with-a7-and-a8-series-chips/)
- [A11pwnX/Linux-iPhone-6s-X-howto](https://github.com/A11pwnX/Linux-iPhone-6s-X-howto)
- [SoMainline/adt_collection](https://github.com/SoMainline/adt_collection) -- a8/J82.adt
  specifically, real T7001-family memory-map data used in Round 4
- [SoMainline/linux-apple-resources — HOWTO.md](https://github.com/SoMainline/linux-apple-resources/blob/master/HOWTO.md)
- postmarketOS wiki device page (`wiki.postmarketos.org`) -- blocked by an Anubis
  anti-bot challenge during this research; check manually in a browser.
