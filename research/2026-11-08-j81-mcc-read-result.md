# J81 MCC one-shot read result (2026-11-08)

The supervised, acknowledged read completed on the existing J81 Linux RAM boot.
The 32-bit read at physical `0x200000830` returned `0x00000000`; the capture
reached `finished rc=0` and the watchdog disarmed normally. The capture log is
kept in the private live-artifacts area. No second read or other device access
was performed.

For comparison, the known iOS 8.1 write paths set these low-five-bit/bit-8
patterns (`value & 0x11f`): startup/selector 0, `0x010`; display-on selector 3,
`0x10a`; framebuffer/idle selector 4, `0x115`. Selector 4 also sets bit 6,
giving `0x155` under mask `0x15f`; selectors 0 and 3 preserve bit 6, so their
`0x15f` masked values depend on its prior value. These are conditional
software write effects, not documented hardware modes or proof of hardware
acceptance. The sampled zero matches none of the low-five-bit/bit-8 patterns.
It does not show whether MCC was initialized, powered, or otherwise owned, nor
whether an iOS callback ran on another boot. The Linux capture cannot recover
iOS runtime history or establish register semantics.

Address translation and bit-write analysis are recorded in
[`2026-11-07-j81-mcc-physical-address-audit.md`](2026-11-07-j81-mcc-physical-address-audit.md),
[`2026-11-07-j81-mcc-ios81-record-stride.md`](2026-11-07-j81-mcc-ios81-record-stride.md),
and [`2026-11-07-j81-mcc-hardware-meaning-audit.md`](2026-11-07-j81-mcc-hardware-meaning-audit.md).
