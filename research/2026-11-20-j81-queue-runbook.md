# Test queue runbook (prepared 2026-11-20 while Martin was away). Nothing below has been run.

Readiness: `boot/check_j81_queue.sh` prints `QUEUE READY` (checksums of every artifact, host tests, `--verify-only`). No builds are needed for any step; the builder VM is stopped and not required. Each step is one DFU cycle.

Order (highest value first; later steps are conditional):

| # | Step | Kind | What it answers |
| --- | --- | --- | --- |
| 1 | Linux PLL replay test | writes (2 PLL words) + core read | does iPadOS's page-1/page-4 `+8[31:30]=01` (the one observed unmatched difference) unblock the core read? Includes MiscACG, +0x2d000, voltage check, all before GFX power-on |
| 2 | iPadOS `fender-pmgrx-cpu48` | read-only | Fender +0 bit 29 (paired with a successful ID path), SoC TVM status +0x2d100, vm_sram +0x23004, +0x22000 before and after GPC, CPU TVM +0x48 |
| 3 | iPadOS `fender-cpu194` | read-only | DPE bit 35 (bit 3 of +0x194) |
| 4+ | iPadOS `fender-cpu20`, `-cpu190`, `-cpu150`, `-cpu1a0`, `-cpu1b0` | read-only | only if step 2 or 3 shows a difference worth completing (each also gives a second Fender sample) |

If step 1 returns the GPU ID the problem is solved; skip the rest and tell me. The core read can hang (the 20 s watchdog resets the iPad into iPadOS); that is an expected outcome, not a failure of the queue.

## Step 1: Linux PLL replay test (I launch it, you do the boot)
1. iPad in DFU, then (sudo needed):
```bash
cd /Users/martinp/Work/Sandbox/ipadlinux/ipad-nixos && sudo boot/vendor/palera1n-macos-arm64 --pongo-shell --override-pongo artifacts/live/private/j81-observer-paired-20261119-v1/Pongo.bin --debug-logging
```
2. At "Booting PongoOS..." (replug the Lightning cable if it stalls or times out, then redo step 1 from DFU):
```bash
cd /Users/martinp/Work/Sandbox/ipadlinux/ipad-nixos && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=artifacts/live/gcroot-pyusb/lib/python3.14/site-packages /opt/homebrew/bin/python3 boot/load_m1n1.py artifacts/live/private/j81-observer-paired-20261119-v1/m1n1-linux.bin
```
3. Tell me "linux up". I run the preflight and the campaign (`artifacts/live/private/j81-linux-pll-write-experiment/runner/boot`, log dir `j81-linux-pll-write-results-<date>-run1`), record the result, commit, and copy it to the mailbox. Sequence inside: S0 snapshot, MiscACG store, voltage-manager check (stop if bits 11:8 set), +0x2d000 store, PLL1 `+0x1008` store (only if it reads 0x80480348 -> 0x40480348), snapshot, PLL4 `+0x4008` store (only if 0x88480348 -> 0x48480348), snapshot, GFX cycle, bridge, GPC batch, core read under the watchdog. Any unexpected readback stops the run before the next step.
4. When I report the result (or the iPad is back on iPadOS) go on.

## Steps 2 to 4+: iPadOS read-only probes (one DFU cycle each; I decode the result)
Per probe: iPad in DFU, run (replace `<V>` with the variant), wait for iPadOS to boot, unlock, then collect and tell me the variant. Same commands for each:
```bash
cd /Users/martinp/Work/Sandbox/ipadlinux/ipad-nixos && sudo boot/vendor/palera1n-macos-arm64 --rootless --override-kpf artifacts/live/private/j81-ios-state-probes/checkra1n-kpf-pongo-j81-<V> --debug-logging
```
```bash
cd /Users/martinp/Work/Sandbox/ipadlinux/ipad-nixos && sudo /usr/bin/log collect --device-udid f8f1f9d8d3a75efe97c87c34918381c824c315c5 --output artifacts/live/private/gpu-offline/j81-<V>-device.logarchive
```
(Replug the cable if palera1n stalls at "Booting PongoOS..."; wait for the collect prompt to return before touching the iPad; if the collect says the archive exists pick a new name.) Ready-to-paste for steps 2 and 3:
- Step 2 `<V>` = `fender-pmgrx-cpu48`
- Step 3 `<V>` = `fender-cpu194`
I then run `boot/decode_j81_ios_probe.py <archive> <V>`, which labels every field and derives Fender bit 29 and the CPU bits, and write the result note.

