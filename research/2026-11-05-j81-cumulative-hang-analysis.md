# Cumulative bridge-segment hang: offline conclusion

The successful runs and the failed same-boot run now separate two effects:

1. A clean boot can accept the first selector-9 setup plus the first four
   table entries, and a fresh boot can accept the next four entries.
2. After those writes, a further run hung at the *GPC state read*, before any
   new bridge write. The watchdog recovered the iPad to iOS.

The existing iOS 8.1/iPadOS 15 trace explains why this is not a simple table
copy. Apple performs the bridge writes from a conditional clock-state action
while bringing GFX to its requested state; the Linux diagnostic currently
turns the PMGR power domain on directly and then replays raw stores. The
Apple path also performs provider clock/power operations, GPC setup, a bit-4
poll, and a 10-microsecond delay before the early GPU match path. The direct
PMGR consumer does not demonstrate that those clock-state side effects or
ordering were reproduced.

Therefore the hang is evidence of an incomplete state machine, not evidence
that table entry `+0x40020` is intrinsically bad. Do not extend the table or
attempt GPC initialization until the clock-action and GPC ordering are
reconstructed offline. The next hardware experiment, if any, should be a
fresh-boot test of one explicitly identified missing prerequisite, not a
larger raw segment.
