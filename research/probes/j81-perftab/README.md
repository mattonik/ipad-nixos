# J81 iOS perf-table probe

Experimental 19H394 probe, derived mechanically from the hardware-run
[perf-state control probe](../j81-perfctl/README.md) by `gen_perftab.py`.
Hooks, guards, signatures and log format are unchanged. Each of the five
reads samples a different PMGR region 0 word, so one boot compares five
static words with Linux:

| Label in the log | When | Offset | Linux value |
| --- | --- | --- | --- |
| first `Q=` (after `PAGE5-early-before`) | early | `0x23000` voltage control | `0x00000001` (written by m1n1) |
| `T=` | after the power provider call | `0x20120` `dwi` power state | `0x00000200` (off) |
| `C=` | before the `0x11` GPC request | `0x1c010` perf table, state 1 | `0x6436d063` |
| `M=` | after the GPC poll | `0x1c014` perf table, state 1, second word | `0x00000070` |
| last `Q=` (after `PAGE5-before`) | after GPU identity | `0x1c300` | `0x40000001` |

All five were read on Linux without effect. On iPadOS they are undocumented
reads on a live boot and can perturb timing, hang or reboot.

Checks (2026-11-11, no device run): host simulations pass with a fake reader
that requires this exact offset at each call and fail with the perfctl
assembly; the KPF harness on the exact 19H394 kernel reports
`J81_PERFTAB_EMIT prepared=1 words=964` and `J81_PERFTAB_PATCH applied=1`
and refuses eleven missing and eleven duplicate signatures and a wrong UUID;
the device binary (`KPF_CFLAGS=-DJ81_PERFTAB_DEVICE_BUILD`, component
`j81_perftab_capture`) contains each of the five instruction pairs once, in
the expected order. Private module
`artifacts/live/private/j81-ios-perftab-probe/perftab4`, SHA-256
`af39a37eba79c11249760ff8de4ba7d36d8055c6a9b7bd41c1db5531f73e2188`.

Run as for the perfctl probe, with
`--override-kpf artifacts/live/private/j81-ios-perftab-probe/perftab4` and a
fresh `ios-logarchive-j81-perftab-01` directory. The iPad must be unlocked
before the log pull.
