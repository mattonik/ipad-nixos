# J81 iPadOS page-5 writer capture, 2026-11-11

A temporary 19H394 rootless boot used the [page-5 writer probe](probes/j81-page5writer/README.md), module SHA-256 `d0e8c2c019a469db97540eb9715efd85b6c8562430c262a37b6361bd098833b4`. iPadOS reached its Home screen; its private log archive was retrieved after a USB reconnect. The 10:52:34 local-time GPU startup records contain:

| Record | Value | Interpretation |
| --- | --- | --- |
| Early `Q` | `00000000` | Earlier page-5 +4 read |
| `P1`, `G1`, `I` | `000003ff`, `00000001`, `00070500` | Captured PMGR/GPC and GPU identity checkpoints |
| `Z` | `00000002:00000001:00000000:00000000` | Phase closed; candidate store site reached; zero matching reservations at snapshot; no overflow recorded |
| `C`, `T`, `M` | `00000000`, `00000000`, `40000000` | Bit 30 was clear at the control and power-boundary samples, set after the GPC poll |
| Late `Q` | `40000000` | Later page-5 +4 read |

There were no `W=` records in this capture. The iOS GPU driver subsequently reported G4G A1 and successful firmware boot. These are driver log reports, not proof of a rendering test. `seen=1` confirms that the patched store site was reached, but does not prove the target object or physical mapping, nor that a matching store was absent: a writer can be delayed before reservation until after the snapshot. Direct stores, other PMGR objects or aliases, firmware and autonomous hardware are also outside this filter. Thus this does not identify the bit's cause or justify writing it on Linux.

The iPad startup capture and extracted logs are private under `artifacts/live/private/ios-logarchive-j81-page5writer-01/`; they can contain personal information and must not be published. No Linux hardware access or GPU-core read was performed in this run.
