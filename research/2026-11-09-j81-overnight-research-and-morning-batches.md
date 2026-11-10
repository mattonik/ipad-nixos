# J81 GPU: aggregate-state investigation and morning batches

2026-11-09. This is a preparation report: the new matrix probe has **not**
been run on the iPad. All iOS instrumentation described here is specific to
the observed iPadOS 15.8.5 build 19H394 and its checked kernel UUID.

## What changed in our understanding

The [wide capture](2026-11-09-j81-ios-wide-bridge-result.md) observed the
GFX client's software cache changing from 0 to a requested 15, while the
buffer saw no matching selector 9/10, state 15 writer dispatch. The writer
hook still needs a positive hardware control; zero recorded entries is not
proof that no bridge write occurred. The same boot identified the GPU and
reported successful firmware startup.

Offline disassembly now identifies a second state, separate from the client
cache: the dependency builder compares an effective requested state with a
per-device **aggregate software state**. It adds an entry to its transition
list only when those values differ. The calling callback dispatches that
list only if its resulting count is nonzero. Therefore a client request of
0 to 15 can coexist with an aggregate comparison of 15 to 15 and no
dispatch. This is a testable explanation, not an observed runtime result,
and neither software state is a measurement of PMGR hardware state.
The builder also contains conditions that force the effective request to 15;
the aggregate comparison alone cannot identify an earlier consumer or rule
out one of those overrides.

For this build, the aggregate comparison is at XNU virtual address
`0xfffffff006bc9114`, the count check at `0xfffffff006bd7c1c`, and the
dispatcher at `0xfffffff006bd81a8`. The per-device aggregate is addressed
via the PMGR object at `+0x19094 + instance*0x260 + device`; the client
cache is separate, at `+0x19554`. These addresses are build-specific.

## Batch 1: discriminate aggregate state and dispatch

Prepared module: `artifacts/live/private/j81-ios-matrix-probe/checkra1n-kpf-pongo-j81-matrix`

SHA-256: `8bb488ec6a3da89b1c01973034ddfabd744154811199eb03a282c4dff6ae54c7`.
It is a temporary rootless iOS boot probe, not a Linux GPU driver. It adds no
GPU or PMGR MMIO reads or writes. It records the existing client decision,
aggregate comparison, transition-list count and selector 9/10 writer
requests from early XNU through the first GFX clock-provider return. It
logs in batches after the provider returns. It does not observe iBoot or
earlier boot stages. The selector recording is global and can include
concurrent unrelated requests; reservation order is not proof of MMIO
completion. A finite 96-entry buffer records overflow explicitly.

From the repository root, after confirming DFU and keeping the iPad
connected, the operator can run:

```sh
printf '%s  %s\n' 8bb488ec6a3da89b1c01973034ddfabd744154811199eb03a282c4dff6ae54c7 artifacts/live/private/j81-ios-matrix-probe/checkra1n-kpf-pongo-j81-matrix | shasum -a 256 -c - && sudo boot/vendor/palera1n-macos-arm64 --rootless --override-kpf artifacts/live/private/j81-ios-matrix-probe/checkra1n-kpf-pongo-j81-matrix --debug-logging
```

As in the previous boots, if palera1n is stuck at “Booting PongoOS” while
PongoOS is visible, stop it and rerun the command. Once iPadOS is up, unlock
and collect the complete private log archive before a normal restart. Do not
publish the archive: it may include personal data. A cable replug after
unlock was needed on earlier captures.

The compact `AGXk`-prefixed output contains `D` (client cache old > request),
`A` (old aggregate > effective aggregate request), `N` (transition count),
`B` (buffer overflow), then zero or more `09:`/`0a:` writer records.
The digits in `D1`, `A1`, `N1` are observation flags: `0` means the hook
was not observed, not that the state or count was zero. `?` means an entry
was not ready when read. No marker is also inconclusive; check patch and
logging/boot evidence before interpreting it.

