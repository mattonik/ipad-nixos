# J81 Linux core-read-off control: the compressed batch RETURNS; the stall is the core read

2026-11-21, one shot, logs (private) `artifacts/live/private/j81-linux-nocore-results-20261121-run1/`. Plan:
[2026-11-21-j81-nocore-control-plan.md](2026-11-21-j81-nocore-control-plan.md). Module `4827876e...` (compressed module, core load compiled out).

## Result
- Campaign exit 0, watchdog disarmed, iPad still up afterwards (ping OK). Single GFX activation confirmed in `gfx-request.log` (one request, `old=00000300 request=0000000f`).
- Both gates passed (wrapper dry run `stage=before-pmgr-read`, `rc=1`; clean state afterwards).
- Kernel batch (66 bridge stores, GPC request, poll, page-5 sample, irq-off, `ioremap_np`) **returned**:
  `result=ok mode=immediate raw=0x00000001 polls=28 prewrite_ns=286041 postwrite_ns=285208 first=0x40000000 first_ns=1000`.
  GPC state 1 after 28 polls (about 286 us after the request store, iPadOS 289 us); page 5 +4 = 0x40000000 (bit 30 set), loaded about 1 us after the poll load.
- `core` file: `core_valid=0 reason=core-read-disabled` (as designed). `status 0x2d100` = 1, `vm_sram 0x23004` = 0x170 in the final snapshot, as on iPadOS.

## Reading
Run 3 (same module with the core load) hung in the batch; this control (without it) completes normally. So the stall in run 3 is the core load at 0x201000020
itself, not the in-kernel bridge/GPC/page-5 sequence. Together with the earlier runs, the core read hangs on Linux whether it follows the other stages by seconds
(userspace tools) or by about a microsecond (in-kernel, irq-off, non-posted), with one GFX activation or three. Timing and mapping attributes are therefore not the cause.
Everything we can read at that point matches iPadOS. The missing ingredient is not in the registers we compare; candidates stay the unmodelled provider side effects and state outside
PMGR/GPC/bridges (clock/reset consumers, SPR/SMC/SEP), and retention of the individual bridge words (unsampled).
Next ideas (agent ranks 2 and 3): read back the same bridge words on both OSes after the stores and after GPC; compare PS and MiscACG on both sides of the activation.
