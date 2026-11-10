# J81 iOS/Linux PMGR and GPC poll comparison

On 2026-11-10 the user booted the temporary 19H394
[poll-comparison probe](probes/j81-pollcompare/README.md). The iPad returned
to iPadOS and the startup log was collected privately. The instrumented boot
reported:

```text
AGXk: Starting GPU driver. Available features: P1=000003ff G1=00000001 I=00070500
AGXk: Probing - Detected G4G A1 [...]
AGXk: ... GPU firmware booted successfully (AGXFirmwareKextG4G)
```

`P1` positively marks an existing iOS PMGR poll read for region 0, offset
`0x20320`, instance 0, mask/expected `0xf0`, in the GFX provider thread.
Its last matching sampled raw word was `0x000003ff`. `G1` marks the
existing same-thread GPC poll returning with bit 4 clear; its raw sample was
`0x00000001`. `I` is the already-existing first RGX identity read, observed
after both identity loads completed. There were no extra MMIO accesses from
the probe. The prior provider-window capture in this boot logged `B0`.

The separate Linux host-paced campaign read PMGR `0x000003ff`, GPC state
`0x00000001`, and GPC control `0x40000000` before its acknowledged RGX
identity-read checkpoint; no identity result followed. The iOS PMGR and GPC
samples therefore match the two corresponding Linux raw values, across
different instrumented boots and at related but not identical instants.
This capture did **not** read iOS GPC control. It does not prove that the
unmeasured clocks, resets, fabric, mappings, boot history, timing or bridge
values were equivalent, or that Linux's load instruction executed after its
checkpoint. It makes a difference in these two sampled words a less likely
explanation for the stall; it does not identify the cause or establish Linux
GPU functionality.

The private archive and filtered log are under
`artifacts/live/private/ios-logarchive-j81-pollcompare-01/`; full device
logs may contain personal information and must not be published. Linux
comparison: [host-paced campaign](2026-11-09-j81-campaign-paced-result.md).