| Observation | Meaning and next batch |
| --- | --- |
| `D1:0>f`, `A1:f>f`, `N1:0` | Supports aggregate-already-active explanation. Trace when the aggregate became 15 and inspect earlier consumers and force-on conditions; do not assume hardware is on. |
| `A1` differs and `N1` is nonzero, but no matching writer entries | Investigate the dispatcher's mode, target and alternate writers; establish a positive writer-hook control before concluding it was skipped. |
| Matching writer entries | Compare selector, arguments, context and sequence against Linux; recording a request does not prove the write completed or the GPU is accessible. |
| `D0`, `A0`, `N0`, overflow, missing marker, reboot or hang | Inconclusive. Preserve the log and use the known-working controls below before changing the hypothesis. |

The module checks the kernel UUID and unique exact instruction signatures at
all five patch points, validates branch reachability, and applies its hooks
as a group or none. It has been built as an ARM64 kext. A host signature
harness accepted the expected kernel image and rejected each missing or
duplicated signature and a wrong UUID. Native ARM64 host tests passed for
both aggregate scenarios, unseen markers, 96-entry overflow, concurrent
reservations, and IRQ-masked logging suppression. The harness simulates
device execution: these tests do not establish real boot-time memory
mapping, register preservation under all contexts, timing or lock safety.
Source and host test inputs are kept next to the private binary.

## Batch 2: recover and separate instrumentation failures

If batch 1 fails to boot or logs nothing usable, first return to normal
iPadOS. If a further temporary boot is practical, repeat the previously
successful **wide** control, SHA-256
`395d32ff92b017434909eb020e6919c28ff5c227770dfc0cb50a55ffed239f20`, at
`artifacts/live/private/j81-ios-wide-probe/checkra1n-kpf-pongo-j81-wide`.
It provides the prior client-decision and writer-window baseline, but is
not a positive writer control. If necessary, the earlier identity-only
module is a smaller fallback:
`artifacts/live/private/j81-ios-identity-probe/checkra1n-kpf-pongo-j81-identity`,
SHA-256 `f8f53f4163c6c778865e9f9fe840710ae4095721fbe2c89c24dde10cee337c9e`.
Both have booted on this iPad previously. Use the same command as batch 1,
substituting the module and checksum. These controls do not answer the new
aggregate question; their purpose is to locate a boot or capture failure.

After a conclusive batch 1, the appropriate next instrument depends on the
result in the table. It is a planned follow-up, not a second prebuilt module.
Do not use guessed reset, PLL, GPU-core or PMGR writes as a combination
search. The probe can stall or reboot the device, and a further DFU cycle
may be required.

## Followed projects and public work

Checked 2026-11-09. Orchard's A10 work reports fixes tested with Firefox,
WebGL and dEQP and newer [render job lifetime and retirement changes](https://github.com/OrchardLinux/orchard/commit/de8f6a0feb0a).
The earlier [Firefox/WebGL GPU changes](https://github.com/OrchardLinux/orchard/commit/711ec3e3fad6)
are useful for the later rendering stage. These are A10 observations, not a
verified A8X bring-up sequence. Our Orchard documentation [PR #112](https://github.com/OrchardLinux/orchard/pull/112)
remains open; the open-PR query found no second GPU-titled PR.

iPhOmarchy reports [A11 GFX domain success under its consumer](https://github.com/ryzensnyper/iPhOmarchy/commit/2f56a53f5a43),
and a later [IOP/firmware payload was built](https://github.com/ryzensnyper/iPhOmarchy/commit/94817450d802),
not reported boot-tested in that update. Its RTKit-era architecture differs
from A8X; use it for methodology, not register sequences.

[Project Cascadia](https://github.com/rzxvx/Project-Cascadia/commits/main/)
continues A5 NAND boot work; this check found no new A8X GPU result.
Mesa's recent [PowerVR change](https://gitlab.freedesktop.org/mesa/mesa/-/commit/a6fd0595abf892c03960cdfdc5bcbcf906a019f7)
adds supported sample counts based on capabilities, a later userspace feature,
not an A8X power-on solution. These checks do not prove there is no relevant
work elsewhere.
