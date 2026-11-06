# J81 segment preflight failure

The five-entry selector-9 segment did not reach any bridge or GPC access.
The wrapper stopped after the watchdog armed because `/tmp/gpu-pmgr-peek`
was not staged in the fresh boot. The host therefore sent no PMGR, GPC, or
bridge acknowledgement. The supervisor intentionally left the watchdog
armed, and the USB network disappeared afterward; the resulting reset state
is not yet classified.

This is a failed-precondition run, not a GPU result. The segment must not be
retried in the same boot. A future attempt needs the PMGR peek helper staged
and hash-verified before starting the supervisor.
