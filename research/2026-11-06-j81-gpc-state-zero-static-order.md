# J81 GPC state-zero boundary: Apple order recovered offline

The iOS 8.1 decompilation now gives the exact host-side GPC helper order. The
register addresses match the existing J81 probes:

1. `FUN_ffffff80032a1f4c(..., 1)` writes `0x20` to GPC `+0x20000` (hold).
2. `FUN_ffffff80032a1bc8(..., 0)` waits for bit 4 of `+0x1000` to clear, then
   writes `0x10` (reset-state request).
3. `FUN_ffffff80032a1f84(...)` writes `0x40000000` to GPC `+0`.
4. The later GPC start path writes `0x11` to `+0x1000` and polls bit 4 clear.

The Fender-wake artifact reproduces those writes and bounded polls, but keeps
hold asserted when requesting `0x11`; its final raw poll was zero, and its
success code checks only bit 4. The separate GPC-init sequence reached state 1
after a PMGR cycle without asserting hold. Orchard's reference clears hold,
polls state 0, then requests and polls state 1. This makes a missing hold
release a testable hypothesis, not proof of the cause. State 1 alone did not
make the direct RGX read safe.

The same decompilation shows the clock-state path is separate: the special
clock action updates the bridge tables and adjusts a busy counter; conditional
display-idle coordination may also occur. The prior inference that a missing
clock action caused the zero state was not established. A separately reviewed
Fender-only comparison could test the hold-release hypothesis without reading
RGX, but it would still involve MMIO writes and would not establish RGX safety.
