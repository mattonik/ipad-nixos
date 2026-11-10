# J81 in-kernel GPC poll and page-5 sample (prepared, not run)

Follows the [build-agent handoff](2026-11-10-j81-next-build-agent-handoff.md).
The earlier [timed userspace probe](2026-11-10-j81-linux-gpc-page5-timed-probe.md)
sampled page 5 through a sysfs call after the GPC poll and could not bound the
poll-to-read interval. This test moves the GPC setup, the poll and the page-5
load into one kernel function. It is an experiment about timing only. It never
writes page 5 and never touches the GPU core.

## What runs on the device

`kernel/gpc-page5-kpoll/gpc-page5-kpoll.c` (module `gpc_page5_kpoll`, required
parameter `mode=immediate|paired|delayed`) creates
`/sys/devices/j81-gpc-page5-kpoll/` with two one-shot, root-only attributes:

- `gpc_state`: one `readl` of `0x201e01000`.
- `batch`: refuses (`-EINVAL`) unless `gpc_state` was read and was `0`. Then:

```text
writel(0xffff0000, GPC+0x10000); mb();
writel(0x40000000, GPC+0x0);     mb();
local_irq_save
  t_prewrite  = ktime_get_raw_fast_ns()
  writel(0x11, GPC+0x1000); mb();
  t_postwrite = ktime_get_raw_fast_ns()
local_irq_restore
up to 1000 times:
  local_irq_save
    t_poll = ktime_get_raw_fast_ns()
    state  = readl(GPC+0x1000)
    if busy bit 4 clear and (state & 0x1f) == 1:
      immediate, paired: first = readl(PAGE5+4); t_first = ktime_get_raw_fast_ns()
      paired, delayed:   udelay(100); later = readl(PAGE5+4); t_later = ktime_get_raw_fast_ns()
  local_irq_restore
  if busy: usleep_range(10, 20)
```

The stores, their order and values are the ones the userspace probes used.
`mb()` repeats the full barrier those probes placed after each store. The poll
keeps the validated pacing (at least 10 µs between polls, at most 1000 polls,
so at least 10 ms before giving up); the kernel sleep has no 50 µs userspace
timer slack, so polls are likely closer together than before. That is a
difference from the validated loop, not a measured property.

Output is one line. Success:

```text
result=ok mode=M raw=0x…  polls=N prewrite_ns=A postwrite_ns=B first_valid=0|1 first=0x… first_ns=C later_valid=0|1 later=0x… later_ns=D
```

Failure (busy for all 1000 polls, or busy clear with a state other than 1)
reports the last raw poll and the count and performs no page-5 read:

```text
result=poll-failed mode=M raw=0x… polls=N
```

### What the numbers bound

All four are differences of `ktime_get_raw_fast_ns()` (CLOCK_MONOTONIC_RAW,
read from the clocksource the preflight prints). Each is relative to `t_poll`,
the stamp taken just before the successful poll load.

- `first_ns = t_first - t_poll`. Both the poll load and the first page-5 load
  lie between these two stamps and local interrupts are masked throughout, so
  the load-to-load interval is **less than** `first_ns`. Between the two loads
  the source has only the two state tests. The compiled instruction sequence
  is recorded below after the build.
- `later_ns = t_later - t_poll`. Same bracket for the later load. It includes
  `udelay(100)`, so it is at least 100000.
- `postwrite_ns = t_poll - t_postwrite` and `prewrite_ns = t_poll - t_prewrite`.
  The `0x11` store lies between the two write stamps, so the store-to-poll-load
  interval is **more than** `postwrite_ns` and **less than**
  `prewrite_ns + first_ns` (or `+ later_ns` in delayed mode).

Limits: masking local interrupts stops preemption and IRQs on this CPU only.
FIQ, SError, the other two cores, bus latency and the time the hardware takes
to act on a store are not controlled or measured. The fast clock accessor can
be slightly off across a timekeeper update. These are software timestamps, not
hard real-time measurements. The intervals say when the CPU issued the loads,
not when the device sampled its state.

### Modes and the repeated-read control

| mode | page-5 loads | purpose |
| --- | --- | --- |
| `immediate` | one, right after the poll | the H1/H2 question with the fewest accesses |
| `paired` | one right after the poll, one about 100 µs later | H1 on one boot (set, then clear) |
| `delayed` | one, about 100 µs after the poll | control for the first read in `paired` |

