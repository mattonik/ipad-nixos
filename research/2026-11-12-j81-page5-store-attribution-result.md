# J81 page-5 writer attribution result

On 2026-11-12 a temporary 19H394 iPadOS boot ran the
[attribution probe](probes/j81-page5attribution/README.md), module SHA-256
`eb4cd3011f031617f030ac83517e18457375ee106fbf35e5836901384c38127a`.
The device booted and the private archive was retrieved. The relevant record
sequence was:

```text
PAGE5-early-before
Q=00000000
P1=000003ff G1=00000001 I=00070500
Y=00000001:00000001:00000000:00000000:00000000:00000000:00000000:00000000:00000000:00000001
Z=00000002:00000001:00000002:00000000
W=00000502:00000502:53545349
W=00000602:00000602:53545242
C=00000000
T=00000000
M=40000000
PAGE5-before
Q=40000000
```

The GPU driver subsequently reported G4G A1 and successful firmware boot.
The early, C and T samples were zero; M and the late sample had bit 30 set.
The injected reads and hooks can perturb timing; logs do not establish the
exact physical moment or cause of transition.

`Y` reports a captured target address, bridge-store site seen, zero in-flight
counts at both sampled boundaries and export, no recorded accounting failure,
and target present before C. `Z` reports phase 2, ordinary-store site seen,
two reservations and no recorded overflow. Both `W` records are the tagged
ordinary and bridge synthetic metadata controls, respectively. They validate
those matching/publication paths without performing the target stores; neither
is a real hardware write. No real matching `W` record or `W=UNREADY` appeared
in this captured export.

This improves coverage over the earlier ordinary-only trace: both candidate
store sites were reached, both synthetic controls made it through export, and
the target effective virtual address was captured before C. It does **not**
prove hardware set bit 30 or exclude a CPU writer. A writer can be delayed
before accounting, access the same physical word through another virtual
alias, use another instruction/site/width, or run outside the observed window.
DMA, firmware, independent hardware activity, instrumentation effects and
inferred mapping/object lifetime remain possible. A completed CPU store would
not by itself prove device acceptance or causation either. This result does
not justify forcing the bit or repeating the stalled Linux core read.

Private archive and filtered kernel log:
`artifacts/live/private/ios-logarchive-j81-page5attribution-01/`.
