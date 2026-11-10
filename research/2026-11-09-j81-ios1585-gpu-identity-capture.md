# J81 iPadOS 15.8.5: GPU identity hardware capture

2026-11-09. The user supplied a fresh DFU iPad and ran a temporary rootless
palera1n boot with the [host-reviewed identity probe](2026-11-09-j81-ios-identity-probe-build.md).
The module SHA-256 was
`f8f53f4163c6c778865e9f9fe840710ae4095721fbe2c89c24dde10cee337c9e`.
The user reported PongoOS booting and replugged; the iPad returned to iPadOS.
Initial lockdownd connections failed with mux error -8; a cable replug while
unlocked restored service. A private archive was then captured and decoded.

The iOS log archive recorded, under boot UUID
`DE998AAB-24A7-476B-A0C3-435207E72D76`:

```
AGXk: Starting GPU driver. Available features: release
AGXk: Starting GPU driver. Available features: I20=00070500 I18=011b0803
AGXk: Probing - Detected G4G A1 [1MGPUs8Cores 2Frags 1GTPSlots 1FRGSlots 1CDMSlots]
AGXk: AGXAcceleratorG4G_A0: GPU firmware booted successfully (AGXFirmwareKextG4G)
```

The identity probe records `w9` after the original 32-bit read of RGX
`+0x20` and `w8` after the subsequent original 32-bit read of RGX `+0x18`.
Thus, in this instrumented working-iOS boot, those existing reads returned
**`0x00070500`** and **`0x011b0803`**, respectively. On the J81 mapping
previously traced for this probe, these correspond to physical addresses
`0x201000020` and `0x201000018`. The logger's ordered arguments, marker and
boot UUID distinguish this event from other boot logs. The observation is a
runtime sample from the temporary patched iOS boot, not Linux register
readback; no extra GPU MMIO access is introduced by the probe.

The driver proceeded to report successful identification and firmware boot.
This does not prove the cause of Linux's stalled access, that every GPU
workload functions, or equality of PMGR and boot states between operating
systems. No device-side capture of bridge writes or selector state was made.

Private archive and filtered JSON under
`artifacts/live/private/ios-logarchive-j81-identity-01/` can include personal
system information and are excluded from Git. No standalone kernelcache or
Apple binary is published here.

After saving the capture, the host requested `idevicediagnostics restart`,
which reported `Restarting device.` A device ID reappeared, but subsequent
lockdownd queries returned mux error -8. Normal reboot completion was not
independently verified; USB networking had previously needed a cable replug.
