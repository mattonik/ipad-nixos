# J81 PMGR page-5 cross-OS capture

The user authorized separate, potentially stalling reads. The probe and
limits are documented in [the preparation](probes/j81-page5/README.md).

## iOS `0x20e005000`

On 2026-11-10 a temporary 19H394 iPadOS boot ran the fixed `page5-0` module,
SHA-256 `c4c59cb31f5eb50ee358deba195284d0d47fb6ed8e0ebf94b4ab9b7f1cf46d5f`.
The private startup log records, in order:

```text
P1=000003ff G1=00000001 I=00070500
PAGE5-before
Q=00001010
... GPU firmware booted successfully (AGXFirmwareKextG4G)
```

The PMGR object's existing virtual read was called once, with region 0,
offset `0x5000` and instance 0 after the iOS RGX identity reads. In the
captured Pongo J81 ADT, region 0 maps to PMGR physical base `0x20e000000`;
the runtime iOS physical mapping is not independently verified. The returned
value is `0x00001010`, with bit 25 clear. It is a point-in-time sample after
identity, not proof of LLB execution, register meaning, or Linux's value.
No write was added. A successful boot after this read does not establish that
the read has no side effects.

Private source archive: `artifacts/live/private/ios-logarchive-j81-page5-0-01/`.

## iOS `0x20e005004`

A separate temporary boot used fixed module `page5-4`, SHA-256
`889c456e18abc334a8e8bff11bf69dd86e31a6f6d2b4b909a249aff8c5975745`.
It logged `P1=000003ff G1=00000001 I=00070500`, `PAGE5-before`, and
`Q=40000000`; GPU firmware startup was reported afterward. As with the first
read, this calls the existing PMGR method once after identity and uses the
Pongo ADT for the physical-base cross-reference. The `+0` and `+4` samples
are from different boots and must not be treated as an atomic pair.
Private archive: `artifacts/live/private/ios-logarchive-j81-page5-4-01/`.

## iOS `0x20e005008`

A third separate temporary boot used fixed module `page5-8`, SHA-256
`43629e805d0865b660f72b2e91d3f130dc0273b8e69d70461440d70d2fc6c37`.
It logged `P1=000003ff G1=00000001 I=00070500`, `PAGE5-before`, and
`Q=81480348`; GPU firmware startup was reported afterward. This is another
one-shot sample after identity, with the same mapping and limitations.
Private archive: `artifacts/live/private/ios-logarchive-j81-page5-8-01/`.

The three iOS values come from separate boots and are not an atomic snapshot.

## Linux `0x20e005000`

On a fresh cycle-payload Linux RAM boot, the exact kernel-notes hash and
J81 identity passed preflight. The one-shot module was staged and loaded;
after the host recorded and acknowledged the before-read checkpoint, it
returned `0x00001010`. The host recorded completion and watchdog disarm.
That equals the iOS `+0` sample, though the Linux read was on a separate
boot before an explicit GFX cycle, whereas the iOS sample followed GPU
identity. It does not establish matching state at the stalled read, prove
the block's meaning, or show that reading it has no side effects. No page-5
writes or RGX accesses were performed.

Capture: `artifacts/live/gpu/page5-linux-20261110-01/page5-0.log`. The
Linux `+4` and `+8` comparisons each require a fresh boot; the module is
deliberately pinned and one-shot.

## Linux `0x20e005004`: a sampled difference

On a second cycle-payload RAM boot, the same guarded one-shot and
watchdog-supervised procedure returned `0x00000000` at `0x20e005004` and
recorded watchdog disarm. The iOS sample from a separate boot was
`0x40000000`, a difference in bit 30. The Linux observation was taken
before an explicit GFX cycle or GPC initialization, while the iOS observation
was taken after GFX identity. This is a real difference between these samples,
not evidence of what changed the bit or whether it affects the GPU. The
block's semantics remain unknown, and no page-5 writes or RGX accesses were
performed. A useful follow-up is to sample `+4` after a previously tested
Linux GFX/GPC-only initialization on a fresh boot, with no core read, before
considering any modification of this register.

