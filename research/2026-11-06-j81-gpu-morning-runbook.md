# J81 GPU morning runbook

Overnight offline work completed the following artifacts:

* `tools/gpu_ldr_inspect.py --report` — validated META metadata;
* `tools/gpu_g4g_host_plan.py` — execution-disabled host plan;
* `tools/gpu_g4g_loader_compare.py` — Apple/Linux semantic differences;
* `tools/gpu_g4g_apple_model.py` — Apple bucket and zero policy;
* `tools/gpu_g4g_loader_sim.py` — deterministic, MMIO-free operation trace.

The real 8.1 image has been processed and the ignored captures are under
`artifacts/live/private/gpu-observations/`:

```
g4g81-host-report.json
g4g81-host-plan.json
g4g81-loader-compare.json
g4g81-apple-model.json
g4g81-sim.json
```

## Before touching the iPad

Run the host-only checks:

```
cd /Users/martinp/Work/Sandbox/ipadlinux/ipad-nixos
python3 tools/check_offline.py
```

Expected result: 78 passed, 7 unavailable-input skips. Do not treat skipped
source checks as evidence that the firmware adapter is complete.

## Current decision gate

Do not upload the G4G image yet. The report still marks these blockers:

1. Apple low/global and alias ranges are not assigned to Linux `FW_CODE` or
   `FW_DATA` objects;
2. Apple’s second address view and shared-memory lifetime are unresolved;
3. thread-start and firmware-alive ownership are unresolved.

The first real-device action should remain the existing guarded PMGR identity
and runtime-state preflight. It must not add a bridge write, GPC access,
firmware upload, or renderer. A failed or missing preflight means stop and use
a fresh verified RAM boot.

## What is still required for a hardware firmware test

The next code change must make the simulator produce a complete Linux firmware
object map with no `unresolved` buckets. After that comparison is clean, build
a separate firmware-alive payload with:

* a bounded watchdog around every stage;
* no render jobs or display changes;
* no automatic retry after a timeout;
* a documented recovery path to iOS.

Only then should an operator-present test be considered. The current overnight
artifacts are safe because they never allocate, upload, execute, or access
GPU/GPC MMIO.

