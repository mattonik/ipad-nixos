# J81 PMGR power-test gate

Date: 2026-11-06

The requested guarded GFX power test was attempted against the running
`result-hoolock-control` Linux image. The wrapper verified the staged helper
hashes and the live kernel-notes hash, then attempted to insert the one-shot
consumer module. The kernel rejected it before `module_init`:

```
module gpu_pmgr_once: .gnu.linkonce.this_module section size must match the kernel's built struct module size at run time
```

The module never appeared under `/sys/module/gpu_pmgr_once`, the consumer
device was never created, and the wrapper never reached its PMGR checkpoint or
`POWER` acknowledgement. Therefore no PMGR write, runtime-PM request, GFX
power transition, GPU/GPC access, firmware upload, or rendering occurred.

The earlier read-only baseline remains valid (`0x20e020320 = 0x00000300`).
This image needs a module rebuilt against its exact kernel build/configuration
before another power test is considered. Do not retry the incompatible module
in this boot.

## Result

- Guarded power test: **blocked before hardware access**.
- Device state: unchanged by this attempt; Linux remains reachable.
- Next offline task: reproduce the exact kernel module build and verify the
  resulting `.this_module` ABI before any new hardware attempt.

