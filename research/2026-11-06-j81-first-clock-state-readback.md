# J81 first clock-state bridge readback

Date: 2026-11-06

On a fresh test payload, the first selector-9 pair was written under the
existing 20-second watchdog and then checked by a separate watchdog-
supervised readback:

```
PMGR actual before write       15
GPC state before write         0
write                          0x201f00018 <- 0x80010004
GPC state after write          0
bridge readback                0x201f00018 -> 0x80010004
watchdogs                      disarmed normally
```

The private transcripts are:

* `artifacts/live/private/gpu-observations/2026-11-06-gpu-bridge-first-02.log`
* `artifacts/live/private/gpu-observations/2026-11-06-gpu-bridge-peek-after-first-02.log`

The iPad remained responsive, with the PMGR consumer still `active` and
runtime usage `1`. This confirms the first recovered bridge window is mapped,
the first pair write is retained, and the readback path works. It does **not**
raise GPC state from 0, so it is not evidence that the clock-state action is
complete or that subsequent pairs are safe. No second bridge pair, GPC
control write, GPU ID read, firmware, or rendering was attempted.

