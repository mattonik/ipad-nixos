# J81 live read-only snapshot

Date: 2026-11-07 09:43 CET

Read-only checks over the existing USB network link reached the running iPad.
The link answered ping; TCP ports 22 and 23 accepted connections.

```text
model: Apple iPad Air 2 (Wi-Fi)
kernel: Linux 7.3.0-rc1 aarch64
boot_id: e9d7c9ed-8d71-49c3-a271-31a9dd8a74ac
PMGR runtime_status: active
PMGR runtime_usage: 1
consumed one-shot guard: /tmp/gpu-gpc-peek.once
```

The GPC peek guard is already present in this boot. Its runner performs
read-only MMIO reads that may hang, and its one-shot guard prevents repeating
them. No probe or MMIO access, module load, payload transfer, write, or reboot
was attempted. No sensitive device data was recorded.