Each mode needs its own fresh boot. If `paired` and `delayed` disagree about
the later value, that shows sensitivity to the first read or to timing; it does
not prove a destructive read. A first sample of `0` argues against H1 only at
that instant.

### Mappings and ownership

- GPC `0x201e00000 + 0x11000`: no node in the J81 Linux device tree and no
  driver claims it. Earlier probes used `/dev/mem`; the module uses `ioremap`.
- Page 5 `0x20e005000 + 0x1000`: inside the PMGR node's range. The module adds
  a second mapping of that page, as `page5-read-once` did, and only loads `+4`.
  It does not go through the PMGR driver or its regmap.

Both are mapped at module load, before any device access. A failed mapping
fails the load and nothing is written. The module has no exit path; it and the
two mappings stay until reboot.

Read side effects are unknown. Page 5 `+4` has been read once per boot on
Linux twice without a hang (the standalone read and the timed probe). It has
not been read twice on one boot, and not within nanoseconds of the GPC poll.

## Supervision and what a stall loses

`boot/gpu-gpc-page5-kpoll-run.sh` checks, before loading the module: boot ID,
`7.3.0-rc1`/aarch64, module hash, `gpu-pmgr-peek` hash, kernel notes hash,
cycle-module build ID, J81 model and compatible, active runtime lease with
usage 1, RAM root with no block mounts, no earlier one-shot markers, and that
neither page-5 module is loaded. It then runs under the existing fail-closed
watchdog supervisor (new mode `--gpc-page5-kpoll <module-sha256> <boot-id> <mode>`):

1. PMGR state read (`gpu-pmgr-peek`), host must see `0x3ff`.
2. `gpc_state` read, host must see `0`.
3. `stage=before-gpc-page5-kpoll … mode=M`. The host writes it to disk, syncs
   and only then acknowledges. This is the pre-batch marker.
4. `checkpoint=before-kernel-batch`, then the batch. Nothing is reported from
   inside the batch, so that logging cannot sit between the poll and the read.
5. The result line, host acknowledgement, watchdog disarm.

If the device stalls inside the batch, **every value from the batch is lost**,
including the poll count and a first sample that may already have been taken.
The log then ends at step 3 or 4 and says only that the batch started. The
watchdog is not fed, so the device should reset after 20 s; recovery is the
usual DFU and fresh boot. A missing result is never a zero. On a poll failure
the raw value and count are printed, the supervisor stays fail-closed and the
device resets.

Host side: `boot/gpu_gpc_page5_kpoll_capture.py` (strict order and parsing) and
`boot/j81_gpc_page5_kpoll_campaign.py <mode> <new-log-dir>` (base bundle check,
RAM-boot preflight, PMGR cycle, 66 bridge stores, staging, capture). The
campaign refuses to run until the three file hashes are pinned in it.

## Host tests

`tools/check_offline.py` runs them all.

- `kernel/test_gpc_page5_kpoll.py`: compiles the module source against stubs.
  Store addresses, values and order; page-5 load directly after the successful
  poll with interrupts masked and no sleep between; each mode's load count;
  timing brackets; one-shot on both attributes; batch refused before the state
  read and after a non-zero state; each failed mapping and failed attribute;
  busy timeout and invalid state report raw and count and leave page 5 alone;
  wrong machine and unknown mode.
- `boot/test_gpu_gpc_page5_kpoll_run.py`: guard order in the wrapper, argument
  checks, missing or wrong acknowledgement, non-zero GPC state, poll failure,
  mode mismatch, sysfs read error.
- `boot/test_gpu_watchdog_supervisor.py`: new mode end to end with real pipes,
  failed poll leaves the watchdog armed, bad arguments.
- `boot/test_gpu_gpc_page5_kpoll_capture.py`: all modes, malformed results,
  stall after the marker, poll failure, wrong mode, lost host, missing disarm.
- `boot/test_j81_gpc_page5_kpoll_campaign.py`: unpinned or corrupt bundle,
  staging only after the bridge stage, boot ID and mode passed through, reused
  log directory, failed bridge stage.
- `boot/test_j81_preflight.py`: new `gpc-page5-kpoll` profile (kernel notes,
  release, cycle-payload device tree, RAM root, watchdog, no GPU test module
  loaded, no one-shot marker). Missing facts are a NO-GO.

These tests do not show what the hardware does.

## Build record

To be completed after the build: module and supervisor store paths, SHA-256,
vermagic, kernel notes check, and the instructions between the two loads.
