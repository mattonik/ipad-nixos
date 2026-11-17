# J81 PongoOS GPU split test: plan and GO/NO-GO list

Status: **plan only.** Nothing has been built or run yet. Every fact in
"Offline facts" was re-checked on Martin's Mac on 2026-11-14 and matched. The rationale is in
[the strategy reset](2026-11-14-j81-gpu-strategy-reset.md), direction 1.

## Question

Does the RGX core-ID read at `0x201000020` answer when the known Linux GPU
sequence runs from the PongoOS shell, before XNU or m1n1 has run?

- **It answers:** the missing step is something m1n1 or Linux breaks. Next,
  bisect that side (m1n1 `cpufreq_init`, Linux initcalls).
- **It hangs:** iPadOS's boot does something we don't. Next, bisect the XNU
  boot with the existing KPF hooks.
- **Page-5 bit 30 sets in PongoOS** (read before the core read): same
  conclusion as "it answers", and it is known without risking the core read.

## Offline facts (checked 2026-11-14)

- `boot/Pongo.bin`, sha256 `1e5543fd8e6dbd84c334b87d71aa473f4d347c2ba8a5e863b6e10f18461c7575`,
  prints `pongoOS 2.6.3-bb492b00`. Its strings include the shell commands
  `peek` ("32bit mem read") and `poke` ("32bit mem write").
- In PongoOS source at `bb492b0` (`src/shell/main.c`), `peek`/`poke` take a
  hex address and do a plain 32-bit load or store on that virtual address.
  `src/kernel/mm.c` `lowlevel_setup` maps VA `0x200000000`-`0x2ffffffff` 1:1
  with attribute index 0. MAIR is `0x04ff00`, so index 0 is Device-nGnRnE,
  the same as Linux. Every address below lies in that range, so **no custom
  Pongo module is needed**.
- The USB shell protocol is the one used by `scripts/pongoterm.c` (same
  source): command via control OUT `0x21/3`; output via IN `0xa1/1`;
  command-in-progress flag via IN `0xa1/2`; stdout blocking mode via OUT
  `0x21/4` with `wValue` `1` and `0xffff` (`src/shell/usbloader.c`).
- The bridge plan is private and must not be committed:
  `artifacts/live/private/gpu-offline/gfx-bridge-plan.bin`, 528 bytes, sha256
  `1c7b3839da2e7aa914a393e914a7a427c12190293ba5d2b50fe06cf4d8df6435`. It
  contains 2 × 33 little-endian `(offset, value)` pairs, bases `0x201f00000`
  and `0x201f80000`. The offsets are `0x18`, then `0x40000 + 4*(i-1)`; the
  check in `boot/gpu-bridge-once.c` must be repeated.
- The GFX power-on must mirror Hoolock `pmgr-pwrstate.c` (sha256 `4b0adc30…`,
  `apple_pmgr_ps_set`): clear AUTO_ENABLE (bit 28), the flags (bits 9:8) and
  the target (bits 3:0), set target `0xf`, poll until actual (bits 7:4) is
  `0xf`, then write back with the flags cleared and AUTO_ENABLE set. Linux
  read back `0x3ff` after this.
- `boot/j81_preflight.sh` checks only a running Linux boot, so it **cannot**
  vouch for this test. The GO/NO-GO list below replaces it for this run.

## Sequence

Each step goes to the transcript and is flushed before the next command is
sent. Stop on any unexpected value, and make no further writes after a stop.

1. Read GFX PS `0x20e020320`. GO only if it is `0x300` (GFX off). Read page
   5 `0x20e005004`, perf control `0x20e01c200` and voltage `0x20e02300c`.
   Do **not** read any GPC or core address while GFX is off. `0x300` was
   seen under Linux; in PongoOS the state may differ. If so, stop and
   record the value: that is a finding in itself.
2. GFX power-on as above. GO only if PS then reads `0x3ff`.
3. Read GPC state `0x201e01000`. GO only if it is `0`.
4. The 66 bridge stores, in plan order, with each `poke` echo verified.
5. GPC wake: `0x201e10000 = 0xffff0000`, `0x201e00000 = 0x40000000`,
   `0x201e01000 = 0x11`. Then poll `0x201e01000` until bit 4 is clear and
   `(v & 0x1f) == 1`, at most 64 polls (the limit in `gpu-gpc-init.c`).
6. Read page 5 three times, perf control, voltage, and GPC control
   `0x201e00000`, which must be `0x40000000`. **Record the page-5 result
   prominently.**
7. Write a final "before core read" line to the transcript, then read
   `0x201000020`. If it answers, also read `0x201000018`.

A step-7 hang shows up as a USB timeout. Treat it as "no response" and do not
retry.

## Build rules for the Mac session

- Host-side Python only (pyusb from the existing GC root, as
  `boot/run_m1n1_debug.sh` sets it up). A `--mock` mode must simulate the
  register file so the tests can run without the iPad.
- Host tests must cover: plan hash and offset validation; the exact command
  order; every stop condition; poke-echo verification; and a hang classified
  as no-response. Register the tests in `tools/check_offline.py` if that is
  how this suite discovers them.
- Flags: `--no-core-read` runs steps 1-6 only. The output directory must not
  already exist, and the transcript is private (`artifacts/live/gpu/…`).
- Wrapper script: verify the hashes of palera1n (`950c357b…`, see
  `boot/vendor/README.md`), `boot/Pongo.bin` and the plan. Then run
  `sudo boot/vendor/palera1n-macos-arm64 --pongo-shell --override-pongo boot/Pongo.bin --debug-logging`,
  and after the Pongo shell is exited, run the test script. This is the same
  two-phase pattern as `boot/run_m1n1_debug.sh`.

## GO/NO-GO before giving Martin boot steps

- [ ] All host tests pass in mock mode, including hang and every stop case.
- [ ] A mock dry run prints the full command list. Compare it by hand with
      `boot/gpu-bridge-once.c`, `boot/gpu-core-revision-once.c` and the GPC
      writes in the prior Linux GPC tool.
- [ ] Hashes of `palera1n`, `Pongo.bin` and the plan match the pinned values
      on the Mac.
- [ ] The pyusb GC root exists, and the script runs `--help` with the exact
      Python used by `run_m1n1_debug.sh`.
- [ ] No private file (plan, transcript) is staged in Git.
- [ ] Martin is told what happens on a hang: the iPad freezes in PongoOS with
      the watchdog off, needs a forced restart into DFU, and no filesystem is
      mounted at that point.

## Afterwards

Record the result in a new research note (values, page-5 outcome, core-read
outcome). Follow the decision in "Question" above, and do not repeat the run
on the same boot.
