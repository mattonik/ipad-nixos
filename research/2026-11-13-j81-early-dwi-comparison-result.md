# J81 early DWI comparison: control and hold results

On 2026-11-13 the paired probe's control payload booted Linux on J81. The
control combined-image SHA-256 was
`c4ff7308eb9e7f5932e317fd78590e79713f353cb182a19e871de896562684f7`;
the host verifier passed, `/proc/cmdline` had `j81_dwi_hold=0`, and the iPad
reached its dashboard and answered over USB. Its private full kernel log and
sample are at `artifacts/live/private/j81-dwi-early-control-20261113/`.

The kernel log reported:

```text
0.062464 probe-before raw=000000ff ret=0
0.062486 probe-after  raw=000000ff ret=0
0.730837 genpd: Not disabling unused power domains
0.734911 off-before   raw=000000ff ret=0
0.741410 off-result   ret=0
0.746809 off-after    raw=00000200 ret=0
```

The later, acknowledged read-only sample on the same boot returned DWI
`0x20e020120 = 0x200`, PMGR `0x20e02300c = 0`, and page-5
`0x20e005004 = 0`; the sampler reported completion. No GPC request, GPU-core
read, PMU access or manual domain write was made by this comparison.

This directly observes a successful DWI PMGR power-off callback in the
instrumented control boot despite `pd_ignore_unused`; it does not by itself
establish which genpd call site invoked the callback or what powered DWI
before probe. It does not establish a GPU rail voltage or why the GPU stalls.
The instrumentation adds reads and logging that can alter timing.

## Paired hold boot

The separately checksum-verified hold image
`24c43c226656fea6d5eef3ab2ca4ae46f550672a5763dd85bede8bbbe49e09ce`
booted to the dashboard; `/proc/cmdline` contained `j81_dwi_hold=1` and the
iPad answered over USB. The private kernel log and sample are under
`artifacts/live/private/j81-dwi-early-hold-20261113/`.

```text
0.062440 probe-before raw=000000ff ret=0
0.062462 probe-after  raw=000000ff ret=0
0.743312 genpd: Not disabling unused power domains
0.747539 off-before   raw=000000ff ret=0
0.753344 off-rejected ret=-16
```

The same acknowledged sampler on this fresh boot returned DWI `0xff`,
`0x2300c = 0`, and page-5 `+4 = 0`; it reported completion. No GPC request,
GPU-core read, PMU access or manual domain write was made by this comparison.

| Observation | Control | Hold |
| --- | --- | --- |
| DWI at probe entry and after probe | `0xff`, `0xff` | `0xff`, `0xff` |
| DWI power-off callback | succeeded, read back `0x200` | rejected with `-EBUSY` |
| Later DWI read | `0x200` | `0xff` |
| Later PMGR `0x2300c`, page-5 `+4` | `0`, `0` | `0`, `0` |

The controlled pair supports the conclusion that rejecting Linux's DWI
power-off callback maintained the sampled on state in this hold boot; the
same callback successfully turned DWI off in the control. These are discrete
samples, not continuous monitoring; automatic gating, other writers and earlier
boot stages remain outside this proof. The probe's extra logging can affect
timing. With no GPC request, the equal page-5 values do not test GPU startup.
The next discriminating comparison is a separately reviewed GPC sequence on
matched boots with and without the early hold, not an immediate GPU-core read.