## Field meanings (decoder prints them; for reference)
- `fender-pmgrx-cpu48`: P0/P1 `P=` PMGR +0x2d100, `V0=` +0x23004 (vm_sram), `V1=` +0x22000; P1 `G=` Fender +0 (0x201e00000); `CORE=` is the CPU cluster word at 0x202220048 (the GPU ID is not read in this boot).
- `fender-cpuNN`: P1 `G=` Fender +0; `CORE=` the word at 0x202220000+0xNN.
- Reference values already known: iPadOS +0x1008/+0x4008 = 0x40480348/0x48480348; Linux +0x2d100 reads 0 before and 1 after the +0x2d000 store, vm_sram 0x170 (0x180 transiently), Fender +0 0x40000000.

## What decides the next move
- Step 1 returns an ID: PLL words were the missing step; write it up, port into the driver recipe.
- Step 1 hangs: the page-1/page-4 pair alone (with MiscACG and +0x2d000) is not sufficient; use steps 2-4 to look for the next difference (Fender bit 29, CPU TVM, DPE, vm_sram / +0x2d100 / +0x22000 on iPadOS vs Linux).
- Step 1 stops early with a readback mismatch or a lost link: the PLL writes had an unexpected effect on this chip; that is a result, and the summary will show which snapshot differed.
- Fender bit 29 set on iPadOS: a Linux write/replay of that bit becomes the next candidate (needs a plan). Clear: excluded.

## Not prepared
A Linux read of the CPU cluster block through /dev/mem (needed to compare CPU TVM / DPE with iPadOS, only worth it if an iPadOS word is nonzero), and a Linux replay of the CPU TVM / DPE writes. Both wait for the iPadOS values.

## Addendum (after step 2): Linux read of +0x22000
Step 2 showed iPadOS +0x22000 = 0x80000000 (and Fender bit 29 clear, CPU TVM bit 0 clear, both excluded). Linux has never read +0x22000. Read-only script `boot/j81_linux_pmgr_words.py` (tests pass) reads PMGR +0x22000 .. +0x223fc (256 words, the per-domain 0x220xx words of the A8 thread's list) on any fresh Linux observer boot, using the same pinned read-only peek tool; it needs only the two boot commands of step 1, no GFX power-on and no stores:
```bash
cd /Users/martinp/Work/Sandbox/ipadlinux/ipad-nixos/boot && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib PYTHONPATH=../artifacts/live/gcroot-pyusb/lib/python3.14/site-packages /opt/homebrew/bin/python3 j81_linux_pmgr_words.py ../artifacts/live/private/j81-linux-pmgr-words-<date>-run1
```
I run it after "linux up". If Linux +0x22000 is not 0x80000000, a guarded Linux replay of that word becomes the next candidate (needs a plan).

## Addendum 2: iPadOS p22 probe (after the +0x22000 stock lookup, `2026-11-20-j81-22000-stock-lookup.md`)
Variants `p22` (and `fender-p22`) read +0x22004/08/0c/10 before GPC and +0x22004/08/0c/10/14 after it. Use `<V>` = `p22` with the step-2 commands (collect name `j81-p22-device.logarchive`); the decoder labels every field.

## Addendum 3: Linux +0x22000 write test (built after the p22 result; not run)
`artifacts/live/private/j81-linux-w22000-write-experiment/runner/boot` (tests pass, `--verify-only` passes). Same flow as step 1 with one more guarded store: MiscACG, voltage check, +0x2d000, PLL1 +0x1008, PLL4 +0x4008, then **+0x22000 (must read 0x00000000, store 0x80000000, readback must match)**, snapshot, all before GFX power-on, then GFX cycle, bridge, GPC, core read under the watchdog. Stops before the next step on any unexpected readback; stops before the bridge/GPC if any stored word is lost. Boot with the two step-1 commands, say "linux up", and I launch:
`python3 j81_observer_paired_campaign.py <new logdir> --bundle <bundle>` from that runner directory (log dir `j81-linux-w22000-write-results-<date>-run1`). The writer is `boot/pmgr-w22000-set.c` (sha256 ee719eb2..., one 32-bit store). What the bit does is unknown and the stock setter is unlocated; this replays the observed iPadOS end state.
