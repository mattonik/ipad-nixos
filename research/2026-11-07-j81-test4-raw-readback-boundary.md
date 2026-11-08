# J81 test4 raw capture: checkpoint versus readback

Offline audit of the five raw Linux captures; no hardware was accessed.

## Observed operation order

1. `clock-cycle-20261107-test4.log`: the host-gated read of PMGR `0x20e020320`
   returned `0x300` (target/actual 0, auto/reset 0). The one-shot PMGR cycle
   then returned `rc=0`. Its source (`kernel/gpu-pmgr-cycle/gpu-pmgr-cycle.c`)
   requires that initial state and performs runtime-PM get, put, get, leaving
   the final reference held. This exercises generic genpd power transitions;
   it does not capture each intermediate register transition.
2. `clock-table-20261107-test4.log`: PMGR readback was `0x3ff` (target/actual
   15). GPC state `0x201e01000` read as 0. The helper then issued selector 9's
   33 planned writes, in order, followed by selector 10's 33 writes. Every
   host ACK and `after-bridge-*` checkpoint arrived; the helper returned
   `rc=0` and disarmed its watchdog.
3. `gpc-init-20261107-test4.log`: PMGR again read `0x3ff`; GPC state initially
   read 0. The helper issued writes `0x201e10000 <- 0xffff0000`,
   `0x201e00000 <- 0x40000000`, and `0x201e01000 <- 0x11`. Its poll read
   returned state 1; the helper returned `rc=0` and disarmed its watchdog.
4. `postgpc-bridge-20261107-test4.log`: actual reads returned GPC state 1,
   GPC control `0x40000000`, bridge `0x201f00018 = 0x80010004`, and bridge
   `0x201f0001c = 0x00010001`; helper returned `rc=0`.
5. `core-revision-20261107-test4.log`: actual reads returned PMGR `0x3ff`
   twice (first with decoded fields), GPC state 1, and control `0x40000000`.
   It then emitted `before-gpu-revision address=0x201000020 width=32`; host
   sent `READ`, but no after-read, finished, or watchdog-disarm checkpoint
   appears. The capture therefore records an incomplete transaction, not its
   cause or eventual reset outcome.

## What the checkpoints establish

The bridge helper (`boot/gpu-bridge-once.c`) waits for host `ACCESS`, performs
a volatile 32-bit store, executes `__sync_synchronize()`, then prints the
value from its local plan buffer. It does **not** read the register back.
Thus all 66 `after-bridge-*` lines prove the helper progressed through all
planned store instructions/checkpoints in selector order; they do not prove
that all 66 values persisted in the target registers. Likewise,
`boot/gpu-gpc-init.c` prints the local requested value after each of its
three stores, so those three `after-*` values are not readbacks. Its initial
state and poll result are real volatile reads. The post-GPC capture reads two
bridge words. The read at `0x201f00018` matches selector 9's first table write
to that same address and value (`0x80010004`), so one table address/value pair
has readback evidence. The read at `0x201f0001c` is outside the table targets.
Of the 66 table operations, the other 65 have no readback evidence.

This distinction does not contradict the result note's wording that writes
"reached their after-write checkpoints." Avoid shortening that phrase to
"all 66 registers read back" or "all 66 writes verified." The staged plan's
offline hash/content match establishes which constants were supplied, not
hardware readback.

## iOS 8.1 sequence comparison

Static 12B410 evidence in
[`2026-11-07-j81-gpc-provider-object-binding.md`](2026-11-07-j81-gpc-provider-object-binding.md)
places provider clock and power calls before Apple's GPC setup. The J81
provider selects gate ID `0x7c`; the PMGR state index is separately 100.
Apple's clock callback is a per-device reference transition: on an enable
edge it applies PMGR index 100 to state 15 and polls, then applies selector 9
and selector 10, then updates the flag-bit-2 SoC-busy count. Apple's power
callback consumes/reports a saved `WAS_PWRGATED` bit; it is not a direct
power-state read or raw power-on. The G4G probe then sets up GPC, invokes the
identity read, and only afterward performs state-zero cleanup and conditional
provider release. Test4 manually used generic genpd, replayed table stores,
and initialized GPC, but did not execute Apple's provider callbacks or busy
bookkeeping. The later Apple cleanup is after identity and is not evidence for
the cause of the pre-completion test4 read.

Sources: the five files under `artifacts/live/gpu/*-20261107-test4.log`,
`boot/gpu-bridge-once.c`, `boot/gpu-gpc-init.c`,
`boot/gpu-core-revision-once.c`, and `kernel/gpu-pmgr-cycle/gpu-pmgr-cycle.c`.
