# J81 iPadOS tuner: later snapshot result

On 2026-11-11 the temporary 19H394 [later-snapshot probe](probes/j81-tuner-late/README.md)
(module SHA-256 `7843b689fa48a3f9f19023ea7751166caee08457513ceffca18de56579c019ab`)
booted iPadOS and its startup archive was retrieved. The latest matching boot
logged at 15:03:29.094 local time:

```text
P1=000003ff G1=00000001 I=00070500
U=00000000:00000000:00000000:00000000
```

At 15:03:29.202, the original `GPU firmware booted successfully
(AGXFirmwareKextG4G)` message was followed by:

```text
V=00000000:00000000:00000000:00000000
```

Both early and later global entry/exit controls were zero; no window event or
reservation failure was recorded. The original success message was retained
and the added later export executed. The log timestamps are about 108 ms apart;
this is not a measured physical interval between register accesses.

The result does not establish that the tuner policy never ran: the candidate
handler and runtime dispatch remain unproven, and publication/window races
and later activity remain possible. In particular no positive tuner entry or
exit was captured by the later snapshot. It does not justify replaying an MCC
or GPU write on Linux. The query that showed the tuner service matched at boot
was made on the previous tuner-probe boot, not this boot.

Private source archive and decoded log:
`artifacts/live/private/ios-logarchive-j81-tunerlate-01/`. Full device logs
may contain personal information; no extra MMIO was added by the probe.
