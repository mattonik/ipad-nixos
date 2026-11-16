# J81 AGX post-power page-5 capture

## Purpose

This one-shot temporary iPadOS probe separates generic ApplePMGR startup from
the first AGX bring-up action. It replaces the instruction at the exact
19H394 `com.apple.AGXG4G` site `0xfffffff006683950`, immediately after the
stock provider clock and power callbacks at `0xfffffff006683930` and
`0xfffffff00668394c`, and before AGX maps or writes the GPC region.

The injected code maps PMGR, reads only `PMGR + 0x5004`, then deliberately
faults. The crash report's `x0` and `far` carry that word. It makes no PMGR,
GPC, bridge, or GPU-core writes itself.

| Capture result | Meaning |
| --- | --- |
| `x0` / `far` = `0x00000000` | Page-5 bit 30 is still clear after AGX's clock/power callbacks; its writer is later than this boundary. |
| `x0` / `far` = `0x40000000` | The bit is set by, or before, those callbacks; the remaining search is upstream of the GPC sequence. |
| Normal boot | The targeted path did not execute; no conclusion. |

The expected reboot is intentional. A hard reset returns the iPad to normal
iPadOS if the planned panic does not automatically reboot.

## Build identity and checks

The staged payload is:

```
artifacts/live/private/j81-ios-agx-postpower-panic/agx-postpower-page5p4-panic
SHA-256 258740bf270f10a049edc8b1035721e79986043c2867b8a5c85f0fb83789160a
```

It requires the observed iPadOS 15.8.5 `19H394` XNU UUID
`CC26BE6A-292B-3759-9ED0-290BCF18B090`, Darwin `21.6`, XNU
`8020.241.42~8`, and exactly one ten-word AGX signature. The native KPF
harness accepted the retained kernel and refused an altered UUID, missing
site, and duplicate site. The shell contract test confirms one `ml_io_map`,
one page-5 `+4` load, no injected MMIO store, and the intentional fault.

## Run

With the iPad in DFU:

```bash
cd /Users/martinp/Work/Sandbox/ipadlinux/ipad-nixos
shasum -a 256 -c <(printf '%s  %s\\n' \\
  258740bf270f10a049edc8b1035721e79986043c2867b8a5c85f0fb83789160a \\
  artifacts/live/private/j81-ios-agx-postpower-panic/agx-postpower-page5p4-panic)
sudo boot/vendor/palera1n-macos-arm64 --rootless \\
  --override-kpf artifacts/live/private/j81-ios-agx-postpower-panic/agx-postpower-page5p4-panic \\
  --debug-logging
```

After the reboot, unlock and reconnect the iPad. Retrieve the panic report
and read `x0` and `far`; do not infer a result from the presence of an Apple
logo or a red screen alone.
