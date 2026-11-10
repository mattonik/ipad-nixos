# J81 iPadOS 15.8.5: boot-marker hardware result

2026-11-09. The user placed the connected iPad5,3 in DFU and ran palera1n
v2.4 in rootless mode with the temporary custom KPF module described in the
[build review](2026-11-09-j81-marker-kpf-build-review.md). Module SHA-256 was
`7fb1662f2552749707e0c37c3efdbaad40b1b15f91c326e525ae7ed7abeff870`.
The user reported palera1n initially stalled at `Booting PongoOS`; a
cable replug did not advance it. The user stopped and reran the command
without rebooting the iPad. The retry reported uploading its payloads,
issuing `bootx`, and `Booting Kernel`. We did not capture a separate visible
KPF receipt.

The iPad reappeared through the normal device service as iPadOS 15.8.5 build
19H394. After the user unlocked it, the Mac retrieved a private log archive.
The AGXG4G startup event at 22:43:17 local time had the original format
`AGXk: Starting GPU driver. Available features: %s` and rendered:

```
AGXk: Starting GPU driver. Available features: J1
```

Its process image UUID matched the target
`CC26BE6A-292B-3759-9ED0-290BCF18B090`. Earlier unmodified boots of this
device rendered the same event with `release`. The `J1` value is the marker
introduced by the KPF's two replacement instructions, providing positive
runtime evidence that the temporary patch executed and that its early boot
log argument survived to the archive. The match alone is not a raw register
trace and the absent USB-side receipt is not an independent confirmation of
the patchfinder's other checks.

The same captured boot reports `G4G A1`, 1 MGPU, 8 cores, and later
`GPU firmware booted successfully (AGXFirmwareKextG4G)`. This is evidence
that the patched boot got through these driver-reported stages, not proof of
all GPU workloads or all stock KPF behavior.

After retrieving the log, `idevicediagnostics restart` returned
`Restarting device.` The device reappeared in normal device service as
`iPad5,3`, 15.8.5, 19H394. The post-restart archive contains the patched `J1` event under boot UUID
`BC015F37-FEDE-4169-8D72-57B8AD237275` and a separate boot UUID
`C00EB6F4-032D-45E5-9DD6-76ED685AA6E0` whose startup event says `release`.
The timestamps in these two boot records are not chronologically ordered by
our observed restart, so the boot UUIDs matter and the recorded wall clock is
not used alone to establish order. This supports the normal-boot control; a
DFU-to-Linux recovery was not exercised.

Private artifacts, potentially containing personal system logs, are under
`artifacts/live/private/ios-logarchive-j81-marker-01/`: archive tar,
extracted `.logarchive`, `gpu-start.json` and filtered `gpu-success.log`.
They are not committed. No GPU MMIO probe was performed by the custom marker.

Next: design a separately reviewed, bounded observation of values already
read in the iOS probe. The marker proves delivery and log readout for this
one patch site and boot; it does not establish safe instrumentation at other
sites, logging while holding PMGR locks, or preservation after a panic.
