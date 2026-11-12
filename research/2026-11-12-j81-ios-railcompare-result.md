# J81 iPadOS PMGR `0x2300c` comparison

On 2026-11-12 a temporary iPadOS 15.8.5 / 19H394 boot ran the
[two-read probe](probes/j81-railcompare/README.md), module SHA-256
`5823515aa28d7345d50c998c13d9dcc0d684f2146729106166db40de740cfaaf`.
The private kernel archive records:

```text
PAGE5-early-before
Q=00000000
P1=000003ff G1=00000001 I=00070500
PAGE5-before
Q=00000164
... GPU firmware booted successfully (AGXFirmwareKextG4G)
```

The labels are inherited from the page-5 probe; both `Q` values here are
for PMGR reader region 0, offset `0x2300c`, not page 5. The first reading
was after the GFX provider returned and before the GPC/identity sequence;
the second was after GPU identity. Physical `0x20e02300c` is inferred from
the captured ADT/registry resource cross-reference, not independently
verified from the runtime iOS mapping. The object lifetime and method
binding remain inferred. iPadOS reached its Home screen and its GPU driver
reported firmware startup; this is not a rendering test.

On the prior [DWI-first Linux boot](2026-11-11-j81-dwi-gpu-comparison-result.md),
the same physical-address cross-reference was `0` before the GPC campaign
and `0x164` after it and about ten seconds later. Thus these samples show
the same before/after values across the two systems. The boundaries,
instrumentation and boots differ; the iOS reads do not pinpoint when the
change occurred or prove the GPC request caused it.

This result reduces the priority of this word as a direct cross-OS
discriminator. It does not establish its field semantics, PMU row identity,
physical rail or actual voltage; nor does it prove the PMU received the
same request or that other power/clock/reset states match. Linux page-5 bit
30 was clear in its separate capture, while the iOS page-5 bit was set in
other captured boots. No PMU or page-5 write and no Linux GPU-core read
follows from this result.

Private archive and filtered kernel log:
`artifacts/live/private/ios-logarchive-j81-railcompare-01/`.
