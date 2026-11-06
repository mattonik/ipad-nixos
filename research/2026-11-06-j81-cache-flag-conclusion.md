# J81 cache-flag conclusion

The local Darwin SDK and current XNU source expose the direction/type bits and
named cache-mode bits, but neither defines the legacy `0x80000` mapping bit
used by the recovered iOS 8.1 call sites. No local older XNU header or Orchard
source maps it to a cache mode.

The static result is therefore complete enough for a bounded hardware
**read-only/bridge** test, but not for firmware upload: Apple ownership is
physical I/O, while the cache mode and legacy map option remain unknown.

The existing testable artifact is the guarded PMGR/bridge segment payload. A
firmware test must remain blocked until an operator-present runtime observation
resolves the allocator/map behavior or a matching older Darwin source is found.