The inspected 15.8.8 LLB instruction at `0x1803907e0` clears only bit 0
of the value read from `+4`; it preserves bit 30 in the value it writes.
This instruction does not establish how bit 30 became 1 in the iOS sample,
whether it is writable, or whether replaying it would be meaningful.

Capture: `artifacts/live/gpu/page5-linux-20261110-01/page5-4.log`.

## Linux `0x20e005008`

On a third separate cycle-payload RAM boot, the same guarded procedure
returned `0x81480348` and recorded watchdog disarm. This equals the separate
iOS `+8` sample. Capture:
`artifacts/live/gpu/page5-linux-20261110-01/page5-8.log`.

Across these separate pre-GFX Linux boots and post-identity iOS boots, `+0`
and `+8` matched; `+4` differed only by bit 30. The snapshots are not atomic
and cannot establish causation or a safe write. The next useful control is
the previously tested GFX PMGR cycle, 66 bridge requests and GPC setup
without an RGX read, followed by a fresh one-shot `+4` sample.

## Linux `+4` after GFX and GPC control

On a fourth fresh Linux RAM boot, the `gpc-control` campaign passed
preflight, completed the PMGR cycle, reached all 66 bridge-store checkpoints,
and completed the existing GPC setup with its poll returning `1`. Both
watchdogs disarmed. The PMGR cycle device then reported runtime status
`active` and runtime usage `1`. The guarded page-5 one-shot returned
`0x00000000` at `0x20e005004`; its own watchdog disarmed and USB networking
remained available. No GPU-core identity read or page-5 write was made.

Thus the sampled bit-30 difference persisted after this Linux GFX/GPC-only
sequence. This reduces the likelihood that simply performing the tested
power/bridge/GPC sequence explains it. The iOS read still occurred after its
successful identity reads on another boot; the Linux read did not. Neither
the bit's semantics nor any causal role is established. The 66 bridge
checkpoints are not readback of all stores. An attempted additional
`gpu-pmgr-peek` emitted its pre-read checkpoint but was not acknowledged;
it did **not** provide a post-GPC PMGR readback, so `active`/usage are
software runtime-PM observations rather than a new raw PMGR measurement.

Private captures: `artifacts/live/gpu/page5-postgpc-20261110-01/`.

## iOS `+4` before GPC and identity

On another temporary 19H394 boot, the [early timing probe](probes/j81-page5early/README.md)
logged `PAGE5-early-before`, then `Q=00000000`, after the GFX clock-provider
call and before the caller's GPC and identity sequence. It subsequently
logged `P1=000003ff G1=00000001 I=00070500` and GPU firmware startup. The
early zero matches Linux's post-GPC zero; the earlier `0x40000000` iOS value
was sampled after identity on **a different boot**. The two iOS values do
not establish when or whether bit 30 changed within either boot. The
physical-address association, undocumented read side-effect caveat, and
object-lifetime limits remain as in the probe notes.

The useful next control is a same-boot, separately marked early and late
read of `+4`. Even a confirmed transition would not establish causality or
whether the bit is writable. Private archive:
`artifacts/live/private/ios-logarchive-j81-page5early-01/`.

## Paired iOS `+4` timing on one boot

On 2026-11-10, the [paired probe](probes/j81-page5pair/README.md) captured
both samples in the same temporary 19H394 boot. Its private log records:

```text
13:55:15.591 PAGE5-early-before
13:55:15.591 Q=00000000
13:55:15.600 P1=000003ff G1=00000001 I=00070500
13:55:15.600 PAGE5-before
13:55:15.600 Q=40000000
13:55:15.709 GPU firmware booted successfully (AGXFirmwareKextG4G)
```

Bit 30 was clear after the first GFX provider returned and set at the later
identity hook, approximately nine milliseconds later. This establishes a
same-boot difference in the values returned by the instrumented PMGR method;
it does not identify the operation or thread responsible, rule out a read
side effect, establish the bit's function, or prove the iOS runtime mapping
independently of the Pongo ADT. The corresponding Linux post-GPC sample was
zero on a different boot. No write is justified by these observations alone.
Private archive: `artifacts/live/private/ios-logarchive-j81-page5pair-01/`.

