# J81 iPadOS tuner: live IORegistry check

Read-only diagnostics on the connected iPad after the 2026-11-11 tuner-probe
boot. `ideviceinfo` reports iPad5,3, iPadOS 15.8.5, build 19H394. No reboot,
MMIO access, setting change, or new kernel hook was performed.

`idevicediagnostics ioregentry AppleT7000SOCTuner` returned an IORegistry
entry with `IOClass = AppleT7000SOCTuner`,
`CFBundleIdentifier = com.apple.driver.AppleT7000SOCTuner`,
`IONameMatched = soc-tuner,t7000`, `IOProviderClass = ApplePMGRNub`, and
`IOMatchedAtBoot = true`. Thus the candidate service entry is present and
its registry properties report a boot match on this running system. These
properties do not establish the exact instant it matched or started, that
registration succeeded, which class is dispatched at every call, or that
the policy handler executed before GPU identity.

The separate `ioregentry soc-tuner` node reports `soc-tuning = 1`,
`fb-caching = 1`, set 0 IDs `0x12, 0x18, 0x1d, 0x74, 0x7c`, set 2 ID
`0x1c`, and `mcc-configs = 1, 2, 3, 4`. These agree with the previously
captured tree and support applying its topology to the running system; they
do not report live busy bitmaps, selected policy, callback execution or MCC
hardware state. The service and node are separate registry queries, not an
independently captured parent-child traversal.

This makes a later observation of tuner activity plausible, but does not
turn the earlier all-zero probe into evidence that the handler was skipped:
that probe reported only at GPU identity. The
[later boot-log candidate](2026-11-11-j81-tuner-later-export.md) could sample
the same controls again around firmware success, but a known user-triggered
event and post-interaction export point are still unproven.

Raw query outputs are private under
`artifacts/live/private/j81-tuner-ioreg-20261111/`. Service plist SHA-256
`d1c621f9b90ecb8b6deb46baa604dcc1c1631b35a40d7eaf232991b647891b81`;
node plist SHA-256
`eebe361be569de8f9311b7908ed6bdc7a209c3f232a60f4f18bd9029814e01ad`.
