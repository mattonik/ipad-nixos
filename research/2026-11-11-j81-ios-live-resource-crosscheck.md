# J81 live iPadOS GPU and PMGR resource cross-check

On 2026-11-11 the already booted, unlocked iPad reported iPadOS 15.8.5
build 19H394. `idevicediagnostics ioregentry sgx` and `ioregentry pmgr`
returned IORegistry property snapshots. These are metadata queries; no
extra GPU or PMGR MMIO read, page-5 write, reboot, or probe was performed.
Private plist captures remain at
`artifacts/live/private/ios-registry-runtime-20261111/`.

The live `sgx` entry has `compatible = gpu,t7001` and two
`IODeviceMemory` entries, in this order:

| Index | Physical address | Length |
| --- | --- | --- |
| 0 | `0x201000000` | `0x100000` |
| 1 | `0x201e00000` | `0x100000` |

Its `clock-gates` and `power-gates` each contain ID `0x7c`. The live PMGR
entry reports index 0 at `0x20e000000` (length `0x40000`) and indices 11
and 12 at `0x201f00000` and `0x201f80000` (each length `0x81000`). Its
`bridge-reg-index` is 2, and its 264-byte `bridge-settings-9` and
`bridge-settings-10` each hash to
`b3818d986ab8a731bd769f56473970db58ae531f41b17b7dd316cfb2465140d4`.
These match the previously captured Pongo ADT table bytes, while the
resource addresses independently corroborate the earlier translations.

The [static G4G path](2026-11-08-j81-ios15-g4g-pre-id-clock-power.md)
selects index 0 for RGX and index 1 for GPC when the provider exposes two
regions; its identity routine reads RGX `+0x20`. The relevant code range
was also checked for [19H394 parity](2026-11-11-j81-19h394-code-parity.md).
The live resource list therefore supports `0x201000020` as the Linux
core-read comparison target, and the live PMGR entry supports the page-5
physical cross-reference `0x20e005004`. This reduces the likelihood that
the differing observed result is merely an incorrect translation of the
published resource list.

These after-boot published properties do not independently prove the live
identity hook's provider/object binding, exact mapping and attributes at the
earlier checkpoint, physical transaction completion, or bridge register
values. The matching bridge property bytes show configuration data, not
that either system applied or retained all 66 settings. They also do not
explain page-5 bit 30 or establish why the Linux core read did not return.
