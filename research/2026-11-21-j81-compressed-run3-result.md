# J81 compressed-timing run 3: the batch started and never returned (watchdog reset)

2026-11-21, one shot, boot `artifacts/live/private/j81-linux-compressed-results-20261121-run3/`. Plan:
[2026-11-21-j81-compressed-timing-plan.md](2026-11-21-j81-compressed-timing-plan.md). Earlier attempts (run 1, 2) were harness
failures, see their notes; this is the first run in which the compressed module executed.

## What happened

- PMGR writes, single GFX activation (`gfx-request.log`: exactly one request, `old=00000300 request=0000000f`), snapshot A: all as before.
- Wrapper dry run passed (`stage=before-pmgr-read`, `rc=1`); the module `be51efa4...` loaded (the wrapper reached `gpc_state`
  = `0x00000000`, so `__ioremap_prot`/`ioremap_np` resolved and all five mappings succeeded).
- `kpoll.log` ends with `stage=before-gpc-page5-kpoll ... mode=immediate`, `READ`, `checkpoint=before-kernel-batch`. The kernel
  batch never returned: 20 s later the supervisor's watchdog reset the iPad. `compressed-result.txt`: "no result".

## Reading

The compressed in-kernel sequence (66 bridge stores, GPC request, poll, page-5 sample, core read, all irq-off, non-posted
mappings, microseconds apart) **also hangs**. So the seconds-apart timing of the earlier stages, and the posted-vs-non-posted
mapping of the userspace tools, are not what makes the core read hang on Linux.

Caveat: a hang cannot be located. Bridge writes and the GPC poll each worked in earlier runs, but never in this in-kernel,
irq-off, nGnRnE form; the core read at 0x201000020 is the prime suspect, not proven. A discriminating follow-up is a build of the
same module with the core read disabled (module parameter, batch ends after the page-5 sample): if that returns normally the
hang is the core read. It costs one build and one boot cycle.

State at the hang matches iPadOS on everything readable; remaining candidates: unmodeled provider side effects not visible in
PMGR/GPC/bridge registers, and something outside what we compare (clocks/PLL consumers, other SoC blocks, SPR/SMC/SEP).
