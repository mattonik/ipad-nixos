# J81 iOS all-writer capture: 27 additional requests

On 2026-11-10 the user booted the [all-selector probe](2026-11-10-j81-ios-allwriters-probe.md)
on iPadOS 15.8.5 19H394. iPadOS returned, and the startup archive was saved
privately. The GPU driver reported G4G A1 and later reported firmware booted.

The recorded header has `B0` (no buffer overflow), a single GFX transition,
target 0 to 15, mode 0, and `W=0x5d` (93 writer-hook calls during the GFX
provider window). Exactly 93 records were logged, all tagged `P1` and
instance 0, with no unready markers. In reservation order they are:

| Selector | Count | Evidence |
| --- | ---: | --- |
| 7 | 10 | All 10 offset/value pairs exactly match captured Pongo ADT `bridge-settings-7`. |
| 11 | 3 | All 3 pairs exactly match captured `bridge-settings-11`. |
| 6 | 14 | All 14 pairs exactly match captured `bridge-settings-6`. |
| 9 | 33 | Same sequence captured previously and matched to Linux test4. |
| 10 | 33 | Same sequence captured previously and matched to Linux test4. |

This accounts for the 27 additional writer calls seen in the prior count,
in this boot. The hook is global: the records' timing in the provider
window and reservation order do **not** prove that the GFX path issued all
of them, that they are GPU prerequisites, or that each hardware store
completed. The original hook records calls before invoking the writer.
Concurrent activity or window-boundary races remain possible; a per-thread
or caller capture would establish attribution more strongly. No early `P0`
records were captured after hook installation, which says nothing about
earlier bootloader activity or uninstrumented writers.

The captured Pongo PMGR device records associate selector 7 with `DISP0`
(device 28), selector 11 with `USB` (device 6), and selector 6 with `ISP`
(device 24). These are candidate sources and make concurrent display, USB
and image-processing setup plausible; the global writer hook did not record
the calling device, so the associations do not establish the source of
these particular calls.

The captured Pongo ADT maps these selectors through PMGR `reg` index
`2 + selector`, under its `arm-io` translation. Its child base and span are
`0x06100000/0x2000` for 7, `0x0cb00000/0x1000` for 11, and
`0x05b00000/0x31000` for 6; every captured offset lies within the
corresponding range. This mapping is a device-tree cross-reference, not a
runtime observation of physical addresses. The older iOS 8.1 tree's
selector 6 table has only 12 entries and a `0x12000` range; the captured
Pongo table has two additional pairs, offsets `0x21000` and `0x21004`, both
with value `0x808`. The selector 7 and 11 captures match both checked
trees. Do not map the extra selector 6 offsets using the old 8.1 span.

The saved Linux test4 transcripts contain no explicit checkpoints at the
translated addresses for these three selector ranges. This is a lead, not
proof Linux never configured them: another driver or boot stage may have
done so, and the global iOS capture does not yet tie these calls to GFX.
Next investigate the PMGR clock-device records and trace caller/thread
attribution and existing Linux boot state before designing a targeted
hardware experiment. Do not blindly replay these writes.

Private full archive and filtered log:
`artifacts/live/private/ios-logarchive-j81-allwriters-01/`. Full device
logs may contain personal data and must not be published.
