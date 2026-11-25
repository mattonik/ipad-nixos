# Research request 11 result: which ConfigRAM entries complete on J81, and what the hanging ones need (19H394)

Offline analysis of the same stock iPadOS 15.8.5 (19H394) J81 kernelcache as requests 6–10 (sha256 `c3507666…a0008`, AGXG4G). SOFT_RESET bit names come from upstream Linux `drivers/gpu/drm/imagination/pvr_rogue_cr_defs.h` and the reset order from `pvr_fw_startstop.c` (kernel.org, current master). Applying those names to this core is inferred.

Addresses drop the `0xfffffff0` prefix. Tags:
- **code**: read from the disassembly;
- **source**: upstream PowerVR source;
- **capture**: the run log or the runner source in `context/`;
- **inferred**.

No device was used. There is no Apple binary content beyond addresses, offsets, short mnemonics and field names.

## Short answer

What completes through the walk:
- plain register writes, such as META_BOOT (run 33);
- writes of a register's current value (runs 30 and 35).

What hangs:
- SLC mode writes (runs 31 and 32);
- reset asserts (run 36).

On the host side, Apple has nothing in place that the runner lacks (Q1). No clock-gate, power-island or DVFM write happens before the stream, and there is no override hold.

The difference that best fits is **clocking**:
- In state 0 the GPU core clock is stopped: the ADT perf-states give state 0 = 0 Hz, and PLL5 bit 30 reads 0 (runs 20–23).
- The hanging writes are the ones that need the core clock to finish: synchronous unit resets and an SLC reconfiguration.
- The same full assert succeeds from the host in state 1 (W2a), and Apple's own stop path asserts the SLC reset directly with the GPU clocked.

How Apple's walk completes the same entries is not visible in host code. The one host-visible ordering difference: Apple's second state-0 request does not wait for the transition to finish, and the stream and release follow at CPU speed. So Apple may release the override before the GPU has settled into state 0 (inferred, untested). The boots below test the clock reading directly, one variable at a time.

## Findings

**Q1, located (code). Nothing extra is in place on Apple's side** (t2).
- **(a) Clock gates:** Apple never writes `RGX_CR_CLK_CTRL`. The name and `CLK_STATUS` appear only in the failure dump (`0x669a15c`, `0x669a140`). The only direct RGX store near offset 0 goes to `0xac8` (`0x6694300`). With the J81 GPC bit set, every fw write primitive goes to ConfigRAM. No META/BIF/SLC clock or power-island register is written before the stream. The provider calls (PMGR PS) and bridges 9/10, which the runner now matches, are the only host actions on GFX.
- **(b) DVFM:** no AGX or PMGR code raises a GPU PLL or writes a GFX perf-state table before state 1 (request 8, by search). Both sides therefore release the override with the GPU in state 0, which is 0 Hz in the ADT, unless the GPU hasn't reached state 0 yet.
- **(c) Between stream and store:** Apple does only these things:
  - the end marker with its load-back;
  - a timestamp;
  - accel slot `0x8a8 (1)` (event sources and the AIC unmask);
  - a global read;
  - `+0x20000 = 0` with a load-back (`0x669c24c`–`0x669c268`).

  One timing difference stands out. Apple's second state-0 request (setter `0x6698d94`) pre-polls busy, stores `0x10`, loads once, and **does not wait for state 0**. h3pb waits until the request completes, then spends milliseconds on host round trips before the store.

**Q2, located in part (source; capture). Decoding the three asserts** (t1, every bit):
- **Assert 1:** everything Apple resets. Of the bits that read back 1 on J81 after the host's full-assert store (W2a, `0x0000f1fb_6c000000`):
  - TLA (26), SLC (27), DUST_A/B (29, 30);
  - GARTEN/firmware processor (32), BIF1 (33), DUST_C–H (35–40);
  - BERNADO0/1 (44, 45), PHANTOM0/1 (46, 47).
- **Assert 2:** releases RASCAL and the dusts (upstream `MASKFULL ^ RASCALDUSTS`) and keeps TLA, SLC, GARTEN, BIF1, BERNADO and PHANTOM asserted.
- **Assert 3:** keeps only GARTEN.
- Apple leaves SYSARB (bit 5) alone; the upstream full mask includes it.

