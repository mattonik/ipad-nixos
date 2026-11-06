# J81 GPC state-zero boundary: Apple order recovered offline

The iOS 8.1 decompilation now gives the exact host-side GPC helper order. The
register addresses match the existing J81 probes:

1. `FUN_ffffff80032a1f4c(..., 1)` writes `0x20` to GPC `+0x20000` (hold).
2. `FUN_ffffff80032a1bc8(..., 0)` waits for bit 4 of `+0x1000` to clear, then
   writes `0x10` (reset-state request).
3. `FUN_ffffff80032a1f84(...)` writes `0x40000000` to GPC `+0`.
4. The later GPC start path writes `0x11` to `+0x1000` and polls bit 4 clear.

Our Fender-wake artifact already reproduces those writes and bounded polls. The
new hardware batch proves the preceding PMGR transition, but the subsequent
read still returns `+0x1000 = 0x00000000`. This means the remaining unknown is
not the basic reset/hold/write order. It is either the Apple clock-state action
that precedes this helper or a missing condition that makes the final `0x11`
request take effect.

The same decompilation shows the clock-state path is separate: the special
clock action updates the provider's clock table and toggles the device-clock
provider before the GPC helper is called. Therefore another blind GPC write is
not justified. The next artifact should report the final `+0x1000` value after
the recovered wake sequence, with a host checkpoint before that read; it must
remain separate from the existing ID reader and must not touch RGX.