The [next-boundary analysis](2026-11-10-j81-page5-transition-next-boundary.md) identifies the existing successful GPC poll as an intermediate sampling point.

## Reduced middle probe: change observed by the GPC poll

On 2026-11-10 a temporary 19H394 boot ran the
[reduced middle probe](probes/j81-page5min/README.md), module SHA-256
`3ce3a82ecca142355244c81b0df315de49116d27c26459c35be0f5f1761a30ae`.
The private startup log records:

```text
PAGE5-early-before
Q=00000000
P1=000003ff G1=00000001 I=00070500
M=40000000
PAGE5-before
Q=40000000
... GPU firmware booted successfully (AGXFirmwareKextG4G)
```

`M` is the buffered read taken after the successful same-thread GPC poll
and before the caller's delay and identity dispatch; it is printed later at
the identity hook. The result therefore narrows the observed change to the
interval after the early clock-provider-return sample and by the successful
GPC poll. This includes the provider power request and GPC setup, but could
also include elapsed time, concurrent activity or a side effect of the early
read. It does not identify the bit's function or establish a causal link to
Linux's stalled RGX read. The iOS physical mapping is still inferred from the
Pongo ADT. The boot reported successful firmware startup; that does not prove
the reads had no side effects.

The user reported the screen restarting before iPadOS appeared. The captured
boot reached the GPU firmware success log, but the available log does not
establish whether an additional restart occurred or its cause. Private archive:
`artifacts/live/private/ios-logarchive-j81-page5min-01/`.

## Power-provider boundary: change observed during GPC interval

On 2026-11-10 a temporary 19H394 iPadOS boot ran the
[power-boundary probe](probes/j81-page5power/README.md), SHA-256
`7ebf0af4c97fe0a27688b0679661b28c7ef1c6de29fae6e1b6322d522c033351`.
The same startup log records:

```text
PAGE5-early-before
Q=00000000
P1=000003ff G1=00000001 I=00070500
T=00000000
M=40000000
PAGE5-before
Q=40000000
... GPU firmware booted successfully (AGXFirmwareKextG4G)
```

`T` was sampled after the power-provider call returned and before the
caller's GPC setup. `M` was sampled at successful GPC poll before the caller's
subsequent delay and identity reads. Both were buffered and printed later at
the identity hook; their log timestamps are not sampling times. The word
therefore differed between the post-power-provider and post-GPC-poll samples.
The interval contains GPC mapping and setup, state polling, elapsed time and
potential concurrent work; it does not prove which operation changed the
word, that the samples were free from read side effects, or that the bit
controls GPU access. The runtime iOS physical mapping remains inferred from
the Pongo ADT. GPU firmware startup was reported on the same boot.

The user reported a reboot before iPadOS appeared. The available log records
this successful probe boot, but does not establish whether another restart
occurred or why. Full private archive:
`artifacts/live/private/ios-logarchive-j81-page5power-01/`.

## GPC control boundary: transition after control sample

On 2026-11-10 a temporary 19H394 boot ran the
[control-boundary probe](probes/j81-page5control/README.md), SHA-256
`bbcbae242a2e254d1b7f12bd9764d07f03b8055b38863ca8c754711b00b26ca6`.
The same startup log records:

```text
PAGE5-early-before
Q=00000000
P1=000003ff G1=00000001 I=00070500
C=00000000
T=00000000
M=40000000
PAGE5-before
Q=40000000
... GPU firmware booted successfully (AGXFirmwareKextG4G)
```

`T` was sampled after the power-provider return; `C` was sampled after the
conditional GPC control-write site and before the state-request instruction; `M`
was sampled after a successful GPC poll and before identity. They were
buffered and logged in `C`, `T`, `M` order at identity, **not sampling order**.
The observed difference is between `C` and `M`, an interval containing the
`0x11` state request and polling. The probe does not establish that the conditional control write executed
or persisted. It also cannot distinguish a
state-request effect from elapsed time, a concurrent action, or effects of
the additional reads, and it does not establish that bit 30 controls GPU
readiness. Runtime iOS physical mapping is inferred from the Pongo ADT.
The same boot reported GPU firmware startup. Private archive:
`artifacts/live/private/ios-logarchive-j81-page5control-01/`.
