# Research request 6 result: the Fender `+0x20000 = 0` store hang (J81, 19H394)

Offline analysis of the stock iPadOS 15.8.5 (19H394) J81 kernel, sha256 `c3507666…a0008`, AGXG4G kext. Addresses drop the `0xfffffff0` prefix. Tags: **code** (read from the disassembly), **capture** (the runner's notes or source in `context/`), **inferred**, **claimed** (stated by others, not checked here). No device was used.

## Findings

**The main finding: Apple power-cycles the GPU between the first wake and the ConfigRAM stream. The Linux sequence does not.** At probe, Apple turns the GPU on through its provider and does the first wake: end marker, `+0 = 0x40000000`, `0x11`, poll (code, `0x6683918`–`0x66839ac`). Accelerator start then does three things (code, `0x666d924`–`0x666d9a4`):
- requests state 0 (`+0x1000 = 0x10`, with a tight poll on the busy bit);
- switches the GPU off through the same provider: vtable `+0x570 (0,0,0)`, then `+0x568 (0,0)`;
- clears its "powered at probe" flag.

Later, firmware slot `0x78` switches the GPU back on (fw slot `0x228` → provider `+0x568 (1,0)`, then `+0x570 (1,&out,0)`) and requests state 0 a second time. Only then does the stream get written (t1).

The Linux runner turns GFX on once, does its own first wake and two direct RGX writes (W1, W2a), requests state 0 and writes the stream. It never switches GFX off in between (capture: `j81-gpu.c.txt`, `step_activate`, `step_batch`, `step_w1`, `step_w2a`, `step_h`). Both of Apple's switch-off conditions (`0x7a4d882` bit 2 and `0x7a4d87f`) are the same ones that let the probe do its first wake. So on any boot where Apple does the first wake, it also does the switch-off (code).

**Q1, located (code, strong).** t1 lists every access in order, from the 1 → 0 request at `0x666d95c` to the first stream store at `0x6690c20`. The register accesses in that window:
1. The 1 → 0 request and its tight poll.
2. GPU gate off, two provider calls.
3. GPU gate on, two provider calls in reverse order.
4. Fender `+0x10` load, store 0, load (`enableGPCHostInterrupts(3)`). This is done twice, at power-on and again at hardware start.
5. A second state-0 request through the setter (pre-poll every 10 µs, store `0x10`, one load).
6. `+0 = 0x40000000` with a load-back.

No delay is coded, apart from the setter's 10 µs poll steps. Nothing touches RGX directly.

Which PMGR registers the provider calls write was not decoded, since the provider class is in another kext. Its J81 ADT node `sgx` has `clock-gates = power-gates = 124`, and PMGR's `devices` table names id 124 "GFX". So the calls almost certainly switch the same GFX domain that Linux drives through `PM_GFX_PS` (`0x20e020320`) (inferred, strong).

**Q2, located (code, strong).** Fender slot `0x60` with argument 0 does only this: store `+0x20000 = 0`, then a load of `+0x20000`, then return. There is no state check, flag check, poll, barrier or delay (`0x669c24c`–`0x669c268`). The register's own name, from Fender's register dump (slot `0x40`), is `AGX_CR_FNDR_VCM_PERF_STATE_OVERRIDE`.

All three callers with argument 0 make this store right before a GPC state request:
- `bootFirmware` (fw slot `0xc0`): before `0x11`.
- Stop or park (fw slot `0xc8`): before `0x10`, and only if Fender is marked powered.
- A META reset/recovery path (`0x669423c`): before `0x10`, after R0 `+0x1340`/`+0x12a8`/`+0x100` writes and `+0 =` a saved mode.

In the boot path the last state request before the store is the second state-0 request (t1 row 17). So Apple does make this store in state 0, with a non-empty stream just written (code for the order; inferred that the state stays 0). The last MMIO before the store is the end marker's own load-back. No barrier instruction sits on the path.

**Q3, located (code, strong).** Between the end marker and the store (t3):
- a timestamp written to firmware memory;
- `accel slot 0x8a8 (1)`, which enables interrupt and event sources, with no GPU MMIO in that function (the event-source enable itself is not decoded);
- a read of a global.

`+0` is not written again and `+0x14` is not written. No RGX register is touched outside the stream.

**Q4, located (code, strong for the differences listed in t4).** The first wake runs without a Fender object, does not touch `+0x10` or `+0x20000`, and stores `+0` without a load-back. The boot path differs in three ways:
- it runs after the power cycle above;
- it creates the Fender object and sets its "powered" flag (object `+0xc`, slot `0x30`), and the stream is written only when that flag is set (fw slot `0x98`, `0x668fa40`);
- it clears `+0x10` twice.

The fw "booted" flag `+0xb37` is cleared at power-on and set after `waitForFWAlive`. `0x68ea90` is reached only from the doorbell, not from boot.

**Q5, not located in code (inferred).** No code in the kext enables a clock or PLL for RGX at state 0, apart from the provider gate calls. The kext never uses offset `0x5004`, so it does not touch PLL5 directly (code, by search). As the runner observed, its lock follows the Fender state, so Apple also writes the stream with PLL5 unlocked (inferred from the order; no capture). The `+0x20000` store is `VCM_PERF_STATE_OVERRIDE = 0`, the release of a performance-state override. With argument 1, Apple writes `0x20` and waits for bit 5, so bit 5 reads back as "override active" (code). What Fender does when the override is released with entries in ConfigRAM is not visible from host code. The runner's runs 12–21 show it is the first point where a non-empty list matters (capture).

## Most likely missing precondition

The GFX power cycle: power off after the 1 → 0 request, power back on, then a second state-0 request through the busy-polling setter, all before `+0x10`, `+0` and the stream (t1 rows 3–17). It is the only step in Apple's path between the first wake and the stream that the Linux sequence does not reproduce. Every other step in t1 already has an equivalent in `step_h`.

That this explains the hang is **inferred**. The code shows the power cycle exists, not why Fender needs it. One plausible reading: Fender only walks ConfigRAM cleanly on its first 0 → 1 after a power-up, the way Orchard says Apple stores the stream "once per PMGR power-up" (claimed).

**A possible test, one variable, empty list first.** After `h2` (state 0, busy clear):
1. Switch GFX off: `pm_runtime_put_sync` or the genpd off path, then read PS back.
2. Switch it on (`pm_runtime_get_sync`; PS must read `0x3ff`).
3. Request state 0 again: poll busy, store `0x10`.
4. Then `+0x10`, `+0 = 0x40000000`, the end marker, `+0x20000 = 0`, `0x11`, as in run 11.

If that passes, repeat with the h7d one-entry list. This boot has not been run. GFX power-off has not been tried on J81 under Linux as far as these notes show, so it is the riskiest step. Read nothing from RGX while it is off.

## Not resolved

- What PMGR writes the provider's `+0x568` and `+0x570` produce. It is not decoded because the provider class is in another kext. The ADT gives the device (GFX, id 124) but not the register or bit.
- Whether the provider gate is reference-counted, so that probe on → start off is a real power-off. The call shape suggests yes (inferred).
- The Fender state at the `+0x20000` store. The last request is state 0 (code), but no capture of Apple's sequence exists.
- What Fender does with ConfigRAM when the override is released. It is not visible from host code.
- The meaning of `0x7a4d882` bit 2 and `0x7a4d87f`. They are set at probe from the provider's register-range count and from accelerator slot `0xa30`; their J81 values were not computed. On J81 the probe's first wake is the path request 8 found, which needs both.

## Files

- `t1-start-to-stream.tsv`: Q1, every step from the 1 → 0 request to the first stream store.
- `t2-override-store.tsv`: Q2, slot `0x60`, its callers, and the Fender register names.
- `t3-end-to-store.tsv`: Q3, from the end marker to the override store.
- `t4-first-vs-later.tsv`: Q4, the first wake, the boot path and the Linux runner side by side.
- `SHA256SUMS`.
