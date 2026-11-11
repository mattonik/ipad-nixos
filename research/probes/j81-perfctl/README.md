# J81 iOS GFX perf-state control probe

Experimental 19H394 probe. It is the hardware-run
[five-point control probe](../j81-page5control/README.md) with one change:
all five reads use PMGR region 0 offset `0x1c200` (the GFX perf-state
control word, physical `0x20e01c200` by the Pongo ADT cross-reference)
instead of page-5 `0x5004`. Hooks, guards, signatures, buffer layout and log
format are unchanged, so the log labels keep their old names:

| Label | When | Now holds |
| --- | --- | --- |
| `PAGE5-early-before`, first `Q=` | early, before GPU power | `0x1c200` |
| `T=` | after the power provider call | `0x1c200` |
| `C=` | just before the `0x11` GPC state request | `0x1c200` |
| `M=` | after the successful GPC poll | `0x1c200` |
| `PAGE5-before`, last `Q=` | after GPU identity | `0x1c200` |

Purpose: Linux reads `0x80000000` before the GPC request and `0x80110100`
after it, with page-5 bit 30 never set
([note](../../2026-11-10-j81-gfx-perf-ctl-after-gpc1.md)). This run shows
what a working GPU has in the same word at the same points. Page 5 is not
read in this probe.

The source differs from the control probe only by the symbol prefix, the
`J81_PERFCTL_*` Pongo messages, and five `mov w2, #0xc200` /
`movk w2, #0x1, lsl #16` pairs. The shellcode grows by four words (964).

## Checks done (2026-11-11, no device run)

- Native ARM64 host simulations (`hosttest`, `irqtest`) pass with the fake
  reader accepting only offset `0x1c200`. The unmodified `0x5004` assembly
  fails against the same harness, so the tests do see the offset.
- KPF host harness on the exact 19H394 kernel: `J81_PERFCTL_EMIT prepared=1
  words=964`, `J81_PERFCTL_PATCH applied=1`. Each of eleven missing and
  eleven duplicate signatures and a wrong UUID is refused.
- Device build with `KPF_CFLAGS=-DJ81_PERFCTL_DEVICE_BUILD`, component
  `j81_perfctl_capture`, same Pongo checkout as the earlier probes. The
  final binary contains exactly five `0x52984002 0x72a00022` pairs.
- Private module `artifacts/live/private/j81-ios-perfctl-probe/perfctl4`,
  SHA-256 `ebb30acc414153bd7bc52f4f323bf32c491b7e655e4f14c5f05f71af742dd573`.

Hardware run 2026-11-11: see the [result](../../2026-11-10-j81-gfx-perf-ctl-after-gpc1.md#ipados-comparison-2026-11-11-the-word-is-the-same).

Limits are those of the control probe: mocked context, no proof of the
runtime PMGR object or mapping, and the reads are of an undocumented
register on a live iPadOS boot, which can perturb timing, hang or reboot. On
Linux the same word was read three times through `/dev/mem` without effect.

## Run

Same procedure as the [writer run](../j81-page5writer/MORNING.md) with this
module:

```sh
cd /Users/martinp/Work/Sandbox/ipadlinux/ipad-nixos
shasum -a 256 -c artifacts/live/private/j81-ios-perfctl-probe/SHA256SUMS
sudo boot/vendor/palera1n-macos-arm64 --rootless --override-kpf artifacts/live/private/j81-ios-perfctl-probe/perfctl4 --debug-logging
```

After iPadOS is up, capture into a fresh private directory:

```sh
umask 077
mkdir artifacts/live/private/ios-logarchive-j81-perfctl-01
idevicesyslog archive artifacts/live/private/ios-logarchive-j81-perfctl-01/capture.tar
mkdir artifacts/live/private/ios-logarchive-j81-perfctl-01/boot.logarchive
tar -xf artifacts/live/private/ios-logarchive-j81-perfctl-01/capture.tar -C artifacts/live/private/ios-logarchive-j81-perfctl-01/boot.logarchive
/usr/bin/log show --archive artifacts/live/private/ios-logarchive-j81-perfctl-01/boot.logarchive --style compact --predicate 'process == "kernel"' > artifacts/live/private/ios-logarchive-j81-perfctl-01/kernel.log
```

## Reading the result

- `C=80000000` and `M=80110100` (same as Linux): the word is not the
  difference; page-5 bit 30 remains the only known one.
- `M` or the last `Q` different from `0x80110100`: the Linux transition is
  not completing, and the differing field says where to look.
- Missing markers, a reboot or lost logs are inconclusive.
