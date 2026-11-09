# J81 iPadOS GPU startup trace: feasibility

Offline investigation, 2026-11-09. No device or GPU registers accessed.

## Finding

A boot-time XNU patch is a plausible way to observe selected early GPU
startup events. It is not yet a working trace: no custom hook, buffer,
retrieval path, patched iPadOS boot, or recovery run has been tested.

The local decoded iPad5,3 iPadOS 15.8.8 kernelcache is SHA-256
`832cd980f257e6205b8ec131abea2a8470f3a3455f2c7039c890a091149c7389`;
its association with the 19H422 IPSW is established in the
[provenance note](2026-11-08-j81-ios15-kernelcache-provenance.md), not a
live-device version check. Its AGXG4G code has three 16-byte candidate
instruction sequences, each appearing exactly once in that whole decoded
image in a byte search (each match is instruction-aligned):

| Unslid virtual address | Candidate observation | File offset | Limit |
|---|---|---|---|
| `0xfffffff006683918` | Before provider clock-enable call | `0x1b2f918` | Caller reaches it only when its guards permit. |
| `0xfffffff006683994` | GPC state request and poll region | `0x1b2f994` | A store/poll site, not proof a particular device takes the branch. |
| `0xfffffff00669bb54` | Identity routine entry, before RGX `+0x20` read | `0x1b47b54` | Does not capture the register transaction unless separately instrumented. |

Uniqueness is specific to this binary and the 16 bytes examined. It is not
an instruction relocation check, a complete control-flow proof, a robust
version-independent patchfinder, or evidence that another kernelcache matches.
The existing [iOS 15 pre-ID trace](2026-11-08-j81-ios15-g4g-pre-id-clock-power.md)
provides the surrounding sequence and guards.

## Host patchfinder baseline

The unmodified [palera1n PongoOS iOS15 branch](https://github.com/palera1n/PongoOS/tree/e98323f8a09abd80fc4cbcd74dee023b91a1ec22)
was cloned to a temporary directory at commit
`e98323f8a09abd80fc4cbcd74dee023b91a1ec22`. Its documented `checkra1n/kpf-test`
macOS arm64 target was built and run against the decoded cache, opened
read-only with private mappings. The stock host harness exited 0 and logged
`KPF: Applied patchset`; a debug line also said `Dounmount failed to find
second call for parent_vp`. This is a stock-patchfinder baseline, not proof
that every patch was appropriate, that any custom GPU patch works, or that
PongoOS can boot the patched image on J81. The tool identified the kernel
machine string as `7000`; its own source warns the kernel configuration
string need not distinguish A8 from A8X, so this is not a hardware identity
check. The input hash was unchanged afterward. The private log is
`artifacts/live/private/j81-kpf-test-20261109.log`, SHA-256
`3d1fe82b38d7f8497206cf6f16d659e6b439297202b773890c3f7326629ca8af`.
The checked-out source is an online reference, not a verified match for the
palera1n binary already used in this project.

PongoOS's `BOOT_FLAG_HOOK` invokes an XNU preboot hook; the KPF component
interface exposes pattern matching and instruction emission before XNU
starts. These are suitable mechanisms to investigate, not proof of a
particular logging technique or safe persistence. The local CPU-only test
must be extended to demonstrate exact image/target checks, branch reach,
relocation of overwritten instructions and preservation of registers before
any bootable experiment can be considered. A bounded buffer and reliable
post-boot extraction still need a design; a kernel panic before extraction
would lose an ordinary volatile buffer.

## Why xnuspy is not the first route

[xnuspy](https://github.com/jsherman212/xnuspy/tree/0d9fbbe32a134c89d3679ff7fc3fd1fdac3de7d4)
documents installing hooks from userspace and says 4 KiB devices are not
supported; its source hardcodes 16 KiB page-table geometry. Its default
hook-installation timing is therefore too late to assume it catches the
first GPU startup. A8X is documented as supporting 4 KiB and 64 KiB CPU
pages, not 16 KiB, in the [arm64 kernel page-size discussion](https://lkml.rescloud.iu.edu/hypermail/linux/kernel/2410.2/09515.html).
The running iPadOS kernel page size has not been measured here, but the 16 KiB
assumption is incompatible with the documented A8X CPU capability. Do not
run xnuspy unchanged on this basis.

## Recovery and next step

Before any device experiment, establish that the installed iPadOS is usable,
identify its actual kernelcache build and page size, and confirm a normal
boot and a return to the known DFU/Pongo/Linux path. Inspect boot arguments,
log extraction, and rollback using a temporary boot-only artifact before
any persistent installation or filesystem changes. Palera1n's documented
KPF override is a possible integration point, but compatibility with this
exact iPad and image is untested. An individual [A8X/iOS 15.8.8 palera1n
boot report](https://github.com/palera1n/palera1n/issues/761) also shows
that the iOS boot route can be unreliable; it does not establish that the
same failure will occur here.

A match-only KPF prototype for the three sites was subsequently exercised
offline, as described below. That checks target discovery only; it does not
validate a trace hook.

## Match-only KPF prototype

A temporary host-only KPF component registered exact 16-byte patterns for
the three candidate sites against `com.apple.AGXG4G` `__TEXT_EXEC,__text`.
Its callbacks count matches and do not modify matched instructions; its
finish callback fails unless all three counts equal one. It was built into
`kpf-test.macos` using the reference checkout above, and exercised only on
the host with private kernelcache mappings. The stock KPF still applies its
normal patches to those private in-memory mappings; this test does not
produce a bootable image or verify that the entire in-memory image is
unchanged.

| Input | clock / GPC / identity matches | Result |
|---|---|---|
| Original decoded 19H422 cache | 1 / 1 / 1 | Host test exit 0 |
| Private copy with one clock-signature byte changed | 0 / 1 / 1 | Intentional panic, exit 134 |
| Private copy with clock signature duplicated within the same section | 2 / 1 / 1 | Intentional panic, exit 134 |

Only the clock signature was independently mutated and duplicated; the
other two use the same enforcement logic but were not separately mutated.
The original input SHA-256 remained
`832cd980f257e6205b8ec131abea2a8470f3a3455f2c7039c890a091149c7389`.
The prototype source, registration diff, and three test logs are private in
`artifacts/live/private/j81-kpf-match-only/`; the source SHA-256 is
`b4e18af285490712b92168fbce5c66bfec6ca21ae259f1ed47f02ac63c47a7d1`.
The test binary's SHA-256 was
`038a1113293e632f53ed7e42bfcfbb5b0fe11fedf96e983364342092d797363e`.

This resolves exact target discovery for this extracted image, not the
installed iPad image. No branch, instruction relocation, kernel logging,
trace retrieval, iPadOS boot, or hardware recovery has been tested. A
future hook must separately prove those properties; matching alone cannot
make a boot patch safe.