**The walk's path is not cut by these resets (source; inferred).** The walk writes RGX registers over the register bus, not through BIF or META. Upstream asserts every unit and then reads SOFT_RESET back over that same interface "to clear the SOCIF pipeline", so the register interface stays reachable with units in reset. Resetting BIF or META therefore shouldn't strand the walk's next write.

**Why an assert could still hang (inferred).** A unit reset is synchronous and has to cross into a clock domain that is stopped in state 0, so the write that starts it never completes. META_BOOT is a configuration register in the always-clocked register domain, so it completes. A changing `SLC_CTRL_MISC` write needs the SLC to reconfigure, so it hangs.

Evidence that the asserts themselves are fine when the GPU is clocked:
- W2a's full assert from the host in state 1 returned (capture);
- Apple's stop/recovery path stores `SOFT_RESET = 0x08000000` (SLC only) directly with the GPU clocked (`0x6694200`–`0x6694270`, code).

Whether the first assert alone hangs is untested. The bisect in Q4 covers it more cheaply.

**Q3, located (code). There is no hold on the boot path.**
- Apple writes `+0x20000` exactly once between the stream and `0x11`: the value 0, then a load-back.
- The hold is slot `0x60 (1)`: store `0x20`, poll bit 5, then poll `+0x1000` bit 4. It is used only by fw slot `0xd8` before META slave-port access, where it is followed by `+0 = 0x40000000` and a state ≥ 1 check (fw slot `0x240`).
- The hold confirms itself by reading `+0x20000`, and run 25 showed that read hangs in state 0. So **do not try the hold variant in state 0**.

## Q4: next boots (all with h3pb and run 33's order; one change per boot)

Full table in t3. Ranked by information per risk:
1. **R1, GARTEN-only assert:** `0x100 ← 0x00000001_00000000`, then `0x100 ← 0` (Apple's third value plus the release).
   - Pass: a reset assert as such completes in state 0, and the hang needs a clocked unit.
   - Hang: any assert through the walk hangs in state 0.
   - Low risk: only the firmware-processor wrapper is reset, and it runs no firmware here.
2. **R2, if R1 passes: SLC-only assert:** `0x100 ← 0x00000000_08000000`, then `0x100 ← 0`. This is bit 27, the value Apple's stop path writes.
   - Hang: both hang classes come down to the SLC.
   - Pass: bisect the rest of assert 2 (TLA, BIF1, BERNADO/PHANTOM).
3. **W1S, a walk in state 1:** run 33's META_BOOT list, with the `+0x20000 = 0` store moved to after `0x11` and state 1.
   - If META_BOOT reads 1, Fender also walks on a release in state 1. Then rerun run 36's assert list the same way. A pass there makes the stopped clock in state 0 the cause.
   - Run 15 hung this way, but that was before the bridge fix.
4. **AT, Apple timing:** the second state-0 request without waiting, then `+0x10`, `+0`, run 36's list, the end marker and the release, all in one irq-off call (like run 26, now after h3pb). This tests whether Apple's release lands before the GPU settles. It is several accesses in one call, so a hang can't be attributed inside it.
5. Your (iii), META_BOOT + SLC pair without resets, will most likely hang like run 32, so it tells you little. Your (iv), assert 2 alone, contains the SLC bit; R2 answers it more precisely.

Do not do:
- the hold in state 0;
- reads of `+0x20000` before it is written;
- PMGR `+0x5004` after `+0` and before state 1;
- RGX reads in state 0;
- BIF entries without a real page catalogue.

## Not resolved

- How Apple's walk completes the asserts and the SLC pair: a release before state 0 settles, a walk at 0→1, or something in hardware not visible from the host.
- What `0x3808` is.
- Whether the W2a readback mask is the set of implemented reset bits or partly a sign that direct stores don't fully land (the runner's own caveat).

## Files

- `t1-soft-reset-bits.tsv`: Q2, every bit in the three asserts with upstream names and whether it latches on J81.
- `t2-apple-window.tsv`: Q1/Q3, what Apple has or does before and around the stream, compared with the runner.
- `t3-next-boots.tsv`: Q4, the ranked boots.
- `SHA256SUMS`.
