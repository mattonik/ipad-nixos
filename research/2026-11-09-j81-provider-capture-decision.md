# J81 pre-probe provider comparison and iOS capture decision

Bounded review, 2026-11-09. No device access. This supersedes older claims
that equated the two PMGR bridge version fields.

## A resolved bridge-mode property

In the decoded 19H422-associated iOS 15 kernelcache, instruction sequence
`0xfffffff006bc0344`–`...036c` looks up the string at
`0xfffffff005a54451`, `bridge-settings-version`, and stores its value to
PMGR object `+0x2684` when a value is returned. The preceding lookup at
`...030c`–`...0334` is instead `bridge-counter-version` at
`0xfffffff005a5443a`, stored at `+0x2680`. The direct kernelcache string
addresses and the disassembly agree. The saved Pongo ADT text has neither
property name, while it does contain `bridge-settings-9` and `-10`. It is a
separate capture, not proof of the exact ADT consumed in the 19H422 boot.

The earlier allocation audit found the normal AppleT7001PMGR allocation is
zero-filled. An existing scan of the shared ApplePMGR image for an immediate
`0x2684` finds one direct store, the conditional store above. Together with
property absence, this supports mode 0 in the ordinary captured-tree path,
under the same allocation assumptions. It is not runtime proof: computed or
indirect stores, other code, alternate allocation, a different tree or a
later mutation could change the field. In mode 0, the corrected power-up trace
uses the selector tables at entry `+0x18`. This narrows an uncertainty in the
comparison with Linux's planned 66 stores; it does not prove each write
persisted or that all iOS provider side effects were reproduced.

The 2026-11-08 bridge-writer note associated `bridge-settings-version` with
`+0x2680`; that was incorrect. It is `bridge-counter-version` that maps to
`+0x2680`. Its older non-increasing-branch interpretation was already
superseded by the [power-up correction](2026-11-09-j81-pmgr-clock-reset-path-correction.md).

## What the comparison can and cannot establish

The captured GFX record has no dependency IDs or relevant platform-action flag;
the inspected iOS 15 increasing-state path requests PMGR state 15 and, in
mode 0, applies selectors 9 and 10. The saved tables match the 66 stores planned
and checkpointed in the Linux campaign. Linux observed PMGR `0x3ff` and
GPC state 1/control `0x40000000`; the host-paced run received the checkpoint
before the RGX identity load, but neither a read result nor successful
completion. Those are software checkpoints, not readback of all bridge writes,
and the core-load instruction itself was not independently observed. See
[the campaign result](2026-11-09-j81-campaign-paced-result.md).

The comparison still does not establish the selected GFX frequency,
complete provider side effects, or earlier boot-stage state. It yields no
specific new register operation to replay. Repeating the same read would not
resolve those uncertainties.

## Capture options and decision

1. **First establish a working, ordinary iPadOS boot and build identity.**
   This requires device access but no GPU instrumentation. Determine whether
   the installed system is usable and identify its actual build; confirm the
   existing DFU/Pongo/Linux recovery path. This separates basic feasibility
   from the proposed trace. Do not assume the offline 19H422 cache is installed.
2. **Investigate a temporary preboot KPF instrumentation path.** A stock
   host KPF and a match-only custom prototype were exercised against the
   offline cache; the latter uniquely matched three candidate sites and
   rejected a changed or duplicated clock signature. No logging hook,
   instruction relocation, bootable patch, trace retrieval, or on-device
   recovery has been validated. See [the feasibility and prototype record](2026-11-09-j81-ios-startup-trace-feasibility.md).
   PongoOS provides a preboot patchfinder mechanism, but our host test is not
   proof it works on the iPad. The same-model report in
   [palera1n issue 761](https://github.com/palera1n/palera1n/issues/761)
   reports boot instability and should be treated as one report, not a
   prediction for this device.
3. **m1n1 hypervisor tracing is unproven on this A8X.** The upstream
   [m1n1 project](https://github.com/AsahiLinux/m1n1) provides useful tracing
   infrastructure, but the available investigation has not established a
   working A8X hypervisor boot of iPadOS. A chainloader or Linux boot alone
   would not establish that capability.
4. **Do not assume xnuspy will capture first boot.** Its documented
   userspace hook installation occurs too late for the initial probe, and
   its page-size assumptions need work on A8X. See
   [xnuspy](https://github.com/jsherman212/xnuspy) and the existing
   feasibility record for source and limits.

The immediate decision is to validate an ordinary installed iPadOS boot when
the user has the device. A custom trace should only follow a demonstrated
boot and a tested, retrievable instrumentation design. No new DFU GPU probe
is indicated by this review.

Evidence: local decoded cache SHA-256
`832cd980f257e6205b8ec131abea2a8470f3a3455f2c7039c890a091149c7389`,
`ios15pmgr-bridge-init-insn.log`, `ios15pmgr-version-fields.log`, and Pongo
ADT text `20261106T060741Z-pongo-adt.adt` under `artifacts/live/private/`.
