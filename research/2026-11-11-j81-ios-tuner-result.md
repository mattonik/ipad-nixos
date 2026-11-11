# J81 iPadOS SoC-tuner observation: inconclusive

On 2026-11-11 the temporary 19H394 [tuner probe](probes/j81-tuner/README.md)
(module SHA-256 `58188332889230879ebe922c222031cc09c1479def4b6dc14700eebc1907f694`)
booted iPadOS and the startup archive was retrieved. The latest matching boot
at 14:42:43 local time logged:

```text
P1=000003ff G1=00000001 I=00070500
U=00000000:00000000:00000000:00000000
```

The first line confirms that the inherited PMGR and GPC poll hooks and the
post-identity logging path ran. `U` means no policy entry or return was
recorded in the window, no bounded-reservation failure was recorded, and
neither tuner hook's global positive control was observed before output. The
GPU driver subsequently reported G4G A1 and successful firmware boot.

**This does not establish that the SoC-tuner policy was absent.** The
instrumented implementation may not have been reached before the output,
runtime dispatch may have selected another path, or the event may not have
been observable in the chosen window; phase and publication races also remain.
The zero positive controls do not validate the tuner hook's runtime coverage.
The capture neither establishes a missing Linux callback nor justifies a new
memory-controller or GPU-register write.

The private raw capture and filtered log are at
`artifacts/live/private/ios-logarchive-j81-tuner-01/`. Full device archives
can contain personal data and must not be published. No additional MMIO read
or write was added by this probe.
