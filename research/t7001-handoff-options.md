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

## Ranked candidates for the next attempt

1. **Adopt the fixed entry point `0x803000000` and route T7001 through
   `exit_to_el1_image()` like XNU, instead of a direct `jump_to_image()` call.**
   This is the best-evidenced candidate: it's the exact mechanism a working
   reference implementation uses, on the exact same chip, and it's a smaller,
   simpler amount of custom code than the current patch (removes the custom
   `linux_t7001` jump-target selection, the tramp buffer, and the diagnostic vs.
   handoff split entirely). Testable incrementally and safely: the entry-point
   constant and DTB `SEPFW` reservation can be added and inspected via
   `linux_diag`-style read-only reporting before ever attempting a real jump.
2. **Deprioritize the "missing `cache_clean()` before the jump" theory** recorded
   in this project's own docs — the working reference doesn't do this either.
   Don't spend a hardware cycle on it unless (1) is tried first and still fails.
3. **UART/serial console** remains the right long-term answer if (1) doesn't
   resolve things, per this project's own prior conclusion — but it's now a
   secondary priority behind actually trying the proven reference approach, since
   (1) doesn't require any new hardware and directly targets a documented, working
   implementation rather than blind ARM64 internals guessing.
4. Not recommended: continuing to iterate on the custom `jump_to_image`/tramp/
   marker path from this project's own patch without first trying to match the
   proven reference's approach — five hardware attempts down that path have
   produced no new information beyond "it still hangs."

## Sources

- [konradybcio/pongoOS](https://github.com/konradybcio/pongoOS)
- [konradybcio/linux-apple](https://github.com/konradybcio/linux-apple)
- [Boot Mainline Linux On Apple A7, A8 And A8X Devices — Hackaday](https://hackaday.com/2022/06/12/boot-mainline-linux-on-apple-a7-a8-and-a8x-devices/)
- [Now you can boot Linux on Apple devices with A7 through A11 series chips — Liliputing](https://liliputing.com/now-you-can-boot-linux-on-apple-devices-with-a7-and-a8-series-chips/)
- [A11pwnX/Linux-iPhone-6s-X-howto](https://github.com/A11pwnX/Linux-iPhone-6s-X-howto)
- [SoMainline/adt_collection](https://github.com/SoMainline/adt_collection)
