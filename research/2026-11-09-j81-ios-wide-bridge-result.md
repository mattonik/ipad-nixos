# J81 iOS 15.8.5: wider bridge and GFX cached-state result

> Correction, 2026-11-10: the writer filter's `w4 == 15` condition tested
> a PMGR instance index, not the requested power state. Its empty result
> cannot establish that selector 9/10 writes were absent. See the
> [dispatcher capture](2026-11-10-j81-ios-dispatch-capture-result.md).

2026-11-09. The user placed the iPad in DFU and ran the temporary rootless
palera1n boot with the [wide probe](2026-11-09-j81-ios-wide-bridge-probe.md),
module SHA-256
`395d32ff92b017434909eb020e6919c28ff5c227770dfc0cb50a55ffed239f20`.
The iPad returned to iPadOS; after unlocking, its log archive was retrieved.

On boot UUID `4064DE59-929C-4FBC-BDBC-166CBC672E2D`, the filtered log records:

```
AGXk: Starting GPU driver. Available features: release
AGXk: Starting GPU driver. Available features: B0 D1:00000000>0000000f
AGXk: Probing - Detected G4G A1 [...]
AGXk: ... GPU firmware booted successfully (AGXFirmwareKextG4G)
```

`D1` is a positive observation of the GFX device-ID `0x7c` comparison in
ApplePMGR's state-change callback. It observed cached **software** state 0
and requested state 15. It does **not** measure the PMGR actual-state nibble,
and it does not show why the cached state was zero. Because the values are
unequal, the hypothesis that the callback skipped its transition solely
because its cached and requested states were equal is not consistent with
this observation.

`B0` with no following `09:` or `0a:` tokens means the buffer drained with
no overflow and no recorded writer dispatch matching selectors 9/10 and
requested state argument 15, from after KPF installation and through the
first G4G clock-provider return. This is evidence that the clock and decision
instrumentation ran and the buffer reported zero matching records. The
writer hook itself lacks a separate positive on-device control. The result is
not a proof that iOS made no bridge writes at all: the probe does not cover
iBoot/PongoOS, other writer functions, alternate selectors/states, or direct
MMIO by other components. Nor does it establish hardware register values.

The driver later reported G4G identification and GPU firmware boot success
in the same boot. That is working-path evidence, not proof of a particular
rendering workload or evidence about Linux's state.

## What to investigate next

The inspected callback calls dependency-builder `0xfffffff006bc8de4`; its
output count gates the later transition dispatcher `0xfffffff006bd81a8`.
A wider branch or different bridge mode/writer could also explain the empty
writer log. None is established by the present runtime sample. The next
focused offline analysis should trace the dependency count and dispatcher
branches, including whether the actual PMGR target was already 15 despite
the software cache's 0. A future read-only capture should report those
existing software values and decisions, and any wider tracing must have a
positive control for the writer hook.

The unfiltered archive and filtered `wide.json` are private under
`artifacts/live/private/ios-logarchive-j81-wide-01/`, because the archive can
contain personal system information. No extra GPU/PMGR MMIO read was added
by this probe.

After capture, the host requested a normal restart. The iPad reconnected and
device service reported build `19H394`. The DFU-to-Linux path was not tested.
