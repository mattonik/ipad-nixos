# J81 live preflight after bridge readback

The attached iPad is still running the diagnostic Linux image and answers on
the USB recovery shell. Read-only preflight returned:

```
Linux 7.3.0-rc1 aarch64
Apple iPad Air 2 (Wi-Fi)
/sys/devices/gpu-pmgr-once/power/runtime_status = active
/sys/devices/gpu-pmgr-once/power/runtime_usage = 1
/tmp/gpu-bridge-peek.once exists
```

Only the telnet recovery shell was used because the RAM image's SSH host key
does not match the repository pin. No new MMIO, PMGR transition, module load,
or write was issued. The existing bridge-peek one-shot guard remains consumed,
so the readback cannot be accidentally repeated in this boot.

Next hardware use requires a fresh verified boot and a reviewed read-only
operation; this session is otherwise left untouched.
