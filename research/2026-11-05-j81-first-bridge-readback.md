# J81 first bridge write readback

In the same boot as the guarded first write, the supervised read-only probe
read `0x201f00018` as `0x80010004`. This matches the value written earlier in
the boot. GPC state remained readable, PMGR stayed active with runtime usage
`1`, the watchdog disarmed normally, and the iPad remained responsive.

This confirms that the first write reached a readable register state. It does
not establish that the remaining bridge table writes are safe, nor that GPC
initialization or a GPU ID read will work. No further GPU access was attempted
in this boot.

Private capture:
`artifacts/live/private/gpu-observations/2026-11-05-bridge-peek-after-first-write.log`

Capture SHA-256:
`477678cd6fb1060bffb7e4a4991ce97e63e679e42590149671d269bdcb309234`
